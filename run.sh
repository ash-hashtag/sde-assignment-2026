#!/usr/bin/env bash
# Starts the controller and runs it until the scenario finishes. No Docker; needs Python 3.11+.
#   ./run.sh <SIM_URL>
# State lives in $CONTROLLER_DB (default state/controller.db). Re-running against the same simulator resumes.
set -euo pipefail
SIM_URL="${1:?usage: ./run.sh <SIM_URL>}"
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
exec .venv/bin/python -m controller run --url "$SIM_URL" --db "${CONTROLLER_DB:-state/controller.db}"
