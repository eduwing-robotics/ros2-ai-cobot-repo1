#!/usr/bin/env bash
set -Eeo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${project_dir}/scripts/ksmc_env.sh"

if [[ "${1:-}" == "--legacy-arrival-trigger" ]]; then
  shift
  exec python3 "${project_dir}/vision_assembly/inspection/conveyor_inspection_trigger.py" "$@"
fi
# Default production path: arrival is a prerequisite, never a capture request.
exec python3 "${project_dir}/vision_assembly/integration/inspection_ros.py" "$@"
