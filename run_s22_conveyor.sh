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

# Remove only stale instances created by this project before starting a fresh
# camera + ROI pair.
pkill -f '/vision_server/conveyor_roi' 2>/dev/null || true
pkill -f '/opt/ros/jazzy/bin/ros2 launch vision_server conveyor_roi.launch.py' \
  2>/dev/null || true

"${PROJECT_DIR}/camera2_droidcam/run_camera2_usb.sh" &
CAMERA_PID=$!

camera_ready=0
for _ in {1..20}; do
  if timeout 2s ros2 topic echo \
    /camera2/image_raw/compressed --once >/dev/null 2>&1; then
    camera_ready=1
    break
  fi
  if ! kill -0 "${CAMERA_PID}" 2>/dev/null; then
    echo '[S22 Conveyor] Camera launcher stopped.' >&2
    exit 1
  fi
  sleep 1
done

if (( camera_ready == 0 )); then
  echo '[S22 Conveyor] No camera2 frame received within the startup timeout.' >&2
  exit 1
fi

echo '[S22 Conveyor] Camera ready; starting stop-line overlay.'
"${PROJECT_DIR}/ros2_ws/run_conveyor_roi.sh" &
ROI_PID=$!

wait "${ROI_PID}"
