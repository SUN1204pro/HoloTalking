#!/usr/bin/env bash
# One command to bring up the whole HoloTalking stack on the Mac against the
# remote i86 backend. Opens 3 things and keeps them running until you Ctrl+C.
#
#   1. SSH tunnel to i86  (port 8000 -> localhost)
#   2. frontend dev server (http://localhost:5173)
#   3. holofan_autopush.py  (polls the API, uploads each new video to Holoscope)
#
# Usage:  ./start_holo_mac.sh
set -euo pipefail
cd "$(dirname "$0")"

SSH_HOST="${SSH_HOST:-i86-Server}"
PY="${PY:-python}"

cleanup() { echo; echo "stopping..."; kill $(jobs -p) 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "[1/3] SSH tunnel -> $SSH_HOST (8000)"
ssh -N \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes \
  -L 8000:localhost:8000 \
  "$SSH_HOST" &
SSH_PID=$!

# wait for the backend to answer through the tunnel
echo -n "      waiting for backend"
for i in $(seq 1 60); do
  if curl -s -m 2 http://localhost:8000/api/health >/dev/null 2>&1; then echo " ok"; break; fi
  echo -n "."; sleep 2
  if [ "$i" = 60 ]; then echo " TIMEOUT -- is 'python server_api.py' running on i86?"; exit 1; fi
done

echo "[2/3] frontend  -> http://localhost:5173"
( cd frontend && npm run dev -- --host >/tmp/holo_frontend.log 2>&1 ) &

echo "[3/3] holofan_autopush (polling the API)"
$PY holofan_autopush.py http://127.0.0.1:8000 &

echo
echo "All up. Open http://localhost:5173   (Ctrl+C to stop everything)"
wait
