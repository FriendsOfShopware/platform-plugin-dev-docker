# syntax=docker/dockerfile:1
# The profile resolver supplies the published base image.
ARG BASE_IMAGE=scratch
FROM ${BASE_IMAGE} AS runtime

ENV SHOPWARE_BUILD_DIR=/opt/shopware

ARG DISTRIBUTION_VERSION
ARG NODE_VERSION
ARG NPM_VERSION
ARG DEPENDENCY_REFRESH
RUN apk add --no-cache \
    --repository="https://dl-cdn.alpinelinux.org/alpine/v${DISTRIBUTION_VERSION}/main" \
    --repository="https://dl-cdn.alpinelinux.org/alpine/v${DISTRIBUTION_VERSION}/community" \
    "nodejs${NODE_VERSION:+=$NODE_VERSION}" "npm${NPM_VERSION:+=$NPM_VERSION}"

FROM runtime AS shopware

ARG SHOPWARE_VERSION=dev-trunk
ARG SHOPWARE_SHA
ARG DEPENDENCY_REFRESH
ARG TEMPLATE_REPOSITORY=https://github.com/shopware/shopware

RUN \
    start-mysql && \
    mysql -e "CREATE DATABASE shopware" && \
    mysqladmin --user=root password 'root' && \
    mkdir -p /opt/shopware && \
    git clone -b ${SHOPWARE_VERSION} --depth 1 "${TEMPLATE_REPOSITORY}" "${SHOPWARE_BUILD_DIR}" && \
    cd "${SHOPWARE_BUILD_DIR}" && \
        if [ -n "${SHOPWARE_SHA}" ]; then \
            git fetch --depth 1 origin "${SHOPWARE_SHA}" && \
            git checkout --detach FETCH_HEAD; \
        fi && \
        mkdir -p custom && \
        if [ -f composer.lock ] && grep -q 'maltyxx/images-generator' composer.lock; then \
            rm -f composer.lock; \
        fi && \
        if [ -f composer.lock ]; then \
            composer install --no-interaction -o; \
        else \
            jq '.replace["maltyxx/images-generator"] = "*"' composer.json > composer.tmp.json && mv composer.tmp.json composer.json && \
            if echo "${SHOPWARE_VERSION}" | grep -qE '^v6\.6\.10\.'; then \
              jq '.conflict = (.conflict // {}) + { "squirrelphp/twig-php-syntax": "<1.11.0" }' composer.json > composer.tmp.json && mv composer.tmp.json composer.json; \
            elif echo "${SHOPWARE_VERSION}" | grep -qE '^(trunk|v6\.7\.)'; then \
              jq '.conflict["symfony/type-info"] = "<7.1.8"' composer.json > composer.tmp.json && mv composer.tmp.json composer.json; \
            fi && \
            composer update --prefer-lowest --prefer-stable --no-interaction -o; \
        fi && \
        if echo "${SHOPWARE_VERSION}" | grep -qE '^(trunk|v6\.7\.)'; then \
            APP_URL="http://localhost" php bin/console system:setup --database-url=mysql://root:root@localhost:3306/shopware -nq; \
        else \
            APP_URL="http://localhost" php bin/console system:setup --database-url=mysql://root:root@localhost:3306/shopware --generate-jwt-keys -nq; \
        fi && \
        php bin/console system:install -fnq --create-database && \
        composer clearcache && \
        rm -Rf .git && \
        rm -rf "${SHOPWARE_BUILD_DIR}/custom/plugins" && \
        mkdir -p /plugins && ln -s /plugins "${SHOPWARE_BUILD_DIR}/custom/plugins" && \
        rm -rf "${SHOPWARE_BUILD_DIR}/custom/apps" && \
        mkdir -p /apps && ln -s /apps "${SHOPWARE_BUILD_DIR}/custom/apps"

VOLUME /plugins
WORKDIR /opt/shopware
