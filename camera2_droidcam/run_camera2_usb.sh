#!/usr/bin/env bash
set -Eeo pipefail

DEVICE="${DEVICE:-/dev/video10}"
SIZE="${SIZE:-1920x1080}"
FPS="${FPS:-30}"
JPEG_QUALITY="${JPEG_QUALITY:-95}"
PHONE_PORT="${PHONE_PORT:-4747}"
PHONE_SERIAL="${PHONE_SERIAL:-}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-5}"
MAX_RESTARTS="${MAX_RESTARTS:-5}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${PROJECT_DIR}/scripts/ksmc_env.sh"

CLIENT_PID=""
ROS_PID=""
STOP_REQUESTED=0

log() {
  printf '[S22 USB] %s\n' "$*"
}

cleanup_children() {
  if [[ -n "${ROS_PID}" ]] && kill -0 "${ROS_PID}" 2>/dev/null; then
    kill "${ROS_PID}" 2>/dev/null || true
    wait "${ROS_PID}" 2>/dev/null || true
  fi
  if [[ -n "${CLIENT_PID}" ]] && kill -0 "${CLIENT_PID}" 2>/dev/null; then
    kill "${CLIENT_PID}" 2>/dev/null || true
    wait "${CLIENT_PID}" 2>/dev/null || true
  fi
  ROS_PID=""
  CLIENT_PID=""
}

shutdown() {
  STOP_REQUESTED=1
  cleanup_children
}
trap shutdown EXIT INT TERM

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "Missing command: $1"
    exit 1
  fi
}

require_command adb
require_command droidcam-cli
require_command python3

if [[ -z "${PHONE_SERIAL}" ]]; then
  mapfile -t adb_serials < <(adb devices | awk '$2 == "device" {print $1}')
  if [[ ${#adb_serials[@]} -ne 1 ]]; then
    log "Set PHONE_SERIAL in config/ksmc.env when zero or multiple ADB devices are connected."
    adb devices -l
    exit 1
  fi
  PHONE_SERIAL="${adb_serials[0]}"
fi

if ! adb devices | awk -v serial="${PHONE_SERIAL}" \
  '$1 == serial && $2 == "device" { found=1 } END { exit !found }'; then
  log "S22 ${PHONE_SERIAL} is not authorized over USB."
  log "Unlock the phone, enable USB debugging, and accept the RSA prompt."
  adb devices -l
  exit 1
fi

export ANDROID_SERIAL="${PHONE_SERIAL}"
export ROS_DOMAIN_ID

adb -s "${PHONE_SERIAL}" shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1 || true
adb -s "${PHONE_SERIAL}" shell am start \
  -n com.dev47apps.droidcam/.DroidCam >/dev/null

for _ in {1..10}; do
  if ! adb -s "${PHONE_SERIAL}" shell dumpsys window 2>/dev/null \
    | grep -q 'mDreamingLockscreen=true'; then
    break
  fi
  log "Waiting for S22 unlock..."
  sleep 1
done

if adb -s "${PHONE_SERIAL}" shell dumpsys window 2>/dev/null \
  | grep -q 'mDreamingLockscreen=true'; then
  log "S22 is still locked. Unlock it and run this command again."
  exit 1
fi

if [[ ! -e "${DEVICE}" ]]; then
  log "${DEVICE} is missing; loading v4l2loopback."
  sudo modprobe v4l2loopback \
    video_nr="${DEVICE##*/video}" \
    card_label="DroidCam-S22" \
    exclusive_caps=1
fi

if [[ ! -e "${DEVICE}" ]]; then
  log "Failed to create ${DEVICE}."
  exit 1
fi

# Never reuse old Wi-Fi/USB writers. A stale writer can keep /dev/video10 open
# while no frames reach ROS.
pkill -x droidcam-cli 2>/dev/null || true
pkill -f "^python3 ${SCRIPT_DIR}/camera2_ros_node.py" 2>/dev/null || true
adb -s "${PHONE_SERIAL}" forward --remove "tcp:${PHONE_PORT}" \
  >/dev/null 2>&1 || true

restart_count=0
while (( STOP_REQUESTED == 0 )); do
  restart_count=$((restart_count + 1))
  if (( restart_count > MAX_RESTARTS )); then
    log "Connection failed after ${MAX_RESTARTS} attempts."
    exit 1
  fi

  log "Starting DroidCam attempt ${restart_count}/${MAX_RESTARTS}: ${SIZE}, ROS domain ${ROS_DOMAIN_ID}"
  adb -s "${PHONE_SERIAL}" forward --remove "tcp:${PHONE_PORT}" \
    >/dev/null 2>&1 || true
  droidcam-cli -v -nocontrols -dev="${DEVICE}" -size="${SIZE}" \
    adb "${PHONE_PORT}" &
  CLIENT_PID=$!

  sleep 2
  if ! kill -0 "${CLIENT_PID}" 2>/dev/null; then
    log "DroidCam app rejected the connection; retrying."
    cleanup_children
    adb -s "${PHONE_SERIAL}" shell am start \
      -n com.dev47apps.droidcam/.DroidCam >/dev/null 2>&1 || true
    sleep 1
    continue
  fi

  python3 "${SCRIPT_DIR}/camera2_ros_node.py" \
    --device "${DEVICE}" --fps "${FPS}" --jpeg-quality "${JPEG_QUALITY}" &
  ROS_PID=$!

  sleep 2
  if ! kill -0 "${ROS_PID}" 2>/dev/null; then
    log "ROS camera2 node could not open ${DEVICE}; retrying."
    cleanup_children
    sleep 1
    continue
  fi

  log "Running: /camera2/image_raw/compressed (Ctrl+C to stop)"
  restart_count=0
  while kill -0 "${CLIENT_PID}" 2>/dev/null \
    && kill -0 "${ROS_PID}" 2>/dev/null; do
    sleep 1
  done

  if (( STOP_REQUESTED == 0 )); then
    log "Stream process stopped unexpectedly; reconnecting."
    cleanup_children
    sleep 1
  fi
done
