#!/usr/bin/env python3
"""Resolve upstream inputs once, and reuse images only when those inputs match."""

import argparse
import datetime
import functools
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tarfile
import tomllib
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
LABEL = "io.friendsofshopware.build-inputs"


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def output(name, value):
    with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
        stream.write(f"{name}={value}\n")


def refresh_key():
    if os.environ.get("FORCE_REFRESH", "false") == "true":
        return "manual-" + os.environ["GITHUB_RUN_ID"]
    return datetime.datetime.now(datetime.timezone.utc).strftime("%G-W%V")


@functools.lru_cache(maxsize=None)
def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "platform-plugin-dev-docker"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def image_info(reference, missing_ok=False):
    command = ["docker", "buildx", "imagetools", "inspect", reference,
               "--format", '{"manifest": {{json .Manifest}}, "image": {{json .Image}}}']
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        if missing_ok and any(message in result.stderr.lower() for message in
                              ("not found", "manifest unknown", "name unknown")):
            return None
        raise RuntimeError(f"Cannot inspect {reference}: {result.stderr}")
    info = json.loads(result.stdout)
    image = info["image"]
    if "config" not in image:
        image = image["linux/amd64"]
    return {"digest": info["manifest"]["digest"],
            "labels": image.get("config", {}).get("Labels", {}) or {}}


@functools.lru_cache(maxsize=None)
def pinned_image(reference):
    return reference + "@" + image_info(reference)["digest"]


@functools.lru_cache(maxsize=None)
def revision(repository, ref):
    result = subprocess.run(["git", "ls-remote", "--exit-code", repository,
                             f"refs/heads/{ref}", f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}"],
                            check=True, capture_output=True, text=True)
    refs = dict(line.split()[::-1] for line in result.stdout.splitlines())
    for name in (f"refs/tags/{ref}^{{}}", f"refs/tags/{ref}", f"refs/heads/{ref}"):
        if name in refs:
            sha = refs[name]
            if not re.fullmatch(r"[0-9a-f]{40}", sha):
                raise ValueError(f"Invalid revision for {ref}: {sha}")
            return sha
    raise ValueError(f"Cannot resolve {repository} {ref}")


@functools.lru_cache(maxsize=None)
def npm_version(package, major=None):
    if major is None:
        return json.loads(download(f"https://registry.npmjs.org/{package}/latest"))["version"]
    versions = json.loads(download(f"https://registry.npmjs.org/{package}"))["versions"]
    candidates = [v for v in versions if re.fullmatch(rf"{major}\.\d+\.\d+", v)]
    return max(candidates, key=lambda v: tuple(map(int, v.split("."))))


@functools.lru_cache(maxsize=None)
def nodesource_version(major):
    url = f"https://deb.nodesource.com/node_{major}.x/dists/nodistro/main/binary-amd64/Packages.gz"
    packages = gzip.decompress(download(url)).decode()
    versions = []
    for paragraph in packages.split("\n\n"):
        fields = dict(line.split(": ", 1) for line in paragraph.splitlines() if ": " in line)
        if fields.get("Package") == "nodejs":
            versions.append(fields["Version"])
    if not versions:
        raise ValueError(f"No Node.js {major} packages found")
    def version_key(version):
        # NodeSource publishes stable Node versions with a numeric packaging revision.
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)-(\d+)nodesource(\d+)", version)
        if match is None:
            raise ValueError(f"Unexpected NodeSource version: {version}")
        return tuple(map(int, match.groups()))
    return max(versions, key=version_key)


@functools.lru_cache(maxsize=None)
def alpine_versions(distribution):
    packages = {}
    for repository in ("main", "community"):
        data = download(f"https://dl-cdn.alpinelinux.org/alpine/v{distribution}/{repository}/x86_64/APKINDEX.tar.gz")
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            index = archive.extractfile("APKINDEX").read().decode()
        for paragraph in index.split("\n\n"):
            fields = dict(line.split(":", 1) for line in paragraph.splitlines() if ":" in line)
            if fields.get("P") in ("nodejs", "npm"):
                packages[fields["P"]] = fields["V"]
    return packages


