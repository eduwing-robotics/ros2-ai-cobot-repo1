#!/usr/bin/env bash
set -eo pipefail
viewer_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == '--help' || "${1:-}" == '-h' ]]; then
  exec /usr/bin/python3 "${viewer_dir}/view_camera.py" "$@"
fi
# Portable viewer environment: never source the camera laptop's private config
# or copy its interface allowlist onto a teammate PC with different NIC names.
source "/opt/ros/${ROS_DISTRO:-jazzy}/setup.bash"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-5}"
export ROS_LOCALHOST_ONLY=0
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
exec /usr/bin/python3 "${viewer_dir}/view_camera.py" "$@"
