#!/usr/bin/env bash
# Common portable environment for KSMC launch scripts.

KSMC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export KSMC_ROOT
ksmc_had_nounset=0
case "$-" in
  *u*) ksmc_had_nounset=1 ;;
esac

if [[ -f "${KSMC_ROOT}/config/ksmc.env" ]]; then
  # Device-specific values are intentionally kept outside Git.
  source "${KSMC_ROOT}/config/ksmc.env"
fi

# Opt-in host-specific Fast DDS transport profile. Preserve explicit caller
# profiles; other RMW implementations ignore these Fast DDS variables.
if [[ -n "${KSMC_FASTDDS_PROFILE:-}" ]]; then
  if [[ ! -r "${KSMC_FASTDDS_PROFILE}" ]]; then
    echo "Unreadable KSMC_FASTDDS_PROFILE" >&2
    return 1 2>/dev/null || exit 1
  fi
  export FASTRTPS_DEFAULT_PROFILES_FILE="${FASTRTPS_DEFAULT_PROFILES_FILE:-${KSMC_FASTDDS_PROFILE}}"
fi

# The cell is validated with Fast DDS. Respect an explicitly selected RMW,
# otherwise make sure the transport profile above is actually consumed by all
# ROS launchers (camera, ROI, controller and inspection API).
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-5}"
# This workspace is a multi-PC cell. Make the intended network discovery mode
# explicit so a shell profile inherited from a local-only ROS test cannot make
# the camera topics appear in `ros2 topic list` while delivering no frames to
# the other computers. Callers can still opt into localhost-only diagnostics by
# exporting ROS_LOCALHOST_ONLY=1 before sourcing this file.
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export ROS_AUTOMATIC_DISCOVERY_RANGE="${ROS_AUTOMATIC_DISCOVERY_RANGE:-SUBNET}"
export ROS_LOG_DIR="${ROS_LOG_DIR:-${KSMC_ROOT}/runtime/log}"
mkdir -p "${ROS_LOG_DIR}"

ros_distro="${KSMC_ROS_DISTRO:-jazzy}"
ros_setup="/opt/ros/${ros_distro}/setup.bash"
if [[ ! -f "${ros_setup}" ]]; then
  echo "Missing ROS 2 setup: ${ros_setup}" >&2
  return 1 2>/dev/null || exit 1
fi

set +u
source "${ros_setup}"
for overlay in \
  "${KSMC_ROOT}/robot_ws/install/setup.bash" \
  "${KSMC_ROOT}/ros2_ws/install/setup.bash"; do
  if [[ -f "${overlay}" ]]; then
    source "${overlay}"
  fi
done
if ((ksmc_had_nounset)); then
  set -u
else
  set +u
fi
unset ksmc_had_nounset ros_distro ros_setup overlay
