#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${root}/scripts/ksmc_env.sh"
exec ros2 run vision_server unity_calibration_api --ros-args -p project_root:="${root}"
