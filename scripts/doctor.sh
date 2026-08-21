#!/usr/bin/env bash
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
failures=0

check_file() {
  if [[ -e "$2" ]]; then
    printf 'OK   %s\n' "$1"
  else
    printf 'FAIL %s: %s\n' "$1" "$2"
    failures=$((failures + 1))
  fi
}

check_command() {
  if command -v "$2" >/dev/null 2>&1; then
    printf 'OK   %s\n' "$1"
  else
    printf 'FAIL %s: command %s not found\n' "$1" "$2"
    failures=$((failures + 1))
  fi
}

check_file 'ROS 2 Jazzy' /opt/ros/jazzy/setup.bash
check_file 'Device config' "${PROJECT_DIR}/config/ksmc.env"
check_file 'FR5 workspace overlay' "${PROJECT_DIR}/robot_ws/install/setup.bash"
check_file 'Vision workspace overlay' "${PROJECT_DIR}/ros2_ws/install/setup.bash"
check_file 'Hand-Eye result' "${PROJECT_DIR}/calibration/data/handeye_result.json"
check_file 'ChArUco config' "${PROJECT_DIR}/calibration/config/charuco_board.yaml"
check_file 'FR5 process planner' "${PROJECT_DIR}/ros2_ws/src/fr5_process_sequences/fr5_process_sequences/planner.py"
check_file 'D435 depth config' "${PROJECT_DIR}/ros2_ws/src/vision_server/config/cameras.yaml"
check_command 'Python' python3
check_command 'colcon' colcon
check_command 'rosdep' rosdep
check_command 'ADB (S22)' adb

if command -v droidcam-cli >/dev/null 2>&1; then
  printf 'OK   DroidCam CLI (optional)\n'
else
  printf 'WARN DroidCam CLI not installed; S22 camera will be unavailable\n'
fi

printf '\nProject root: %s\n' "${PROJECT_DIR}"
printf 'Failures: %d\n' "${failures}"
exit "${failures}"
