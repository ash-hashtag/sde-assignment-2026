#!/usr/bin/env bash
# Crash-recovery test: SIGKILL the controller at random moments, restart it, and check the run finishes correctly.
#   scripts/crash_test.sh [scenario] [kills] [port]
# Writes reports/crash_test.log. Verification reads the simulator's run dir, which only this test harness does —
# the controller itself never reads it.
set -euo pipefail
cd "$(dirname "$0")/.."
SC="${1:-scenarios/public_02_incidents.yaml}"; KILLS="${2:-6}"; PORT="${3:-8790}"
NAME="crash_$(basename "$SC" .yaml)"
PY=.venv/bin/python
DB="state/$NAME.db"
LOG=reports/crash_test.log
mkdir -p reports state
rm -f "$DB" "$DB-wal" "$DB-shm"
"$PY" -m sim serve --scenario "$SC" --run-dir "runs/$NAME" --force --port "$PORT" > "runs/sim_$NAME.log" 2>&1 &
SIM=$!
trap 'kill $SIM 2>/dev/null || true' EXIT
until curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; do sleep 0.5; done
{
echo "# crash test $(date -Is): $SC, injected crash points then $KILLS random SIGKILLs"
# 1. deterministic crash points: die right after side effects the store hasn't recorded yet
for CP in mid_ingest:40 after_auto_put:1 before_approval_post:1 after_approval_post:2 after_apply_post:1 \
          after_auto_put:3 after_approval_post:3 after_apply_post:2; do
  set +e
  CONTROLLER_CRASHPOINTS="$CP" "$PY" -m controller run --url "http://127.0.0.1:$PORT" --db "$DB" \
    2>> "runs/controller_$NAME.log" | grep crashpoint
  set -e
  echo "  -> crashed at $CP, sim at $(curl -s http://127.0.0.1:$PORT/sim/state | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["ts"])'); restarting"
done
# 2. random SIGKILLs
for i in $(seq 1 "$KILLS"); do
  "$PY" -m controller run --url "http://127.0.0.1:$PORT" --db "$DB" 2>> "runs/controller_$NAME.log" &
  CTL=$!
  sleep "$(awk -v s=$RANDOM 'BEGIN{srand(s); printf "%.1f", 3 + rand()*9}')"
  if kill -0 $CTL 2>/dev/null; then
    kill -9 $CTL; wait $CTL 2>/dev/null || true
    echo "kill $i: SIGKILL at sim $(curl -s http://127.0.0.1:$PORT/sim/state | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["ts"])')"
  else
    wait $CTL || true; echo "kill $i: controller had already finished"; break
  fi
done
echo "final restart, running to completion"
"$PY" -m controller run --url "http://127.0.0.1:$PORT" --db "$DB" 2>> "runs/controller_$NAME.log"
"$PY" scripts/verify_run.py "runs/$NAME" "$DB" "http://127.0.0.1:$PORT"
} 2>&1 | tee "$LOG"
