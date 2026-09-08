#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $# -eq 0 ]] || { echo "This connection launcher takes no arguments; configure KSMC_REAL_HARDWARE_EXECUTION in config/ksmc.env." >&2; exit 2; }
source "${root}/scripts/ksmc_env.sh"
hardware_execution="${KSMC_REAL_HARDWARE_EXECUTION:-false}"
case "${hardware_execution}" in
  true|false) ;;
  *) echo "KSMC_REAL_HARDWARE_EXECUTION must be true or false." >&2; exit 2 ;;
esac
continuous_transfer="${KSMC_CONTINUOUS_TRANSFER:-false}"
case "${continuous_transfer}" in
  true|false) ;;
  *) echo "KSMC_CONTINUOUS_TRANSFER must be true or false." >&2; exit 2 ;;
esac
# Avoid the measured Fast DDS SHM discovery stall in this API process only.
export FASTDDS_BUILTIN_TRANSPORTS="${KSMC_REAL_API_TRANSPORT:-UDPv4}"
exec ros2 run fr5_process_sequences real_robot_api --ros-args -p "enable_hardware_execution:=${hardware_execution}" -p "enable_continuous_transfer:=${continuous_transfer}"
