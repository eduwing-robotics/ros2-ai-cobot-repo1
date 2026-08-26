#!/usr/bin/env bash
set -euo pipefail

package_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ros_setup="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"

if [[ ! -f "$ros_setup" ]]; then
  echo "ROS setup not found: $ros_setup" >&2
  exit 1
fi

source "$ros_setup"
cd "$package_root"
rosdep install --from-paths src --ignore-src -r -y --skip-keys fr5_moveit_mvp
colcon build --symlink-install
