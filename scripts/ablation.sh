#!/usr/bin/env bash
# Runs a scenario with one module switched off, to measure each lever's contribution.
#   scripts/ablation.sh scenarios/public_01_dev.yaml schedule 8721
set -euo pipefail
cd "$(dirname "$0")/.."
SC="$1"; OFF="$2"; PORT="${3:-8720}"
NAME="$(basename "$SC" .yaml)"
ALL="incidents,did,experiments,schedule"
KEEP=$(echo "$ALL" | tr ',' '\n' | grep -vx "$OFF" | paste -sd,)
PY=.venv/bin/python
[ -d "runs/base_$NAME" ] || "$PY" -m sim baseline --scenario "$SC" --run-dir "runs/base_$NAME"
"$PY" -m sim serve --scenario "$SC" --run-dir "runs/abl_${NAME}_no_$OFF" --force --port "$PORT" > /dev/null 2>&1 &
SIM=$!
trap 'kill $SIM 2>/dev/null || true' EXIT
until curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; do sleep 0.5; done
DB="state/abl_${NAME}_no_$OFF.db"; rm -f "$DB" "$DB-wal" "$DB-shm"
CONTROLLER_MODULES="$KEEP" "$PY" -m controller run --url "http://127.0.0.1:$PORT" --db "$DB" 2> /dev/null
mkdir -p reports/ablation
"$PY" -m sim grade --run "runs/abl_${NAME}_no_$OFF" --baseline "runs/base_$NAME" --out "reports/ablation/${NAME}_no_$OFF.md" > /dev/null
