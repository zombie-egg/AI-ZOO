FROM node:20-alpine AS kiosk-builder

WORKDIR /build/kiosk
COPY kiosk/package*.json ./
RUN npm ci
COPY kiosk/ ./
RUN npm run build

FROM php:8.2-fpm-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        default-mysql-client \
        gettext-base \
        git \
        libfreetype6-dev \
        libgl1 \
        libglib2.0-0 \
        libjpeg62-turbo-dev \
        libpng-dev \
        libzip-dev \
        nginx \
        python3 \
        python3-pip \
        python3-venv \
        supervisor \
        unzip \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j"$(nproc)" bcmath gd pcntl pdo_mysql zip \
    && pecl install redis \
    && docker-php-ext-enable redis \
    && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

WORKDIR /var/www/html
COPY server/composer.json server/composer.lock ./
RUN composer install --no-dev --no-interaction --prefer-dist --optimize-autoloader --no-scripts
COPY server/ ./
RUN composer dump-autoload --no-dev --optimize --no-interaction \
    && mkdir -p runtime \
    && chown -R www-data:www-data runtime

WORKDIR /opt/imageforge
COPY imageforge/pyproject.toml ./
COPY imageforge/app ./app
RUN python3 -m venv /opt/imageforge/.venv \
    && /opt/imageforge/.venv/bin/pip install .
COPY imageforge/ ./

COPY --from=kiosk-builder /build/kiosk/dist/ /var/www/kiosk/
COPY deploy/nginx.conf.template /etc/nginx/templates/ai-zoo.conf.template
COPY deploy/supervisord.conf /etc/supervisor/conf.d/ai-zoo.conf
COPY deploy/start-cloud.sh /usr/local/bin/start-ai-zoo
RUN chmod 0755 /usr/local/bin/start-ai-zoo \
    && rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf

VOLUME ["/data/imageforge", "/var/www/html/runtime"]
EXPOSE 8080

CMD ["/usr/local/bin/start-ai-zoo"]
