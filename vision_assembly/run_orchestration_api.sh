#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${project_dir}/scripts/ksmc_env.sh"
exec ros2 launch vision_server orchestration_api.launch.py
