#!/usr/bin/env bash
# Existing D435/tray detector -> fresh non-SMD target -> 50 mm hover only.
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"
set -u
exec python3 "${script_dir}/scripts/run_tray_part_hover_5cm.py" "$@"
