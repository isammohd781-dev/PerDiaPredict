#!/bin/bash
# Start the three PerdiaPredict apps and nginx in one container (Render or any Docker host).
set -eu
PORT="${PORT:-10000}"
DATA="${PERDIA_DATA_DIR:-/var/data}"
export PERDIA_DATA_DIR="$DATA"

# The persistent disk is mounted by the platform as root; give it to the app user.
mkdir -p "$DATA"
chown -R perdia:perdia "$DATA" 2>/dev/null || true

if [ -z "${PERDIA_ADMIN_PASSWORD:-}" ]; then
    echo "WARNING: PERDIA_ADMIN_PASSWORD is not set; the admin app stays locked." >&2
fi

sed "s/__PORT__/$PORT/" /app/deploy/nginx-render.conf > /tmp/nginx.conf

run_as_app() { env HOME=/home/perdia setpriv --reuid=perdia --regid=perdia --init-groups "$@"; }

cd /app
common="--server.address=127.0.0.1 --server.headless=true"
run_as_app streamlit run patient.py --server.port=8501 $common &
run_as_app streamlit run doctor.py  --server.port=8502 --server.baseUrlPath=doctor $common &
run_as_app streamlit run admin.py   --server.port=8503 --server.baseUrlPath=admin  $common &
run_as_app nginx -e /dev/stderr -c /tmp/nginx.conf -g 'daemon off;' &

# If any process stops, stop the container so the platform restarts it cleanly.
wait -n 2>/dev/null || wait
echo "A PerdiaPredict process stopped; exiting so the platform restarts the service." >&2
exit 1
