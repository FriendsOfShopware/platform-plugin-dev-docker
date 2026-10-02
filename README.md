# What is this?

A docker image with preinstalled Shopware 6, without a webserver, but including some helper tools. These images are meant to be useful for debugging Shopware plugins or running plugin tasks in CI with different Shopware versions.

# Available Docker image tags

We provide a tag for each [minor Shopware 6 release](https://www.shopware.com/en/news/shopware-6-versioning-strategy/), which should always point to the latest patch release. Additionally there exist a tag for each major branch. A list of available tags can be found [here](https://github.com/FriendsOfShopware/platform-plugin-dev-docker/pkgs/container/platform-plugin-dev/versions?filters%5Bversion_type%5D=tagged).

# Available scripts and commands

Inside the Docker container you can use the following commands

## `plugin-uploader`

For more information see the [offical documentation](https://github.com/FriendsOfShopware/FroshPluginUploader#using-the-commands) of the plugin uploader.

## `start-mysql`

Simple script which will start the mysql server and return `0` if it was successfully started.

## `pack-plugin <plugin name>`

This command will install the plugin with `<plugin name>` and compile all JavaScript files needed for the storefront and the administration.
If the environment variable `SHOPWARE_ROOT` is set, this will be used as alternative Shopware location, otherwise if this variable is empty, the default Shopware setup from this image `/opt/shopware` will be used.

Make sure that the plugin folder is present in `${SHOPWARE_ROOT}/custom/plugins/`. If you use the default `SHOPWARE_ROOT` you can place them in `/plugins`.

## `pack-app <app name>`

This command will install the app with `<app name>` and compile all JavaScript files needed for the storefront.
If the environment variable `SHOPWARE_ROOT` is set, this will be used as alternative Shopware location, otherwise if this variable is empty, the default Shopware setup from this image `/opt/shopware` will be used.

Make sure that the app folder is present in `${SHOPWARE_ROOT}/custom/apps/`. If you use the default `SHOPWARE_ROOT` you can place them in `/apps`.

# Build Docker image for a specific Shopware version

The hand-maintained [Alpine profiles](alpine/build-profiles.toml) and [Debian profiles](debian/build-profiles.toml) declare the PHP version, distribution, Node.js and npm policies, Playwright policy and whether the base is frozen. CI and local builds read these same files. The workflow selects a profile and lists the Shopware releases to build with it.

Local builds require Python 3.11 or later and Docker with Buildx. For example:

```sh
python3 scripts/build.py build \
    --flavour debian --profile shopware-6.5 \
    --shopware-version v6.5.0.0 \
    --tag platform-plugin-dev:6.5-debian
```

To build from another template repository, add `--template https://github.com/FriendsOfShopware/platform`. Use `--dry-run` to resolve the upstream versions and print the Docker command without building. `--force-refresh` invalidates mutable dependency layers immediately.

Profiles are named `shopware-6.5`, `shopware-6.6`, `shopware-6.7` and `trunk`. Their version policies mean:

- A Node.js major such as `"18"` selects the latest available NodeSource package for that major; `"current"` selects the current Node.js major.
- `"distribution"` selects Node.js or npm from the profile's Alpine repositories.
- An npm major such as `"9"` selects its latest stable release; `"bundled"` keeps the npm included with Node.js.
- Playwright accepts an exact version or `"latest"`. Omitting it disables its installation, as in the Alpine profiles.
- `frozen-base = true` reuses the published base and excludes it from CI base builds.

A new PHP version or distribution is configured in these files. The resolver reads the profile and passes exact package versions, a pinned base digest and the Shopware commit as Docker build arguments.

# Nightly builds and dependency updates

Nightly builds resolve each Shopware branch or tag to a commit, pin the published PHP base by digest, and check the available Node.js, npm and Playwright versions. Builds on `main` reuse published images when their input fingerprint matches. A changed upstream commit, runtime version, base digest or Dockerfile triggers a rebuild.

The `runtime` stage installs Node.js, npm and, on Debian, Playwright. CI builds it once per PHP, distribution and Node.js variant, then shares it across the Shopware versions. Published runtimes use `runtime-*` tags in the `platform-plugin-dev-base` repository. Branch builds use the same stage through the shared GitHub Actions cache and keep the existing rules for publishing images.

Mutable APT/APK dependencies, downloaded tools and Composer dependencies without a usable lock file refresh weekly, at the start of each UTC ISO week. To refresh sooner, run the **Build Docker images** workflow manually with **force-refresh** enabled. PHP 8.1 bases remain frozen, and Debian Bullseye uses the archived package snapshot configured in its Dockerfile.

The workflow stores resolved inputs in its `build-plan` and `runtime-*` artifacts. Runtime image labels record the dependency versions and refresh period; final image labels record the Shopware commit and input fingerprint. Runtime caches retain intermediate layers, while each Shopware cache retains its final layers.

To build only the shared runtime locally:

```sh
python3 scripts/build.py build \
    --flavour debian --profile shopware-6.6 \
    --target runtime --tag platform-plugin-dev:runtime-6.6-debian
```

Use `--target base` for a profile whose base is not frozen. It builds the base locally; runtime and Shopware builds continue to resolve the published base used by CI. Direct Docker builds also remain possible when supplying the required build arguments explicitly.

# Examples
## Pack Plugin in .gitlab-ci.yml
```yaml
build:pack-plugin:
  image:
    name: ghcr.io/friendsofshopware/platform-plugin-dev:v6.5.0
    entrypoint: [""]
  script:
    - ln -s "$(pwd)" "/plugins/${CI_PROJECT_NAME}"
    - pack-plugin "${CI_PROJECT_NAME}"
    - plugin-uploader ext:validate "$(realpath "${CI_PROJECT_NAME}.zip")"
  artifacts:
    paths:
      - "${CI_PROJECT_NAME}.zip"
    expire_in: 1 week
```

## Pack App in .gitlab-ci.yml
```yaml
build:pack-app:
  image:
    name: ghcr.io/friendsofshopware/platform-plugin-dev:v6.5.0
    entrypoint: [""]
  script:
    - start-mysql
    - ln -s "$(pwd)" "/apps/${CI_PROJECT_NAME}"
    - rm -rf "/apps/${CI_PROJECT_NAME}/store" # Remove the store folder manually since it is not removed in the pack process for apps
    - pack-app "${CI_PROJECT_NAME}"
    - plugin-uploader ext:validate "$(realpath "${CI_PROJECT_NAME}.zip")" || true
  artifacts:
    paths:
      - "${CI_PROJECT_NAME}.zip"
    expire_in: 1 week
```

## PHPUnit tests
The docker images contains `phpunit` constrained via the Shopware `composer.json`. Additionally a `TestBootstrapper` is included, either the one from the Shopware repository or a fallback one for Shopware versions `< 6.4.5.0`. This can be utilized inside your plugin (e.g. in `tests/TestBootstrap.php`)
```php
<?php declare(strict_types=1);

use Shopware\Core\TestBootstrapper;

$testBootstrapper = null;
if (is_readable('/opt/share/shopware/tests/TestBootstrapper.php')) {
    // For Docker image: ghcr.io/friendsofshopware/platform-plugin-dev
    $testBootstrapper = require '/opt/share/shopware/tests/TestBootstrapper.php';
} else {
    // Create your own TestBootstrapper
}

return $testBootstrapper
    ->setLoadEnvFile(true)
    ->setForceInstallPlugins(true)
    ->addActivePlugins('MyTechnicalPluginName')
    ->bootstrap()
    ->getClassLoader()
;
```

The associate `phpunit.xml.dist` would than look something like
```xml
<?xml version="1.0" encoding="UTF-8"?>
<phpunit xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:noNamespaceSchemaLocation="https://schema.phpunit.de/9.3/phpunit.xsd"
         backupGlobals="false"
         colors="true"
         bootstrap="tests/TestBootstrap.php"
         cacheResult="false">
    <coverage processUncoveredFiles="true">
        <include>
            <directory suffix=".php">src</directory>
        </include>
    </coverage>
    <php>
        <ini name="error_reporting" value="-1"/>
        <server name="APP_ENV" value="test" force="true"/>
        <env name="APP_DEBUG" value="1"/>
        <env name="APP_SECRET" value="s$cretf0rt3st"/>
        <env name="SHELL_VERBOSITY" value="-1"/>
        <env name="SYMFONY_DEPRECATIONS_HELPER" value="disabled" />
    </php>
    <testsuites>
        <testsuite name="MyTechnicalPluginName">
            <directory>tests</directory>
        </testsuite>
    </testsuites>
</phpunit>
```

Locally execute the tests using the provided docker images, assuming you are currently inside the plugin directory
```
docker run --rm -it -v "${PWD}:/plugins/MyTechnicalPluginName" ghcr.io/friendsofshopware/platform-plugin-dev:v6.4.0 sh -c 'start-mysql && cd /plugins/MyTechnicalPluginName && phpunit'
```

## Run the tests in .gitlab-ci.yml
```yaml
test:phpunit:
  stage: test
  image:
    name: ghcr.io/friendsofshopware/platform-plugin-dev:${SHOPWARE_VERSION}
    entrypoint: [""]
  script:
    - start-mysql
    - ln -s "$(pwd)" "/plugins/${CI_PROJECT_NAME}"
    - phpunit
  parallel:
    matrix:
      - SHOPWARE_VERSION: ['v6.4.0', 'v6.4.5', 'v6.4.10', 'v6.4.15']
```
