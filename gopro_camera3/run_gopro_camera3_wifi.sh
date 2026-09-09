#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../scripts/ksmc_env.sh"
set -u

GOPRO_RUNTIME_DIR="${SCRIPT_DIR}/../runtime"
mkdir -p "${GOPRO_RUNTIME_DIR}"
exec 9>"${GOPRO_RUNTIME_DIR}/gopro_camera3.lock"
if ! flock -n 9; then
  echo '[ERROR] GoPro camera3 is already running.' >&2
  echo '[ERROR] Stop the previous GoPro terminal with Ctrl+C, then retry.' >&2
  exit 1
fi

GOPRO_IP="10.5.5.9"
GOPRO_SSID="GP27378198"

route_is_ready() {
  local route_info
  route_info="$(ip -4 route get "$GOPRO_IP" 2>/dev/null || true)"
  [[ "$route_info" == *"src 10.5.5."* && "$route_info" != *" via "* ]]
}

# If the GoPro connection was saved previously, reconnect it on the USB Wi-Fi
# adapter. Never take over the laptop's built-in Wi-Fi interface automatically.
if ! route_is_ready && command -v nmcli >/dev/null 2>&1; then
  USB_WIFI_INTERFACE=""
  for interface_path in /sys/class/net/*; do
    interface="$(basename "$interface_path")"
    if [[ -d "$interface_path/wireless" ]] &&
       [[ "$(readlink -f "$interface_path/device")" == *"/usb"* ]]; then
      USB_WIFI_INTERFACE="$interface"
      break
    fi
  done

  if [[ -n "$USB_WIFI_INTERFACE" ]] &&
     nmcli connection show "$GOPRO_SSID" >/dev/null 2>&1; then
    # USB Wi-Fi interface names can change after reconnecting the adapter.
    # Repair an old interface binding automatically while preserving the
    # laboratory/ROS network as the system default route.
    SAVED_INTERFACE="$(
      nmcli -g connection.interface-name connection show "$GOPRO_SSID" \
        2>/dev/null || true
    )"
    if [[ "$SAVED_INTERFACE" != "$USB_WIFI_INTERFACE" ]]; then
      echo "[INFO] Rebinding $GOPRO_SSID from ${SAVED_INTERFACE:-auto} to $USB_WIFI_INTERFACE..."
      nmcli connection modify "$GOPRO_SSID" \
        connection.interface-name "$USB_WIFI_INTERFACE" \
        ipv4.never-default yes \
        ipv6.never-default yes
    fi
    echo "[INFO] Connecting $USB_WIFI_INTERFACE to $GOPRO_SSID..."
    nmcli --wait 15 connection up id "$GOPRO_SSID" ifname "$USB_WIFI_INTERFACE" || true
  fi
fi

for _attempt in {1..10}; do
  route_is_ready && break
  sleep 1
done

if ! route_is_ready; then
  echo "[ERROR] The laptop is not connected directly to the GoPro Wi-Fi."
  echo "[ERROR] 1) Turn on the HERO11 with Quik, then leave the preview screen."
  echo "[ERROR] 2) Connect the USB Wi-Fi adapter to $GOPRO_SSID."
  echo "[ERROR] 3) Run this command again."
  exit 1
fi

if ! curl --silent --fail --max-time 2 \
  "http://${GOPRO_IP}:8080/gopro/camera/state" >/dev/null; then
  echo "[ERROR] GoPro Wi-Fi is connected, but the camera HTTP API is not responding."
  echo "[ERROR] Make sure the camera is on and close Quik's preview screen."
  exit 1
fi

export PYTHONUNBUFFERED=1
exec python3 "$SCRIPT_DIR/notebooks/gopro_camera3_node.py" \
  198 \
  --transport wifi \
  --host "$GOPRO_IP" \
  --port 8554 \
  --publish-fps "${GOPRO_PUBLISH_FPS:-15}" \
  --jpeg-quality "${GOPRO_JPEG_QUALITY:-88}" \
  --stall-timeout 8
