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

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-5}"
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
