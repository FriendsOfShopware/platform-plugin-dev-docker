#!/usr/bin/env node

const FLAVORS = [
    "alpine",
    "bullseye",
];

/**
 * @todo: load from https://github.com/FriendsOfShopware/shopware-static-data/pull/1
 */
const PHP_VERSIONS = [
    "8.0",
    "8.1",
    "8.2",
];

const getTemplate = (version) => {
    const parts = version.match(/v[0.9]*.\.([0-9]*)\..*/);
    if (parts.length < 2) {
        throw new Error("Unexpected version format: " + version);
    }

    const minor = parts[1];
    if (parseInt(minor) <= 4) {
        return "https://github.com/shopware/production";
    }

    return "https://github.com/shopware/platform";
}

async function main() {
    const response = await fetch("https://api.github.com/repos/shopware/platform/git/refs/tags")
    const tags = await response.json();

    const versions = tags.map((tag) => {
        const version = tag.ref.replace("refs/tags/", "");
        const parts = version.match(/v[0.9]*.\.([0-9]*)\..*/);
        if (parts.length < 2) {
            return;
        }

        const minor = parts[1];
        // skip 
        if (parseInt(minor) <= 3) {
            return;
        }

        return version;
    }).filter(version => !!version);

    let matrix = versions.map((version) => {
        const template = getTemplate(version);

        const matrix = [];

        for (let flavor in FLAVORS) {
            for (let phpVersion in PHP_VERSIONS) {
                matrix.push({
                    "shopware-version": version,
                    "php-version": phpVersion,
                    "flavour": flavor,
                    "template": template,
                })
            }
        }

        return matrix;
    })

    console.log(JSON.stringify({
        include: matrix,
    }));
}

main();