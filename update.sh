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

PORT_MAP=$(docker compose ps --format json 2>/dev/null | python3 - <<'PY'
import sys, json
raw=sys.stdin.read().strip()
if not raw:
    print("8080")
    raise SystemExit
try:
    lines=[json.loads(x) for x in raw.splitlines() if x.strip()]
    ports=(lines[0].get('Publishers') or []) if lines else []
    if ports and ports[0].get('PublishedPort'):
        print(ports[0]['PublishedPort'])
    else:
        print('8080')
except Exception:
    print('8080')
PY
)

echo "Done. Open: http://<NAS_IP>:${PORT_MAP}"
