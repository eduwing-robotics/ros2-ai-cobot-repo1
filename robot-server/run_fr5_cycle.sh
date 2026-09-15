#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "${1:-}" in
  --execute|--check) source "${root}/scripts/ksmc_env.sh" ;;
esac
# Match the successful real trials: avoid Fast DDS SHM discovery stalls.
export FASTDDS_BUILTIN_TRANSPORTS=UDPv4
exec python3 "${root}/vision_assembly/scripts/assembly_cycle_launcher.py" "$@"
