#!/usr/bin/env bash
set -euo pipefail

script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fr5_root="${FR5_ROOT:-${script_root}}"
package_root="${KSMC_UNITY_ENDPOINT_ROOT:-${script_root}/../main-server/Ros2UnityEndopoint_PKG}"
fairino_setup="$fr5_root/robot_ws/install/setup.bash"

if [[ ! -f "$fr5_root/scripts/ksmc_env.sh" || ! -f "$fairino_setup" ]]; then
  echo "FR5 workspace not found: $fr5_root" >&2
  echo "Set FR5_ROOT to the FR5_robot_control directory." >&2
  exit 1
fi

set +u
source "$fr5_root/scripts/ksmc_env.sh"
set -u

driver_pid=""
endpoint_pid=""
cleanup() {
  trap - INT TERM EXIT
  if [[ -n "$endpoint_pid" ]] && kill -0 "$endpoint_pid" 2>/dev/null; then
    kill -INT "$endpoint_pid" 2>/dev/null || true
    wait "$endpoint_pid" 2>/dev/null || true
  fi
  if [[ -n "$driver_pid" ]] && kill -0 "$driver_pid" 2>/dev/null; then
    kill -INT "$driver_pid" 2>/dev/null || true
    wait "$driver_pid" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

if ros2 node list --no-daemon --spin-time 2 2>/dev/null | grep -Fxq /fr_command_server; then
  echo "FAIRINO command server is already running; stop it before using this launcher." >&2
  exit 1
fi
if ss -ltn 2>/dev/null | grep -Eq '[:.]10000[[:space:]]'; then
  echo "TCP port 10000 is already in use; stop the existing Unity Endpoint first." >&2
  exit 1
fi

echo "Starting FAIRINO state server (ROS_DOMAIN_ID=$ROS_DOMAIN_ID)..."
# A congested remote DDS send must not hold up local robot-state publication.
# Apply the profile only to the driver child; preserve the endpoint environment.
driver_dds_profile="${KSMC_FAIRINO_DDS_PROFILE:-$fr5_root/config/fairino_fastdds.xml}"
if [[ ! -r "$driver_dds_profile" ]]; then
  echo "FAIRINO DDS profile not readable: $driver_dds_profile" >&2
  exit 1
fi
FASTDDS_BUILTIN_TRANSPORTS=UDPv4 \
FASTRTPS_DEFAULT_PROFILES_FILE="$driver_dds_profile" \
  ros2 run fairino_hardware_v3_9_7 ros2_cmd_server &
driver_pid=$!

ready=false
state_deadline=$((SECONDS + 30))
while (( SECONDS < state_deadline )); do
  if ! kill -0 "$driver_pid" 2>/dev/null; then
    echo "FAIRINO state server exited during startup." >&2
    wait "$driver_pid"
    exit 1
  fi
  remaining=$((state_deadline - SECONDS))
  (( remaining > 0 )) || break
  probe_timeout=$((remaining < 6 ? remaining : 6))
  if timeout "$probe_timeout" ros2 topic echo --once /nonrt_state_data >/dev/null; then
    ready=true
    break
  fi
  # Type discovery may fail immediately before the driver connects.
  # Wait by elapsed time instead of exhausting a fixed number of attempts.
  (( SECONDS >= state_deadline )) || sleep 0.5
done
if [[ "$ready" != true ]]; then
  echo "No /nonrt_state_data received within 30 seconds." >&2
  exit 1
fi
echo "FAIRINO pose stream is ready."

echo "Starting Unity Endpoint on 0.0.0.0:10000..."
ROS_SETUP="$fairino_setup" "$package_root/run.sh" &
endpoint_pid=$!

set +e
wait -n "$driver_pid" "$endpoint_pid"
status=$?
set -e
echo "A managed process stopped; shutting down the integrated launcher." >&2
exit "$status"
