#!/usr/bin/env node

const FLAVOURS = [
    "alpine",
    "bullseye",
];

/**
 * Hardcode some versions, because e.g. there are no tags for them.
 */
const HARDCODED_MATRIX = [
    {
        "shopwareVersion": "6.4",
        "phpVersions": ["8.1", "8.2"],
    },
    {
        "shopwareVersion": "6.5.x",
        "phpVersions": ["8.1", "8.2", "8.3"],
    },
    {
        "shopwareVersion": "trunk",
        "phpVersions": ["8.2", "8.3"],
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
    try {
        const minor = parseMinorVersion(version);

        // For everything below 6.5, we need the shopware/production template.
        if (minor <= 4) {
            return "https://github.com/shopware/production";
        }
    } catch (e) {
        // Ignore
    }

    return "https://github.com/shopware/shopware";
}

function addMatrixEntries(matrix, shopwareVersion, phpVersion, isMain) {
    FLAVOURS.forEach((flavour) => {
        matrix.push({
            "shopware-version": shopwareVersion,
            "php-version": phpVersion,
            "flavour": flavour,
            "template": getTemplate(shopwareVersion),
            "is-main": isMain,
        });
    });
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

    if (Object.entries(shopwareMinorVersions).length === 0) {
        throw new Error("No shopwareMinorVersions entries generated.");
    }

    let matrix = [];

    for (const [_, entry] of  Object.entries(shopwareMinorVersions)) {
        const supportedPhpVersions = entry.phpVersions.filter((phpVersion) => phpVersion >= minPHPVersion);

        supportedPhpVersions.forEach((phpVersion, i) => {
            addMatrixEntries(matrix, 'v' + entry.shopwareVersion, phpVersion, i === supportedPhpVersions.length - 1);
        });
    }

    if (matrix.length === 0) {
        throw new Error("No matrix entries generated.");
    }

    HARDCODED_MATRIX.forEach((entry) => {
        const supportedPhpVersions = entry.phpVersions.filter((phpVersion) => phpVersion >= minPHPVersion);

        supportedPhpVersions.forEach((phpVersion, i) => {
            addMatrixEntries(matrix, entry.shopwareVersion, phpVersion, i === supportedPhpVersions.length - 1);
        });
    });

    console.log(JSON.stringify({
        include: matrix.flat(),
    }));
}

main();