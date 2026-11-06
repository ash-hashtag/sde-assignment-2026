#!/usr/bin/env bash
# Runs one scenario end to end: baseline (if missing), simulator, controller, grade.
#   scripts/run_scenario.sh scenarios/public_01_dev.yaml [port]
set -euo pipefail
cd "$(dirname "$0")/.."
SC="$1"; PORT="${2:-8700}"
NAME="$(basename "$SC" .yaml)"
PY="${PYTHON:-.venv/bin/python}"
[ -d "runs/base_$NAME" ] || "$PY" -m sim baseline --scenario "$SC" --run-dir "runs/base_$NAME"
"$PY" -m sim serve --scenario "$SC" --run-dir "runs/mine_$NAME" --force --port "$PORT" > "runs/sim_$NAME.log" 2>&1 &
SIM=$!
trap 'kill $SIM 2>/dev/null || true' EXIT
until curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; do sleep 0.5; done
mkdir -p state
rm -f "state/$NAME.db" "state/$NAME.db-wal" "state/$NAME.db-shm"
CONTROLLER_DB="state/$NAME.db" ./run.sh "http://127.0.0.1:$PORT" 2> "runs/controller_$NAME.log"
mkdir -p reports
"$PY" -m sim grade --run "runs/mine_$NAME" --baseline "runs/base_$NAME" --out "reports/$NAME.md" > /dev/null
echo "graded -> reports/$NAME.md"
