ARG PHP_VERSION=8.1
FROM ghcr.io/friendsofshopware/platform-plugin-dev-base:${PHP_VERSION}-alpine

ARG SHOPWARE_VERSION=dev-trunk

ENV SHOPWARE_BUILD_DIR /opt/shopware

RUN \
  if echo "${SHOPWARE_VERSION}" | grep -q '^v6.4.*'; then \
      apk add --no-cache --repository="https://dl-cdn.alpinelinux.org/alpine/v3.16/main" 'nodejs=16.20.2-r0' 'npm=8.10.0-r0'; \
  elif echo "${SHOPWARE_VERSION}" | grep -q '^v6.6.*'; then \
      apk add --no-cache --repository="https://dl-cdn.alpinelinux.org/alpine/v3.19/main" 'nodejs=20.11.1-r0' 'npm=10.2.5-r0'; \
  else \
      apk add --no-cache npm; \
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
        composer install --no-interaction -o && \
        APP_URL="http://localhost" php bin/console system:setup --database-url=mysql://root:root@localhost:3306/shopware --generate-jwt-keys -nq && \
        php bin/console system:install -fnq --create-database && \
        composer clearcache && \
        rm -Rf .git && \
        rm -rf "${SHOPWARE_BUILD_DIR}/custom/plugins" && \
        mkdir -p /plugins && ln -s /plugins "${SHOPWARE_BUILD_DIR}/custom/plugins" && \
        rm -rf "${SHOPWARE_BUILD_DIR}/custom/apps" && \
        mkdir -p /apps && ln -s /apps "${SHOPWARE_BUILD_DIR}/custom/apps"

VOLUME /plugins
WORKDIR /opt/shopware
