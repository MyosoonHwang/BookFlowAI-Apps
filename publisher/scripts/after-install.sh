#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/var/www/publisher"
NGINX_SITE="/etc/nginx/sites-available/bookflow-publisher"
NGINX_LINK="/etc/nginx/sites-enabled/bookflow-publisher"
LOG_FILE="/var/log/bookflow-publisher-deploy.log"

exec > >(tee -a "$LOG_FILE") 2>&1

if [ ! -d "$APP_DIR" ]; then
  echo "Missing application directory: $APP_DIR" >&2
  exit 1
fi

chown -R www-data:www-data "$APP_DIR"
find "$APP_DIR" -type d -exec chmod 0755 {} +
find "$APP_DIR" -type f -exec chmod 0644 {} +

cat > "$NGINX_SITE" <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    root /var/www/publisher;
    index index.html index.htm;

    access_log /var/log/nginx/bookflow-publisher-access.log;
    error_log /var/log/nginx/bookflow-publisher-error.log warn;

    location = /health {
        access_log off;
        add_header Content-Type text/plain;
        return 200 "ok\n";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINX

rm -f /etc/nginx/sites-enabled/default
ln -sfn "$NGINX_SITE" "$NGINX_LINK"

nginx -t
systemctl restart nginx

echo "AfterInstall completed at $(date -Is)"
