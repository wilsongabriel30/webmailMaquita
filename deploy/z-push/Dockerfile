FROM php:8.3-fpm-bookworm

# Install php-imap and required extensions
RUN apt-get update && apt-get install -y     libc-client-dev     libkrb5-dev     libxml2-dev     libzip-dev     libcurl4-openssl-dev     libicu-dev libonig-dev media-types libxslt1-dev     && docker-php-ext-configure imap --with-kerberos --with-imap-ssl     && docker-php-ext-install imap soap intl zip curl mbstring xsl sysvshm sysvsem     && apt-get clean && rm -rf /var/lib/apt/lists/*

# Clone Z-Push
RUN apt-get update && apt-get install -y git     && git clone --depth 1 https://github.com/Z-Hub/Z-Push.git /opt/z-push     && apt-get remove -y git && apt-get autoremove -y     && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install AWL library (required for CalDAV/CardDAV backends)
RUN apt-get update && apt-get install -y libawl-php     && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create state and log directories
RUN mkdir -p /var/lib/z-push /var/log/z-push     && chown -R www-data:www-data /var/lib/z-push /var/log/z-push /opt/z-push

# PHP config
RUN echo "max_execution_time=3600" >> /usr/local/etc/php/conf.d/zpush.ini     && echo "memory_limit=256M" >> /usr/local/etc/php/conf.d/zpush.ini     && echo "post_max_size=50M" >> /usr/local/etc/php/conf.d/zpush.ini     && echo "upload_max_filesize=50M" >> /usr/local/etc/php/conf.d/zpush.ini     && echo "expose_php=Off" >> /usr/local/etc/php/conf.d/zpush.ini     && echo "display_errors=Off" >> /usr/local/etc/php/conf.d/zpush.ini     && echo "date.timezone=America/Guayaquil" >> /usr/local/etc/php/conf.d/zpush.ini

# PHP-FPM config - listen on all interfaces
RUN sed -i 's/listen = 127.0.0.1:9000/listen = 0.0.0.0:9000/' /usr/local/etc/php-fpm.d/www.conf

EXPOSE 9000
WORKDIR /opt/z-push/src
CMD ["php-fpm"]
