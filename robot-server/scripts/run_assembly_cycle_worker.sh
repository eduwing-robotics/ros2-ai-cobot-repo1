#!/usr/bin/env bash
# Internal API worker. Public/operator entrypoint: run_fr5_cycle.sh.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${root}/scripts/ksmc_env.sh"
export FASTDDS_BUILTIN_TRANSPORTS=UDPv4
exec python3 "${root}/vision_assembly/scripts/assembly_cycle_launcher.py" "$@"