def load_profiles(flavour):
    with (ROOT / flavour / "build-profiles.toml").open("rb") as stream:
        profiles = tomllib.load(stream)["profiles"]
    for name, profile in profiles.items():
        for key in ("php", "distribution", "node", "npm"):
            if not isinstance(profile.get(key), str) or not profile[key]:
                raise ValueError(f"{flavour} profile {name}: {key} must be a nonempty string")
        if not isinstance(profile.get("frozen-base"), bool):
            raise ValueError(f"{flavour} profile {name}: frozen-base must be a boolean")
        if "playwright" in profile and not isinstance(profile["playwright"], str):
            raise ValueError(f"{flavour} profile {name}: playwright must be a version string or latest")
        if profile["npm"] == "distribution" and profile["node"] != "distribution":
            raise ValueError(f"{flavour} profile {name}: distribution npm requires distribution Node.js")
    return profiles


def profile_inputs(entry):
    profiles = load_profiles(entry["flavour"])
    name = entry["profile"]
    if name not in profiles:
        raise ValueError(f'Unknown {entry["flavour"]} build profile: {name}')
    return profiles[name]


def base_matrix():
    bases = {}
    for path in sorted(ROOT.glob("*/build-profiles.toml")):
        flavour = path.parent.name
        for profile in load_profiles(flavour).values():
            key = (flavour, profile["php"])
            spec = {"flavour": flavour, "php-version": profile["php"],
                    "distribution-version": profile["distribution"], "frozen-base": profile["frozen-base"]}
            if key in bases and bases[key] != spec:
                raise ValueError(f"Conflicting base settings for {key}")
            bases[key] = spec
    return {"include": [{k: v for k, v in base.items() if k != "frozen-base"}
                        for base in bases.values() if not base["frozen-base"]]}


def runtime_inputs(entry, refresh):
    profile = profile_inputs(entry)
    php, flavour = profile["php"], entry["flavour"]
    base = f'{os.environ["DOCKER_REPOSITORY"]}-base:{php}-{flavour}'
    spec = {"php-version": php, "flavour": flavour, "base-image": pinned_image(base),
            "distribution": profile["distribution"], "refresh": refresh,
            "npm-version": "", "playwright-version": ""}
    if profile["node"] == "distribution":
        packages = alpine_versions(profile["distribution"])
        spec["node-version"] = packages["nodejs"]
        major = packages["nodejs"].split(".")[0]
    else:
        major = profile["node"]
        if major == "current":
            releases = json.loads(download("https://nodejs.org/dist/index.json"))
            major = releases[0]["version"].lstrip("v").split(".")[0]
        spec["node-version"] = nodesource_version(major)
    if profile["npm"] == "distribution":
        spec["npm-version"] = packages["npm"]
    elif profile["npm"] != "bundled":
        spec["npm-version"] = npm_version("npm", int(profile["npm"]))
    playwright = profile.get("playwright")
    if playwright:
        spec["playwright-version"] = npm_version("playwright") if playwright == "latest" else playwright
    spec["node-major"] = major
    spec["runtime-id"] = f"{php}-{flavour}-node{major}"
    dockerfile = Path(flavour, "Dockerfile").read_text().split("FROM runtime AS shopware", 1)[0]
    spec["recipe"] = hashlib.sha256(dockerfile.encode()).hexdigest()
    spec["fingerprint"] = fingerprint(spec)
    return spec


def docker_arguments(spec):
    names = {"BASE_IMAGE": "base-image",
             "DISTRIBUTION_VERSION": "distribution", "NODE_MAJOR": "node-major",
             "NODE_VERSION": "node-version", "NPM_VERSION": "npm-version",
             "PLAYWRIGHT_VERSION": "playwright-version", "DEPENDENCY_REFRESH": "refresh"}
    return [value for name, key in names.items() for value in ("--build-arg", f"{name}={spec[key]}")]


def local_build(args):
    os.chdir(ROOT)
    os.environ.setdefault("DOCKER_REPOSITORY", "ghcr.io/friendsofshopware/platform-plugin-dev")
    entry = {"flavour": args.flavour, "profile": args.profile}
    if args.target == "shopware" and not args.shopware_version:
        raise ValueError("--shopware-version is required when building Shopware")
    if args.force_refresh:
        refresh = "manual-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    else:
        refresh = refresh_key()
    if args.target == "base":
        profile = profile_inputs(entry)
        if profile["frozen-base"]:
            raise ValueError("This profile reuses a frozen published base; select runtime or shopware instead")
        command = ["docker", "buildx", "build", "--pull", "--provenance=false", "--load",
                   "--file", f"{args.flavour}/Dockerfile.base",
                   "--build-arg", f'PHP_VERSION={profile["php"]}',
                   "--build-arg", f'DISTRIBUTION_VERSION={profile["distribution"]}',
                   "--build-arg", f"DEPENDENCY_REFRESH={refresh}"]
    else:
        spec = runtime_inputs(entry, refresh)
        command = ["docker", "buildx", "build", "--load", "--file", f"{args.flavour}/Dockerfile",
                   "--target", args.target, *docker_arguments(spec)]
        if args.target == "shopware":
            sha = revision(args.template, args.shopware_version)
            command += ["--build-arg", f"SHOPWARE_VERSION={args.shopware_version}",
                        "--build-arg", f"SHOPWARE_SHA={sha}",
                        "--build-arg", f"TEMPLATE_REPOSITORY={args.template}"]
    command += ["--tag", args.tag, "."]
    print(shlex.join(command), flush=True)
    if not args.dry_run:
        subprocess.run(command, check=True)


