#!/usr/bin/env bash
set -Eeo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${PROJECT_DIR}/scripts/ksmc_env.sh"

usage() {
  cat <<'EOF'
Usage:
  run_conveyor_remote_server.sh --monitor-only
  run_conveyor_remote_server.sh --execute --confirm-motion

The armed server does not move on startup. Motion begins only after a guarded
/conveyor/move_to_assembly or /conveyor/move_to_inspection service request.
EOF
}

allow_motion=false
if [[ $# -eq 1 && "$1" == "--monitor-only" ]]; then
  allow_motion=false
elif [[ $# -eq 2 && "$1" == "--execute" && "$2" == "--confirm-motion" ]]; then
  allow_motion=true
else
  usage >&2
  exit 2
fi

exec ros2 run vision_server conveyor_remote_server --ros-args \
  -p allow_motion:="${allow_motion}"
