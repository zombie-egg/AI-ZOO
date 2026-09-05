#!/bin/sh
set -eu

: "${MYSQL_HOST:?MYSQL_HOST is required}"
: "${MYSQL_DATABASE:?MYSQL_DATABASE is required}"
: "${MYSQL_USERNAME:?MYSQL_USERNAME is required}"
: "${MYSQL_PASSWORD:?MYSQL_PASSWORD is required}"
: "${REDIS_HOST:?REDIS_HOST is required}"
: "${IMAGEFORGE_SECRET:?IMAGEFORGE_SECRET is required}"
: "${IMAGEFORGE_SECRET_KEY:?IMAGEFORGE_SECRET_KEY is required}"
: "${IMAGEFORGE_INTERNAL_TOKEN:?IMAGEFORGE_INTERNAL_TOKEN is required}"
: "${KIOSK_DEVICE_PROXY_TOKEN:?KIOSK_DEVICE_PROXY_TOKEN is required}"

MYSQL_PORT="${MYSQL_PORT:-3306}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"
export MYSQL_PWD="$MYSQL_PASSWORD"

cat > /var/www/html/.env <<EOF
APP_DEBUG = false
ZONE = domestic

[APP]
DEFAULT_TIMEZONE = Asia/Shanghai

[DATABASE]
TYPE = mysql
HOSTNAME = ${MYSQL_HOST}
DATABASE = ${MYSQL_DATABASE}
USERNAME = ${MYSQL_USERNAME}
PASSWORD = ${MYSQL_PASSWORD}
HOSTPORT = ${MYSQL_PORT}
CHARSET = utf8mb4
DEBUG = false
PREFIX = ai_

[REDIS]
HOST = ${REDIS_HOST}
PORT = ${REDIS_PORT}
PASSWORD = ${REDIS_PASSWORD}
SELECT = 0

[CACHE]
driver = redis

[LANG]
default_lang = zh-cn

[PROJECT]
UNIQUE_IDENTIFICATION = ai-zoo
DEMO_ENV = false

[PHASE1]
OFFLINE_ACCEPTANCE = false

[LUNA]
BASE_URL = http://127.0.0.1:8000
OSS_BASE_URL = ${PUBLIC_BASE_URL:-http://127.0.0.1:${PORT}}
PHASE1_STUB_ENABLED = false
SECRET = ${IMAGEFORGE_SECRET}
SECRET_KEY = ${IMAGEFORGE_SECRET_KEY}

[IMAGEFORGE]
BASE_URL = http://127.0.0.1:8000
INTERNAL_TOKEN = ${IMAGEFORGE_INTERNAL_TOKEN}

[KIOSK]
DEVICE_PROXY_TOKEN = ${KIOSK_DEVICE_PROXY_TOKEN}
PHOTO_TTL_DAYS = 7
OPERATOR_TEST_MODE = false
EOF
chmod 0600 /var/www/html/.env
chown www-data:www-data /var/www/html/.env

export LUNA_UPSTREAM=imageforge
export LUNA_BASE_URL=http://127.0.0.1:8000
export LUNA_PHASE1_STUB_ENABLED=false
export DATABASE_PATH="${DATABASE_PATH:-/data/imageforge/imageforge.db}"
export PRIVATE_DIR="${PRIVATE_DIR:-/data/imageforge/private}"
mkdir -p "$(dirname "$DATABASE_PATH")" "$PRIVATE_DIR" /var/www/html/runtime
chown -R www-data:www-data /var/www/html/runtime

until mysqladmin ping -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USERNAME" --silent; do
  sleep 2
done

TABLE_COUNT="$(mysql -N -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USERNAME" "$MYSQL_DATABASE" -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='ai_config';")"
if [ "$TABLE_COUNT" = "0" ]; then
  mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USERNAME" "$MYSQL_DATABASE" < /var/www/html/database/loxi_luna.sql
fi
for migration in phase3_kiosk.sql phase4_direct_generation.sql phase5_pose_selection.sql phase6_multi_participant.sql; do
  mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USERNAME" "$MYSQL_DATABASE" < "/var/www/html/database/$migration"
done

envsubst '${PORT} ${KIOSK_DEVICE_PROXY_TOKEN}' < /etc/nginx/templates/ai-zoo.conf.template > /etc/nginx/conf.d/ai-zoo.conf
exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