def plan():
    refresh = refresh_key()
    entries = json.loads(os.environ["MATRIX"])
    if isinstance(entries, dict):
        entries = entries["include"]
    runtimes = {}
    for entry in entries:
        spec = runtime_inputs(entry, refresh)
        previous = runtimes.get(spec["runtime-id"])
        if previous is not None and previous != spec:
            raise ValueError(f'Conflicting inputs for runtime {spec["runtime-id"]}')
        runtimes[spec["runtime-id"]] = spec
        entry["runtime-id"] = spec["runtime-id"]
        entry["shopware-sha"] = revision(entry["template"], entry["shopware-version"])
    Path("build-plan.json").write_text(json.dumps({"runtimes": runtimes, "entries": entries}))
    output("runtime-matrix", json.dumps({"include": list(runtimes.values())}))
    print(f"Resolved {len(entries)} Shopware builds and {len(runtimes)} runtime variants")


def check_image():
    inputs = json.loads(os.environ["BUILD_INPUTS"])
    expected = inputs["fingerprint"]
    published = image_info(os.environ["IMAGE"], missing_ok=True)
    # Branch builds always validate the current recipe, even if main already published it.
    reuse = (os.environ.get("GITHUB_REF") == "refs/heads/main" and published is not None
             and published["labels"].get(LABEL) == expected)
    output("build", "false" if reuse else "true")
    output("fingerprint", expected)
    output("image", os.environ["IMAGE"] + "@" + published["digest"] if reuse else "")
    print("Inputs unchanged; reuse published image" if reuse else "Build required")


def complete_runtime():
    spec = json.loads(os.environ["BUILD_INPUTS"])
    image = os.environ.get("REUSED_IMAGE", "")
    if not image and os.environ.get("PUSH") == "true":
        digest = os.environ["DIGEST"]
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise ValueError("Runtime build did not return a digest")
        image = os.environ["IMAGE"] + "@" + digest
    spec["runtime-image"] = image
    Path(f'runtime-{spec["runtime-id"]}.json').write_text(json.dumps(spec))


def merge():
    plan = json.loads(Path("build-plan.json").read_text())
    runtimes = {spec["runtime-id"]: spec for path in Path(".").glob("runtime-*.json")
                for spec in [json.loads(path.read_text())]}
    for entry in plan["entries"]:
        spec = runtimes[entry["runtime-id"]]
        entry.update(spec)
        recipe = hashlib.sha256(Path(entry["flavour"], "Dockerfile").read_bytes()).hexdigest()
        entry["fingerprint"] = fingerprint({"runtime": spec["runtime-image"] or spec["fingerprint"],
                                             "sha": entry["shopware-sha"], "template": entry["template"],
                                             "version": entry["shopware-version"], "recipe": recipe,
                                             "refresh": spec["refresh"]})
    output("matrix", json.dumps({"include": plan["entries"]}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "check-image", "complete-runtime", "merge", "refresh", "profiles"):
        commands.add_parser(name)
    local = commands.add_parser("build", help="Build locally using the same profiles and upstream inputs as CI")
    local.add_argument("--flavour", required=True, choices=["alpine", "debian"])
    local.add_argument("--profile", required=True)
    local.add_argument("--shopware-version")
    local.add_argument("--template", default="https://github.com/shopware/shopware")
    local.add_argument("--target", default="shopware", choices=["base", "runtime", "shopware"])
    local.add_argument("--tag", required=True)
    local.add_argument("--dry-run", action="store_true", help="Resolve inputs and print the command without building")
    local.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()
    if args.command == "refresh":
        output("refresh", refresh_key())
    elif args.command == "profiles":
        output("base-matrix", json.dumps(base_matrix()))
    elif args.command == "build":
        local_build(args)
    else:
        globals()[args.command.replace("-", "_")]()
