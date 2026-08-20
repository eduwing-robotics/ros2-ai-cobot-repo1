#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${PROJECT_DIR}/scripts/ksmc_env.sh"

if [[ ! -d "${PROJECT_DIR}/robot_ws/src/vendor" ]]; then
  echo "Missing FAIRINO vendor source. Run robot_ws/setup_fairino_vendor.sh --from-official" >&2
  exit 1
fi

"${PROJECT_DIR}/robot_ws/build_robot_ws.sh"

cd "${PROJECT_DIR}/ros2_ws"
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install

echo "All KSMC ROS workspaces built successfully."
