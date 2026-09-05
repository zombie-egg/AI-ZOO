FROM m.daocloud.io/docker.io/library/php:8.0-fpm-bullseye

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        libfreetype6-dev \
        libjpeg62-turbo-dev \
        libpng-dev \
        libzip-dev \
        unzip \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j"$(nproc)" bcmath gd pcntl pdo_mysql zip \
    && curl --fail --silent --show-error --location https://pecl.php.net/get/redis-5.3.7.tgz --output /tmp/redis.tgz \
    && pecl install /tmp/redis.tgz \
    && docker-php-ext-enable redis \
    && rm -rf /var/lib/apt/lists/*

COPY --from=m.daocloud.io/docker.io/library/composer:2 /usr/bin/composer /usr/local/bin/composer

WORKDIR /var/www/html
