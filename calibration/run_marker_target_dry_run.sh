#!/usr/bin/env bash

# ROS Jazzy's setup script references AMENT_TRACE_SETUP_FILES while it is
# initializing.  Source both environments before enabling nounset.
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"

exec python3 "${script_dir}/scripts/marker_target_dry_run.py" "$@"
