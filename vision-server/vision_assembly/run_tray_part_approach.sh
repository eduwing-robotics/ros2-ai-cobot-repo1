#!/usr/bin/env bash
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"
set -u
exec python3 "${script_dir}/scripts/move_tray_part_approach.py" "$@"
