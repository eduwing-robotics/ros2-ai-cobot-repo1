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
production_assembly="${KSMC_PRODUCTION_ASSEMBLY:-false}"
case "${production_assembly}" in
  true|false) ;;
  *) echo "KSMC_PRODUCTION_ASSEMBLY must be true or false." >&2; exit 2 ;;
esac
boundary_pause="${KSMC_WHOLE_CYCLE_BOUNDARY_PAUSE:-false}"
case "${boundary_pause}" in
  true|false) ;;
  *) echo "KSMC_WHOLE_CYCLE_BOUNDARY_PAUSE must be true or false." >&2; exit 2 ;;
esac
# Avoid the measured Fast DDS SHM discovery stall in this API process only.
export FASTDDS_BUILTIN_TRANSPORTS="${KSMC_REAL_API_TRANSPORT:-UDPv4}"
# Status/event sends must not block the executor that receives robot feedback.
api_dds_profile="${KSMC_REAL_API_DDS_PROFILE:-$root/config/fairino_fastdds.xml}"
if [[ ! -r "$api_dds_profile" ]]; then
  echo "Robot API DDS profile not readable: $api_dds_profile" >&2
  exit 1
fi
export FASTRTPS_DEFAULT_PROFILES_FILE="$api_dds_profile"
exec ros2 run fr5_process_sequences real_robot_api --ros-args -p "enable_hardware_execution:=${hardware_execution}" -p "enable_continuous_transfer:=${continuous_transfer}" -p "enable_production_assembly:=${production_assembly}" -p "enable_whole_cycle_pause:=${boundary_pause}" -p "whole_cycle_boundary_pause:=${boundary_pause}"
