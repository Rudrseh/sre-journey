#!/bin/sh
set -e

: "Starting ${APP_NAME:-Nginx Static Site} in ${APP_ENV:-development} mode"

if [ "$NGINX_PORT" != "80" ]; then
  echo "Using custom NGINX_PORT=${NGINX_PORT}"
fi

exec "$@"
