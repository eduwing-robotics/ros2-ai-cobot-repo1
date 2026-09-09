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
check_command 'Python' python3
check_command 'colcon' colcon
check_command 'rosdep' rosdep
check_command 'ADB (S22)' adb
check_command 'V4L2 utilities' v4l2-ctl

scrcpy_bin="${PROJECT_DIR}/runtime/tools/scrcpy-linux-x86_64-v4.1/scrcpy"
if [[ -x "${scrcpy_bin}" ]]; then
  printf 'OK   scrcpy 4.1 (S22 USB camera)\n'
else
  printf 'FAIL scrcpy 4.1: run camera2_scrcpy/install_scrcpy.sh\n'
  failures=$((failures + 1))
fi

if modinfo v4l2loopback >/dev/null 2>&1; then
  printf 'OK   v4l2loopback kernel module\n'
else
  printf 'FAIL v4l2loopback kernel module is unavailable\n'
  failures=$((failures + 1))
fi

printf '\nProject root: %s\n' "${PROJECT_DIR}"
printf 'Failures: %d\n' "${failures}"
exit "${failures}"
