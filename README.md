# What is this?

A docker image with preinstalled Shopware 6, without a webserver, but including some helper tools. These images are meant to be useful for debugging Shopware plugins or running plugin tasks in CI

# Examples
## Pack Plugin in .gitlab-ci.yml
```
build:pack-plugin:
  image:
    name: aragon999/shopware-plugin-dev:6.3
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
