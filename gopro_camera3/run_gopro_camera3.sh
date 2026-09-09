#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../scripts/ksmc_env.sh"

set -u
export PYTHONPATH="$SCRIPT_DIR/third_party/open_gopro_multi_webcam${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1

GOPRO_RUNTIME_DIR="${SCRIPT_DIR}/../runtime"
mkdir -p "${GOPRO_RUNTIME_DIR}"
exec 9>"${GOPRO_RUNTIME_DIR}/gopro_camera3.lock"
if ! flock -n 9; then
  echo '[ERROR] GoPro camera3 is already running.' >&2
  echo '[ERROR] Stop the previous GoPro terminal with Ctrl+C, then retry.' >&2
  exit 1
fi

GOPRO_IP="172.21.198.51"
GOPRO_ROUTE_READY=0
for _attempt in {1..10}; do
  ROUTE_INFO="$(ip -4 route get "$GOPRO_IP" 2>/dev/null || true)"
  if [[ "$ROUTE_INFO" == *"src 172.21.198."* && "$ROUTE_INFO" != *" via "* ]]; then
    GOPRO_ROUTE_READY=1
    break
  fi
  sleep 1
done

if [[ "$GOPRO_ROUTE_READY" -ne 1 ]]; then
  echo "[ERROR] GoPro USB network interface is not ready."
  if lsusb | grep -q "2672:0059"; then
    echo "[ERROR] HERO11 is visible on USB, but CDC-NCM networking failed."
    echo "[ERROR] Reconnect it with a USB 3 data cable/port after selecting GoPro Connect."
  else
    echo "[ERROR] HERO11 is not visible on USB. Check camera power, cable, and port."
  fi
  exit 1
fi

exec python3 "$SCRIPT_DIR/notebooks/gopro_camera3_node.py" \
  198 \
  --transport usb \
  --camera-resolution 7 \
  --publish-fps "${GOPRO_PUBLISH_FPS:-15}" \
  --jpeg-quality "${GOPRO_JPEG_QUALITY:-88}" \
  --stall-timeout 5
