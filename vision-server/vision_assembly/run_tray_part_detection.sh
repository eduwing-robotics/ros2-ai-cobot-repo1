#!/usr/bin/env bash
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source /opt/ros/jazzy/setup.bash
source "${script_dir}/../robot_ws/install/setup.bash"
set -u
exec python3 "${script_dir}/scripts/detect_tray_parts.py" "$@"
