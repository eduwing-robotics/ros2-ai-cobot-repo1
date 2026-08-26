#!/usr/bin/env bash
set -euo pipefail
export ROS_DOMAIN_ID=5

package_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
setup_file="$package_root/install/setup.bash"

if [[ ! -f "$setup_file" ]]; then
  echo "Run ./build.sh first." >&2
  exit 1
fi

set +u
source /home/hc/KSMC/robot_ws/install/setup.bash
source "$setup_file"
set -u
exec ros2 launch ros_tcp_endpoint endpoint.py
