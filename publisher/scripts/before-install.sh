#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/var/www/publisher"
BACKUP_DIR="/var/www/publisher.previous"
LOG_FILE="/var/log/bookflow-publisher-deploy.log"

exec > >(tee -a "$LOG_FILE") 2>&1

export DEBIAN_FRONTEND=noninteractive

if ! command -v nginx >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y --no-install-recommends nginx ca-certificates curl
fi

systemctl enable nginx

rm -rf "$BACKUP_DIR"
if [ -d "$APP_DIR" ]; then
  cp -a "$APP_DIR" "$BACKUP_DIR"
fi

install -d -m 0755 "$APP_DIR"
find "$APP_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

echo "BeforeInstall completed at $(date -Is)"
