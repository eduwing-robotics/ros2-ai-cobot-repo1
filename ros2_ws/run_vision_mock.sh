#!/usr/bin/env bash
set -eo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SCENARIO="${1:-pass}"
export ROS_LOG_DIR="${SCRIPT_DIR}/log/runtime"
mkdir -p "${ROS_LOG_DIR}"
source "${SCRIPT_DIR}/../scripts/ksmc_env.sh"

exec ros2 launch vision_server mock.launch.py "scenario:=${SCENARIO}"
