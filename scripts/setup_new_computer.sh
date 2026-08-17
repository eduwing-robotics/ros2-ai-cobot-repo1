#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f /opt/ros/jazzy/setup.bash ]]; then
  echo "ROS 2 Jazzy is required first: /opt/ros/jazzy/setup.bash not found." >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y \
  adb build-essential git python3-colcon-common-extensions python3-opencv \
  python3-numpy python3-pip python3-rosdep python3-scipy python3-yaml \
  v4l-utils \
  ros-jazzy-cv-bridge ros-jazzy-image-transport ros-jazzy-rqt-image-view \
  ros-jazzy-realsense2-camera ros-jazzy-realsense2-description

if [[ ! -f "${PROJECT_DIR}/config/ksmc.env" ]]; then
  cp "${PROJECT_DIR}/config/ksmc.env.example" \
    "${PROJECT_DIR}/config/ksmc.env"
  echo "Created config/ksmc.env. Edit PHONE_SERIAL before S22 use."
fi

if [[ ! -d "${PROJECT_DIR}/robot_ws/src/vendor" ]]; then
  "${PROJECT_DIR}/robot_ws/setup_fairino_vendor.sh" --from-official
fi

"${PROJECT_DIR}/scripts/build_all.sh"

echo
echo "Base setup complete. DroidCam is optional; see camera2_droidcam/README.md."
echo "Next: edit config/ksmc.env, then run scripts/doctor.sh."
