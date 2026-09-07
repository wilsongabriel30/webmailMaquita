# Z-Push (ActiveSync) para Maquita Mail — componente de primera clase (D-9 corregida, 07/09/2026).
# Base oficial en su etiqueta actual y paquetes del sistema al día en cada build; se reconstruye
# cada mes (OPERACION.md). No se migra a Alpine ni a PHP «rc». El crítico de zlib/minizip
# (CVE-2023-45853, sin corrección en Debian, minizip no se usa) está aceptado con motivo (D-9).
FROM php:8.3-fpm-bookworm

ARG ZPUSH_VERSION=2.7.6
# Dimensionado: cada dispositivo en Ping ocupa un worker de PHP-FPM (~25-30 MB) mientras espera.
# 200 workers cubren ~200 dispositivos simultáneos en Ping (≈ 5-6 GB en el peor caso); para ~300
# dispositivos, PHP_MAX_CHILDREN=320 exige ~9 GB libres o un anfitrión aparte. Ver OPERACION.md.
ARG PHP_MAX_CHILDREN=200

# Extensiones que Z-Push necesita (imap, soap, intl, zip, curl, mbstring, xsl, sysv*)
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
        libc-client-dev libkrb5-dev libxml2-dev libzip-dev libcurl4-openssl-dev \
        libicu-dev libonig-dev media-types libxslt1-dev libawl-php ca-certificates \
    && docker-php-ext-configure imap --with-kerberos --with-imap-ssl \
    && docker-php-ext-install imap soap intl zip curl mbstring xsl sysvshm sysvsem \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Z-Push en una VERSIÓN fija (la última con soporte al escribir esto), no en master.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && git clone --depth 1 --branch "${ZPUSH_VERSION}" https://github.com/Z-Hub/Z-Push.git /opt/z-push \
    && rm -rf /opt/z-push/.git \
    && apt-get purge -y git && apt-get autoremove -y --purge \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Estado y registros (se montan desde el anfitrión) y propietario
RUN mkdir -p /var/lib/z-push /var/log/z-push \
    && chown -R www-data:www-data /var/lib/z-push /var/log/z-push /opt/z-push

# PHP: tiempos largos (Ping/Sync de ActiveSync), sin exponer versión ni errores
RUN { echo "max_execution_time=3600"; echo "memory_limit=128M"; echo "post_max_size=50M"; \
      echo "upload_max_filesize=50M"; echo "expose_php=Off"; echo "display_errors=Off"; \
      echo "log_errors=On"; echo "error_log=/var/log/z-push/php-error.log"; \
      echo "date.timezone=America/Guayaquil"; } > /usr/local/etc/php/conf.d/zpush.ini \
    && sed -i 's/^listen = .*/listen = 0.0.0.0:9000/' /usr/local/etc/php-fpm.d/www.conf \
    && sed -i "s/^;\?pm.max_children = .*/pm.max_children = ${PHP_MAX_CHILDREN}/" /usr/local/etc/php-fpm.d/www.conf \
    && sed -i 's/^;\?pm.start_servers = .*/pm.start_servers = 10/; s/^;\?pm.min_spare_servers = .*/pm.min_spare_servers = 5/; s/^;\?pm.max_spare_servers = .*/pm.max_spare_servers = 30/; s/^;\?pm.max_requests = .*/pm.max_requests = 500/' /usr/local/etc/php-fpm.d/www.conf \
    && sed -i 's/^;\?request_terminate_timeout = .*/request_terminate_timeout = 3600/' /usr/local/etc/php-fpm.d/www.conf

# Herramientas de diagnóstico de Z-Push a mano: z-push-admin y z-push-top
RUN printf '#!/bin/sh\nexec php /opt/z-push/src/z-push-admin.php "$@"\n' > /usr/local/bin/z-push-admin \
    && printf '#!/bin/sh\nexec php /opt/z-push/src/z-push-top.php "$@"\n' > /usr/local/bin/z-push-top \
    && chmod 755 /usr/local/bin/z-push-admin /usr/local/bin/z-push-top

EXPOSE 9000
WORKDIR /opt/z-push/src
CMD ["php-fpm"]
