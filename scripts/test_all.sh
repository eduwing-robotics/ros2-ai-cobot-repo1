#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${PROJECT_DIR}/ros2_ws/src/fr5_process_sequences:${PROJECT_DIR}/ros2_ws/src/vision_server${PYTHONPATH:+:${PYTHONPATH}}"

python3 -m pytest \
  "${PROJECT_DIR}/ros2_ws/src/fr5_process_sequences/test" \
  "${PROJECT_DIR}/ros2_ws/src/vision_server/test" \
  -q

python3 -m compileall -q \
  "${PROJECT_DIR}/calibration/scripts" \
  "${PROJECT_DIR}/vision_assembly/scripts" \
  "${PROJECT_DIR}/ros2_ws/src"

echo "Source tests and Python syntax checks passed."
