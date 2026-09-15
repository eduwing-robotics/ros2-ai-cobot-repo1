#!/usr/bin/env bash
set -eo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../scripts/ksmc_env.sh"

# Serialize launchers and refuse an existing orphan from an older launch.
# Never terminate an existing node or start a second control/image publisher.
mkdir -p "${KSMC_ROOT}/runtime"
exec 9>"${KSMC_ROOT}/runtime/conveyor_roi.lock"
if ! flock -n 9; then
  echo '[ERROR] Conveyor stop-overlay launcher is already running.' >&2
  exit 73
fi
if pgrep -u "$(id -u)" -f '/lib/vision_server/conveyor_roi( |$)' >/dev/null; then
  echo '[ERROR] Existing conveyor stop-overlay node; no duplicate or takeover.' >&2
  exit 73
fi

exec ros2 launch vision_server conveyor_roi.launch.py "$@"
