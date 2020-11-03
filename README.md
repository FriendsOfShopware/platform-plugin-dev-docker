# What is this?

A docker image with preinstalled Shopware 6, without a webserver, but including some helper tools. These images are meant to be useful for debugging Shopware plugins or running plugin tasks in CI with different Shopware versions.

# Available Docker image tags

We provide a tag for each [minor Shopware 6 release](https://www.shopware.com/en/news/shopware-6-versioning-strategy/), which should always point to the latest patch release, e.g:
```
v6.3.0
v6.3.1
v6.3.2
v6.3.3
```

# Available scripts and commands

Inside the Docker container you can use the following commands

## `plugin-uploader`

For more information see the [offical documentation](https://github.com/FriendsOfShopware/FroshPluginUploader#using-the-commands) of the plugin uploader.

## `start-mysql`

Simple script which will start the mysql server and return `0` if it was successfully started.

## `pack-plugin <plugin name>`

This command will install the plugin with `<plugin name>` and compile all JavaScript files needed for the storefront and the administration.
If the environment variable `SHOPWARE_ROOT` is set, this will be used as alternative Shopware location, otherwise if this variable is empty, the default Shopware setup from this image `/opt/hopware` will be used.

# Build Docker image for specific Shopware version

It is possible to specify the Shopware version or even the template with the Docker option `--build-arg`, e.g.:
```
docker build --build-arg SHOPWARE_VERSION=6.3 . -t platform-plugin-dev:6.3
```

In the same way it is also possible to specify the template Git repository URL:
```
docker build --build-arg SHOPWARE_VERSION=6.3 \
    --build-arg TEMPLATE_REPOSITORY='https://github.com/FriendsOfShopware/production' \
    . -t platform-plugin-dev:6.3
```


# Examples
## Pack Plugin in .gitlab-ci.yml
```
build:pack-plugin:
  image:
    name: ghcr.io/friendsofshopware/platform-plugin-dev:v6.3.1
    entrypoint: [""]
  script:
    - start-mysql
    - ln -s "$(pwd)" "/plugins/${CI_PROJECT_NAME}"
    - pack-plugin "${CI_PROJECT_NAME}"
    - plugin-uploader ext:validate "$(realpath "${CI_PROJECT_NAME}.zip")"
  artifacts:
    paths:
      - "${CI_PROJECT_NAME}.zip"
    expire_in: 1 week
```
