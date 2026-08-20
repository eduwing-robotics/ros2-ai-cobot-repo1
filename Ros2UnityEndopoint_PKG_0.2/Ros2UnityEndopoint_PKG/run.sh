#!/usr/bin/env bash
set -euo pipefail
export ROS_DOMAIN_ID=5

package_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
setup_file="$package_root/install/setup.bash"

if [[ ! -f "$setup_file" ]]; then
  echo "Run ./install.sh first." >&2
  exit 1
fi
set +u
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${project_dir}/scripts/ksmc_env.sh"
source "$setup_file"
set -u
exec ros2 run ros_tcp_endpoint default_server_endpoint --ros-args \
  -p ROS_IP:="${ROS_IP:-0.0.0.0}" \
  -p ROS_TCP_PORT:="${ROS_TCP_PORT:-10000}"
