#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
calibration_file="${project_dir}/vision_assembly/data/s22_plane_calibration.json"

if [[ ! -f "${calibration_file}" ]]; then
  echo "Missing S22 plane calibration: ${calibration_file}" >&2
  echo "Capture at least 6 spread-out points, then run:" >&2
  echo "  ~/KSMC/vision_assembly/run_calibrate_s22_plane.sh" >&2
  exit 1
fi

source "${project_dir}/scripts/ksmc_env.sh"
exec ros2 launch vision_server s22_board_localizer.launch.py "$@"
