#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"
# Fast DDS 2.14.6 deadlocked in WriterProxy::stop / PDP liveliness on this
# node (upstream Fast-DDS#6502). Scope the alternative RMW to registration.
export RMW_IMPLEMENTATION="${KSMC_TRAY_SECTION_RMW:-rmw_cyclonedds_cpp}"
exec python3 "${script_dir}/scripts/view_tray_sections.py" "$@"
