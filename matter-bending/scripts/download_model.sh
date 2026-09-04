#!/usr/bin/env bash
# Downloads the MediaPipe Hand Landmarker (float16) model used by
# hand_tracker.py. Run from anywhere; the model is always saved beside
# hand_tracker.py, where it expects to find it.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MODEL_URL="https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
DEST="$PROJECT_DIR/hand_landmarker.task"

echo "Downloading MediaPipe Hand Landmarker model (float16) to $DEST"
curl -L --fail -o "$DEST" "$MODEL_URL"
echo "Done."
