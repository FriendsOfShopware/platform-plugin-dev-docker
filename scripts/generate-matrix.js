#!/usr/bin/env node

const FLAVORS = [
    "alpine",
    "bullseye",
];

/**
 * @todo change url when https://github.com/FriendsOfShopware/shopware-static-data/pull/1 is merged.
 */
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

async function main() {
    const response = await fetch("https://api.github.com/repos/shopware/platform/git/refs/tags")
    const tags = await response.json();

    const versions = tags.map((tag) => {
        const version = tag.ref.replace("refs/tags/", "");
        const minor = parseMinorVersion(version);
        
        // We only want to support versions >= 6.3 to reduce build time
        if (parseInt(minor) <= 3) {
            return;
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
        .flat();

    console.log(JSON.stringify({
        include: matrix,
    }));
}

main();