#!/usr/bin/env bash
# Compiles every module and runs the unit test suite. gesture_math.py and
# osc_bridge.py's tests need no external dependencies; if opencv/mediapipe/
# python-osc aren't installed, hand_tracker.py still compiles and imports
# (it defers those imports into main()), but its --help / missing-model
# checks below are skipped.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "== compiling =="
python3 -m py_compile gesture_math.py osc_bridge.py hand_tracker.py

echo "== unit tests =="
python3 -m unittest discover -s tests -v

echo "== hand_tracker.py CLI smoke test =="
python3 hand_tracker.py --help >/dev/null

echo "== graceful missing-model handling =="
if python3 hand_tracker.py --model-path /nonexistent/hand_landmarker.task; then
    echo "expected exit code 1 for a missing model, got 0" >&2
    exit 1
else
    echo "missing model correctly exits non-zero without a traceback"
fi

echo "All checks passed."
