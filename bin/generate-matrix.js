#!/usr/bin/env node

const FLAVORS = [
    "alpine",
    "bullseye",
];

/**
 * Hardcode some versions, because e.g. there are no tags for them.
 */
const HARDCODED_MATRIX = [
    {
        "shopware-version": "6.4",
        "php-version": "8.1",
        "template": "https://github.com/shopware/shopware",
    },
    {
        "shopware-version": "6.5.x",
        "php-version": "8.1",
        "template": "https://github.com/shopware/shopware",
    },
    {
        "shopware-version": "trunk",
        "php-version": "8.2",
        "template": "https://github.com/shopware/shopware",
    },
];

const loadShopwarePHPVersions = async () => {
    const response = await fetch("https://raw.githubusercontent.com/FriendsOfShopware/shopware-static-data/main/data/all-supported-php-versions-by-shopware-version.json")
    return await response.json();
}

const loadMinPHPVersion = async () => {
    const response = await fetch("https://php.watch/api/v1/versions/secure")
    const result = await response.json();

    const [firstVersion] = Object.values(result.data);

    return firstVersion.name;
}

const parseMinorVersion = (version) => {
    const parts = version.match(/[0.9]*.\.([0-9]*)\..*/);
    if (parts.length < 2) {
        throw new Error("Unexpected version format: " + version);
    }

    return parseInt(parts[1], 10);
}

const getTemplate = (version) => {
    const minor = parseMinorVersion(version);

    // For everything below 6.5, we need the shopware/production template.
    if (minor <= 4) {
        return "https://github.com/shopware/production";
    }

    return "https://github.com/shopware/shopware";
}

async function main() {
    const minPHPVersion = await loadMinPHPVersion();

    const shopwarePhpVersions = await loadShopwarePHPVersions();

    const shopwareMinorVersions = [];

    for (const [shopwareVersion, phpVersions] of Object.entries(shopwarePhpVersions)) {
        const [_, platform, major, minor, patch, prerelease, buildmetadata] = shopwareVersion.match(/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$/) ?? [];

        if (prerelease !== undefined || buildmetadata !== undefined) {
            continue;
        }

        const majorMinor = `${platform}.${major}.${minor}`;

        if (shopwareMinorVersions[majorMinor] !== undefined && shopwareMinorVersions[majorMinor].shopwareVersion >= shopwareVersion) {
            continue;
        }

        shopwareMinorVersions[majorMinor] = {shopwareVersion, phpVersions}

    }

    let matrix = [];

    for (const [_, line] of  Object.entries(shopwareMinorVersions)) {
        const minPhpVersions = line.phpVersions.filter((phpVersion) => phpVersion >= minPHPVersion);

        if (minPhpVersions.length === 0) {
            continue;
        }

        FLAVORS.forEach((flavor) => {
            matrix.push({
                "shopware-version": 'v' + line.shopwareVersion,
                "php-version": minPhpVersions[0],
                "flavour": flavor,
                "template": getTemplate(line.shopwareVersion),
            });
        });
    }

    if (matrix.length === 0) {
        throw new Error("No matrix entries generated.");
    }

    HARDCODED_MATRIX.forEach((entry) => {
        FLAVORS.forEach((flavor) => {
            entry.flavour = flavor;

            matrix.push(entry);
        });
    });

    console.log(JSON.stringify({
        include: matrix.flat(),
    }));
}

main();