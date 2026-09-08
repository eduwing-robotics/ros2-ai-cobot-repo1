#!/usr/bin/env bash
set -euo pipefail

package_root="${KSMC_UNITY_ENDPOINT_ROOT:-/home/juchan-yoon/Ros2UnityEndopoint_PKG_0.1v/Ros2UnityEndopoint_PKG}"
fr5_root="${FR5_ROOT:-/home/juchan-yoon/FR5_robot_control}"
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
ros2 run fairino_hardware_v3_9_7 ros2_cmd_server &
driver_pid=$!

ready=false
for _ in $(seq 1 5); do
  if ! kill -0 "$driver_pid" 2>/dev/null; then
    echo "FAIRINO state server exited during startup." >&2
    wait "$driver_pid"
  fi
  if timeout 6 ros2 topic echo --once /nonrt_state_data >/dev/null 2>&1; then
    ready=true
    break
  fi
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
