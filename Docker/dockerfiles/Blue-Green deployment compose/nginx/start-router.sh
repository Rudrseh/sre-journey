#!/bin/sh
set -e

ACTIVE_COLOR=${ACTIVE_COLOR:-blue}
FALLBACK_COLOR=${FALLBACK_COLOR:-green}
MAX_RETRIES=${MAX_RETRIES:-10}
SLEEP_SECONDS=${SLEEP_SECONDS:-2}

check_target() {
    color=$1
    wget -q --spider "http://${color}:80/health.html" || return 1
}

select_target() {
    if check_target "$ACTIVE_COLOR"; then
        echo "$ACTIVE_COLOR"
        return 0
    fi

    if check_target "$FALLBACK_COLOR"; then
        echo "$FALLBACK_COLOR"
        return 0
    fi

    return 1
}

for i in $(seq 1 "$MAX_RETRIES"); do
    if TARGET=$(select_target); then
        break
    fi
    echo "Waiting for ${ACTIVE_COLOR} or ${FALLBACK_COLOR} to become healthy..."
    sleep "$SLEEP_SECONDS"
done

if ! TARGET=$(select_target); then
    echo "Health check failed for ${ACTIVE_COLOR} and ${FALLBACK_COLOR}. Aborting startup."
    exit 1
fi

echo "Routing traffic to ${TARGET}"

cat > /etc/nginx/conf.d/default.conf <<EOF
upstream backend {
    server ${TARGET}:80;
}

server {
    listen 80;
    location / {
        proxy_pass http://backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF

nginx -g 'daemon off;'
