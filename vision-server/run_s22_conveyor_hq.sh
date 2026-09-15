#!/usr/bin/env bash
set -Eeo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${PROJECT_DIR}/scripts/ksmc_env.sh"

CAMERA_PID=""
CAMERA_OWNED=0
ROI_PID=""
HQ_LOCK_FILE="${S22_CAMERA_CONTROL_DIR:-${PROJECT_DIR}/runtime/s22_camera_control}/hq_launcher.lock"
mkdir -p "$(dirname "${HQ_LOCK_FILE}")"
exec 8>"${HQ_LOCK_FILE}"
if ! flock -n 8; then
  echo '[S22 Conveyor HQ] Another HQ launcher is already running; leaving it untouched.'
  exit 0
fi

camera_launcher_pid() {
  local pid=""
  local cmdline=""
  local pid_file="${S22_CAMERA_CONTROL_DIR:-${PROJECT_DIR}/runtime/s22_camera_control}/launcher.pid"
  [[ -r "${pid_file}" ]] || return 1
  pid="$(<"${pid_file}")"
  [[ "${pid}" =~ ^[0-9]+$ ]] || return 1
  kill -0 "${pid}" 2>/dev/null || return 1
  [[ -r "/proc/${pid}/cmdline" ]] || return 1
  cmdline="$(tr '\0' ' ' <"/proc/${pid}/cmdline")"
  [[ "${cmdline}" == *"${PROJECT_DIR}/camera2_scrcpy/run_camera2_scrcpy.sh"* ]] || return 1
  CAMERA_PID="${pid}"
  return 0
}

cleanup() {
  if [[ -n "${ROI_PID}" ]] && kill -0 "${ROI_PID}" 2>/dev/null; then
    kill "${ROI_PID}" 2>/dev/null || true
    wait "${ROI_PID}" 2>/dev/null || true
  fi
  if (( CAMERA_OWNED )) && [[ -n "${CAMERA_PID}" ]] && kill -0 "${CAMERA_PID}" 2>/dev/null; then
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
if camera_launcher_pid; then
  echo "[S22 Conveyor HQ] Reusing existing S22 scrcpy launcher (PID ${CAMERA_PID})."
else
  "${PROJECT_DIR}/camera2_scrcpy/run_camera2_scrcpy.sh" &
  CAMERA_PID=$!
  CAMERA_OWNED=1
fi

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
