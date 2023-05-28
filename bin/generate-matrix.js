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
        "shopware-version": "trunk",
        "php-version": "8.1",
        "flavour": "bullyseye",
        "template": "https://github.com/shopware/platform",
    },
    {
        "shopware-version": "trunk",
        "php-version": "8.1",
        "flavour": "alpine",
        "template": "https://github.com/shopware/platform",
    },
    {
        "shopware-version": "trunk",
        "php-version": "8.2",
        "flavour": "bullyseye",
        "template": "https://github.com/shopware/platform",
    },
    {
        "shopware-version": "trunk",
        "php-version": "8.2",
        "flavour": "alpine",
        "template": "https://github.com/shopware/platform",
    },
];

const loadShopwarePHPVersions = async () => {
    const response = await fetch("https://raw.githubusercontent.com/FriendsOfShopware/shopware-static-data/main/data/all-supported-php-versions-by-shopware-version.json")
    return await response.json();
}

const parseMinorVersion = (version) => {
    const parts = version.match(/v[0.9]*.\.([0-9]*)\..*/);
    if (parts.length < 2) {
        throw new Error("Unexpected version format: " + version);
    }

    return parseInt(parts[1], 10);
}

const parseMajorVersion = (version) => {
    const parts = version.match(/v\d+\.(\d+).*/);
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

    return "https://github.com/shopware/platform";
}

/**
 * Helper to find the supported PHP versions in the static-dump. 
 * Needed because some (older) shopware tags have an v before the composer version.
 */
const findSupportedPhpVersion = (supportedPhpVersions, shopwareVersion) => {
    const parts = shopwareVersion.match(/^v?(.*)/);
    if (parts.length < 2) {
        throw new Error(`Something went wrong, extracting the version from ${shopwareVersion}. Got ${parts} from the regex.`)
    }
    const version = parts[1];

    if (supportedPhpVersions[version]) {
        return supportedPhpVersions[version];
    }

    if (supportedPhpVersions['v' + version]) {
        return supportedPhpVersions['v' + version];
    }

    // Shopware Version not found. Can happen when e.g. RCs are not published on Packagist.
    return undefined;
}

async function main(args) {
    if (args.length < 3) {
        console.error("Usage: generate-matrix.js <major-version>");
        console.error("Usage: generate-matrix.js 4 -- generate matrix for Shopware 6.4");
        console.error("Usage: generate-matrix.js 5 -- generate matrix for Shopware 6.5");
        process.exit(1);
    }

    const majorVersion = parseInt(args[2], 10);

    const response = await fetch("https://api.github.com/repos/shopware/platform/git/refs/tags")
    const tags = await response.json();

    const versions = tags.map((tag) => {
        const version = tag.ref.replace("refs/tags/", "");
        const major = parseMajorVersion(version);

        if (major !== majorVersion) {
            return undefined;
        }

        return version;
    }).filter(version => !!version);

    const shopwarePhpVersions = await loadShopwarePHPVersions();

    let matrix = versions
        .map((version) => {
            const template = getTemplate(version);

            const matrix = [];


            const supportedPhpVersions = findSupportedPhpVersion(shopwarePhpVersions, version);

            FLAVORS.forEach((flavor) => {
                supportedPhpVersions.forEach((phpVersion) => {
                    matrix.push({
                        "shopware-version": version,
                        "php-version": phpVersion,
                        "flavour": flavor,
                        "template": template,
                    })
                });
            });

            return matrix;
        })
        .concat(HARDCODED_MATRIX)
        .flat();

    console.log(JSON.stringify({
        include: matrix,
    }));
}

main(process.argv);