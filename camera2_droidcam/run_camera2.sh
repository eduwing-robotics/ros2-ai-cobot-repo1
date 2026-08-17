#!/usr/bin/env bash
set -eo pipefail

PHONE_IP="${PHONE_IP:-192.168.11.7}"
PHONE_PORT="${PHONE_PORT:-4747}"
DEVICE="${DEVICE:-/dev/video10}"
SIZE="${SIZE:-1920x1080}"
FPS="${FPS:-30}"
JPEG_QUALITY="${JPEG_QUALITY:-95}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../scripts/ksmc_env.sh"
CLIENT_PID=""

cleanup() {
  if [[ -n "${CLIENT_PID}" ]] && kill -0 "${CLIENT_PID}" 2>/dev/null; then
    kill "${CLIENT_PID}" 2>/dev/null || true
    wait "${CLIENT_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ ! -e "${DEVICE}" ]]; then
  echo "Missing ${DEVICE}. Load v4l2loopback first." >&2
  exit 1
fi

if ! pgrep -f "droidcam-cli.*${PHONE_IP}.*${PHONE_PORT}" >/dev/null; then
  droidcam-cli -v -nocontrols -dev="${DEVICE}" -size="${SIZE}" \
    "${PHONE_IP}" "${PHONE_PORT}" &
  CLIENT_PID=$!
  sleep 2
  if ! kill -0 "${CLIENT_PID}" 2>/dev/null; then
    echo "DroidCam connection failed. Check the phone app and Wi-Fi." >&2
    exit 1
  fi
fi

exec python3 "${SCRIPT_DIR}/camera2_ros_node.py" \
  --device "${DEVICE}" --fps "${FPS}" --jpeg-quality "${JPEG_QUALITY}"
