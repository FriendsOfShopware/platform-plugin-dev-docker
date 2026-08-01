ARG PHP_VERSION=8.1
FROM ghcr.io/friendsofshopware/platform-plugin-dev-base:${PHP_VERSION}-debian

ARG SHOPWARE_VERSION=dev-trunk

ENV SHOPWARE_BUILD_DIR=/opt/shopware

RUN \
  if echo "${SHOPWARE_VERSION}" | grep -q '^v6.4.*'; then \
      curl -fsSL https://deb.nodesource.com/setup_16.x | bash; \
  elif echo "${SHOPWARE_VERSION}" | grep -q '^v6.5.*'; then \
      curl -fsSL https://deb.nodesource.com/setup_18.x | bash; \
  elif echo "${SHOPWARE_VERSION}" | grep -q '^v6.6.*'; then \
      curl -fsSL https://deb.nodesource.com/setup_20.x | bash; \
  elif echo "${SHOPWARE_VERSION}" | grep -q '^v6.7.*'; then \
      curl -fsSL https://deb.nodesource.com/setup_22.x | bash; \
  else \
      curl -fsSL https://deb.nodesource.com/setup_current.x | bash; \
  fi; \
  apt-get install nodejs && \
  if echo "${SHOPWARE_VERSION}" | grep -q '^v6.5.*'; then \
    npm install -g npm@^9.0.0; \
  fi

# Playwright dropped Debian 11 (bullseye) support with 1.62, so the bullseye
# based images (PHP 8.1 / Shopware 6.5) stay on the last version supporting it.
RUN \
    node -v && \
    if grep -q '^11\.' /etc/debian_version; then \
        npx playwright@1.61.1 install --with-deps; \
    else \
        npx playwright install --with-deps; \
    fi

ARG TEMPLATE_REPOSITORY=https://github.com/shopware/shopware

RUN \
    start-mysql && \
    mysql -e "CREATE DATABASE shopware" && \
    mysqladmin --user=root password 'root' && \
    mkdir -p /opt/shopware && \
    git clone -b ${SHOPWARE_VERSION} --depth 1 "${TEMPLATE_REPOSITORY}" "${SHOPWARE_BUILD_DIR}" && \
    cd "${SHOPWARE_BUILD_DIR}" && \
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
