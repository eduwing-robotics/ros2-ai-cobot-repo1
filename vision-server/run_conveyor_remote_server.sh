#!/usr/bin/env bash
set -Eeo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${PROJECT_DIR}/scripts/ksmc_env.sh"

# Keep the historical server-only command safe for the separate conveyor-server
# role. A caller that owns the whole cell can opt into the additive launcher
# with `--with-s22`; that launcher starts this script again without the flag,
# so it cannot recurse. The Unity/ROS-TCP endpoint is deliberately not part of
# either path and remains team-managed.
with_s22=false
server_args=()
for arg in "$@"; do
  if [[ "${arg}" == "--with-s22" ]]; then
    with_s22=true
  else
    server_args+=("${arg}")
  fi
done
if ${with_s22}; then
  exec "${PROJECT_DIR}/run_conveyor_cell.sh" "${server_args[@]}"
fi
set -- "${server_args[@]}"

# There must be exactly one process with authority to publish the robot's
# /cmd_vel.  ROS graph discovery is asynchronous and cannot by itself prevent
# two launchers on this laptop from alternating speed and zero commands.  Keep
# an inherited flock for the whole server lifetime so a direct test controller
# and the remote server cannot own the belt at the same time.
CONVEYOR_CMD_LOCK="${PROJECT_DIR}/runtime/conveyor_cmd_vel_owner.lock"
mkdir -p "$(dirname "${CONVEYOR_CMD_LOCK}")"
exec 9>"${CONVEYOR_CMD_LOCK}"
if ! flock -n 9; then
  echo '[S22 Conveyor] Another conveyor command owner is already running.' >&2
  echo '[S22 Conveyor] Stop it before starting the remote server.' >&2
  exit 1
fi

usage() {
  cat <<'EOF'
Usage:
  run_conveyor_remote_server.sh --monitor-only
  run_conveyor_remote_server.sh --execute --confirm-motion
  run_conveyor_remote_server.sh --with-s22 --monitor-only
  run_conveyor_remote_server.sh --with-s22 --execute --confirm-motion

The armed server does not move on startup. Motion begins only after a guarded
/conveyor/move_to_assembly or /conveyor/move_to_inspection service request.
The --with-s22 form also starts the S22 camera/ROI launcher and owns both
processes for the lifetime of the command. It never starts the Unity endpoint.
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
