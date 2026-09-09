#!/usr/bin/env bash
set -Eeo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${PROJECT_DIR}/scripts/ksmc_env.sh"

CAMERA_PID=""
ROI_PID=""

cleanup() {
  if [[ -n "${ROI_PID}" ]] && kill -0 "${ROI_PID}" 2>/dev/null; then
    kill "${ROI_PID}" 2>/dev/null || true
    wait "${ROI_PID}" 2>/dev/null || true
  fi
  if [[ -n "${CAMERA_PID}" ]] && kill -0 "${CAMERA_PID}" 2>/dev/null; then
    kill "${CAMERA_PID}" 2>/dev/null || true
    wait "${CAMERA_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# Remove only stale conveyor overlay instances before starting one managed
# S22 scrcpy camera + ROI pair.
pkill -f '/vision_server/conveyor_roi' 2>/dev/null || true
pkill -f '/opt/ros/jazzy/bin/ros2 launch vision_server conveyor_roi.launch.py' \
  2>/dev/null || true

echo '[S22 Conveyor HQ] Starting the USB scrcpy camera.'
"${PROJECT_DIR}/camera2_scrcpy/run_camera2_scrcpy.sh" &
CAMERA_PID=$!

# The ROI node is a persistent subscriber and safely waits for the first
# frame. A short ros2 CLI probe can miss DDS discovery and is intentionally
# not used as a startup gate.
sleep 3
if ! kill -0 "${CAMERA_PID}" 2>/dev/null; then
  echo '[S22 Conveyor HQ] Camera launcher stopped during startup.' >&2
  exit 1
fi

echo '[S22 Conveyor HQ] Starting assembly + inspection stop-line overlay.'
"${PROJECT_DIR}/ros2_ws/run_conveyor_roi.sh" &
ROI_PID=$!
echo '[S22 Conveyor HQ] Stop lines: /vision/conveyor/stop_image/compressed'
echo '[S22 Conveyor HQ] Smooth view: /camera2/image_stream/compressed'
echo '[S22 Conveyor HQ] Clean analysis: /camera2/image_raw/compressed'

while true; do
  if ! kill -0 "${CAMERA_PID}" 2>/dev/null; then
    echo '[S22 Conveyor HQ] Camera launcher stopped.' >&2
    exit 1
  fi
  if ! kill -0 "${ROI_PID}" 2>/dev/null; then
    wait "${ROI_PID}"
    exit $?
  fi
  sleep 2
done
