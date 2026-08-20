#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="${PROJECT_DIR}/vendor/droidcam-linux-client"
DROIDCAM_REPOSITORY="https://github.com/dev47apps/droidcam-linux-client.git"
DROIDCAM_REVISION="cdc044bd74873c6b8750750aac42db8029dac5c1"

if [[ ! -f "${SOURCE_DIR}/Makefile" ]]; then
  echo "Fetching DroidCam source at ${DROIDCAM_REVISION}..."
  mkdir -p "$(dirname "${SOURCE_DIR}")"
  git clone "${DROIDCAM_REPOSITORY}" "${SOURCE_DIR}"
  git -C "${SOURCE_DIR}" checkout --detach "${DROIDCAM_REVISION}"
fi

sudo apt-get update
sudo apt-get install -y \
  build-essential \
  "linux-headers-$(uname -r)" \
  v4l-utils \
  libavutil-dev \
  libswscale-dev \
  libasound2-dev \
  libspeex-dev \
  libusbmuxd-dev \
  libplist-dev \
  libturbojpeg0-dev

make -C "${SOURCE_DIR}" clean
make -C "${SOURCE_DIR}" droidcam-cli
sudo install -m 0755 "${SOURCE_DIR}/droidcam-cli" /usr/local/bin/droidcam-cli

sudo modprobe v4l2loopback video_nr=10 card_label=DroidCam exclusive_caps=1

echo
echo "DroidCam installation complete."
echo "Expected virtual camera: /dev/video10"
v4l2-ctl --list-devices || true
