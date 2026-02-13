#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "[1/4] Pull latest code..."
git pull --ff-only

echo "[2/4] Rebuild and restart container..."
docker compose up -d --build

echo "[3/4] Container status..."
docker compose ps

echo "[4/4] Recent logs..."
docker compose logs --tail=80

echo "Done. Open: http://<NAS_IP>:5600"
