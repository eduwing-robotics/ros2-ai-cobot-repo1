#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"

if [[ ! -f "${script_dir}/install/setup.bash" ]]; then
  echo "robot_ws is not built. Run ${script_dir}/build_robot_ws.sh first." >&2
  exit 1
fi

exec ros2 run fairino_hardware_v3_9_7 ros2_cmd_server
