#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="${script_dir}"

set +u
source "${script_dir}/../scripts/ksmc_env.sh"
set -u

cd "${workspace_dir}"
colcon build --symlink-install \
  --packages-select fairino_msgs fairino_hardware_v3_9_7 fairino_description fairino5_v6_moveit2_config

echo "Built KSMC FR5 workspace: ${workspace_dir}/install"
