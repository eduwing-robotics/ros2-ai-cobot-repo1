#!/usr/bin/env bash
set -euo pipefail

package_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ros_setup="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"

if [[ ! -f "$ros_setup" ]]; then
  echo "ROS 2 setup not found: $ros_setup" >&2
  exit 1
fi
if ! command -v colcon >/dev/null 2>&1; then
  echo "colcon not found. Install python3-colcon-common-extensions." >&2
  exit 1
fi

set +u
source "$ros_setup"
set -u
cd "$package_root"
colcon build --symlink-install

echo "Installed. Run: ./run.sh"
