#!/usr/bin/env bash
set -euo pipefail

package_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

set +u
if [[ -n "${ROS_SETUP:-}" ]]; then
  if [[ ! -f "$ROS_SETUP" ]]; then
    echo "ROS setup not found: $ROS_SETUP" >&2
    exit 1
  fi
  source "$ROS_SETUP"
elif ! command -v ros2 >/dev/null 2>&1 || ! ros2 pkg prefix fairino_msgs >/dev/null 2>&1; then
  if [[ ! -f /opt/ros/jazzy/setup.bash ]]; then
    echo "ROS 2 setup not found: /opt/ros/jazzy/setup.bash" >&2
    exit 1
  fi
  source /opt/ros/jazzy/setup.bash
fi
set -u

if ! command -v colcon >/dev/null 2>&1; then
  echo "colcon not found. Install python3-colcon-common-extensions." >&2
  exit 1
fi
if ! ros2 pkg prefix fairino_msgs >/dev/null 2>&1; then
  echo "Warning: fairino_msgs not found; building endpoint-only mode." >&2
  echo "Source the FAIRINO workspace in ~/.bashrc, then rebuild for real robot messages." >&2
fi

cd "$package_root"
colcon build --symlink-install
printf '%s\n' "$package_root" > "$package_root/install/.built_for"

echo "Built for this PC: $package_root/install"
echo "Run: ./run.sh"
