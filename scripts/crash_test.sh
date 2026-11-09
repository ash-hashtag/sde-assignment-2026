#!/usr/bin/env bash
# Crash-recovery test: kill the controller mid-run, restart it, and check the run finishes correctly.
#   scripts/crash_test.sh [scenario] [kills] [port]
# Two independent passes, each on a fresh simulator and store, each verified:
#   A. injected crash points: os._exit right after a side effect the store hasn't recorded yet;
#   B. random SIGKILLs at 1-4 s intervals (a dev scenario runs in under a minute on a fast box).
# They are separate because either one alone can run the scenario to its end before the other gets a turn.
# Writes reports/crash_test.log. Verification reads the simulator's run dir, which only this test harness does —
# the controller itself never reads it.
set -euo pipefail
cd "$(dirname "$0")/.."
SC="${1:-scenarios/public_02_incidents.yaml}"; KILLS="${2:-6}"; PORT="${3:-8790}"
PY=.venv/bin/python
LOG=reports/crash_test.log
URL="http://127.0.0.1:$PORT"
mkdir -p reports state runs
SIM=
trap 'kill $SIM 2>/dev/null || true' EXIT

sim_ts() { curl -s "$URL/sim/state" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["ts"])'; }

start() {   # fresh simulator + store for one pass
  NAME="crash_$(basename "$SC" .yaml)_$1"; DB="state/$NAME.db"
  rm -f "$DB" "$DB-wal" "$DB-shm"
  "$PY" -m sim serve --scenario "$SC" --run-dir "runs/$NAME" --force --port "$PORT" > "runs/sim_$NAME.log" 2>&1 &
  SIM=$!
  until curl -sf "$URL/health" >/dev/null; do sleep 0.5; done
}

finish() {
  echo "final restart, running to completion"
  "$PY" -m controller run --url "$URL" --db "$DB" 2>> "runs/controller_$NAME.log"
  "$PY" scripts/verify_run.py "runs/$NAME" "$DB" "$URL"
  kill $SIM; wait $SIM 2>/dev/null || true
}

{
echo "# crash test $(date -Is): $SC"
echo
echo "## pass A: injected crash points"
start points
for CP in mid_ingest:40 after_auto_put:1 before_approval_post:1 after_approval_post:2 after_apply_post:1 \
          after_auto_put:3 after_approval_post:3 after_apply_post:2; do
  set +e
  CONTROLLER_CRASHPOINTS="$CP" "$PY" -m controller run --url "$URL" --db "$DB" \
    2>> "runs/controller_$NAME.log" | grep crashpoint
  set -e
  echo "  -> ran with $CP, sim at $(sim_ts); restarting"
done
finish

echo
echo "## pass B: $KILLS random SIGKILLs"
start kills
for i in $(seq 1 "$KILLS"); do
  "$PY" -m controller run --url "$URL" --db "$DB" 2>> "runs/controller_$NAME.log" &
  CTL=$!
  sleep "$(awk -v s=$RANDOM 'BEGIN{srand(s); printf "%.1f", 1 + rand()*3}')"
  if kill -0 $CTL 2>/dev/null; then
    kill -9 $CTL; wait $CTL 2>/dev/null || true
    echo "kill $i: SIGKILL at sim $(sim_ts)"
  else
    wait $CTL || true; echo "kill $i: controller had already finished"; break
  fi
done
finish
} 2>&1 | tee "$LOG"
