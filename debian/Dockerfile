ARG PHP_VERSION=8.1
FROM ghcr.io/friendsofshopware/platform-plugin-dev-base:${PHP_VERSION}-debian

ARG SHOPWARE_VERSION=dev-trunk
ARG TEMPLATE_REPOSITORY=https://github.com/shopware/production

ENV SHOPWARE_BUILD_DIR /opt/shopware

RUN \
  if echo "${SHOPWARE_VERSION}" | grep -q '^v6.4.*'; then \
      curl -fsSL https://deb.nodesource.com/setup_16.x | bash; \
  elif echo "${SHOPWARE_VERSION}" | grep -q '^v6.5.*'; then \
      curl -fsSL https://deb.nodesource.com/setup_18.x | bash; \
  else \
      curl -fsSL https://deb.nodesource.com/setup_current.x | bash; \
  fi; \
  apt-get install nodejs

RUN \
    node -v && \
    npx playwright install --with-deps

RUN \
    start-mysql && \
    mysql -e "CREATE DATABASE shopware" && \
    mysqladmin --user=root password 'root' && \
    mkdir -p /opt/shopware && \
    git clone -b ${SHOPWARE_VERSION} --depth 1 "${TEMPLATE_REPOSITORY}" "${SHOPWARE_BUILD_DIR}" && \
    cd "${SHOPWARE_BUILD_DIR}" && \
        mkdir -p custom && \
        composer install --no-interaction -o && \
        APP_URL="http://localhost" php bin/console system:setup --database-url=mysql://root:root@localhost:3306/shopware --generate-jwt-keys -nq && \
        php bin/console system:install -fnq --create-database && \
        composer clearcache && \
        rm -rf "${SHOPWARE_BUILD_DIR}/custom/plugins" && \
        mkdir -p /plugins && ln -s /plugins "${SHOPWARE_BUILD_DIR}/custom/plugins" && \
        rm -rf "${SHOPWARE_BUILD_DIR}/custom/apps" && \
        mkdir -p /apps && ln -s /apps "${SHOPWARE_BUILD_DIR}/custom/apps"

VOLUME /plugins
WORKDIR /opt/shopware
