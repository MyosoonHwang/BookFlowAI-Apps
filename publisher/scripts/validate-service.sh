#!/usr/bin/env bash
set -Eeuo pipefail

URL="http://127.0.0.1/health"
LOG_FILE="/var/log/bookflow-publisher-deploy.log"

exec > >(tee -a "$LOG_FILE") 2>&1

for attempt in $(seq 1 30); do
  if curl -fsS --max-time 2 "$URL" | grep -qx "ok"; then
    echo "ValidateService passed at $(date -Is)"
    exit 0
  fi
  echo "Health check attempt $attempt failed"
  sleep 2
done

systemctl status nginx --no-pager || true
journalctl -u nginx -n 80 --no-pager || true
exit 1
