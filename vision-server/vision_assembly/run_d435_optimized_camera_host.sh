#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runtime_dir="${script_dir}/../runtime"
source "${script_dir}/../scripts/ksmc_env.sh"
mkdir -p "${runtime_dir}" "${ROS_LOG_DIR}"

lock_file="${runtime_dir}/d435_optimized_camera_host.lock"
exec 8>"${lock_file}"
if ! flock -n 8; then
  echo '[D435 Optimized] The integrated D435 launcher is already running.' >&2
  exit 1
fi

camera_pid=''
relay_pid=''

stop_group() {
  local pid="$1"
  [[ -n "${pid}" ]] || return 0
  kill -0 "${pid}" 2>/dev/null || return 0
  kill -INT -- "-${pid}" 2>/dev/null || kill -INT "${pid}" 2>/dev/null || true
  for _attempt in {1..40}; do
    kill -0 "${pid}" 2>/dev/null || return 0
    sleep 0.1
  done
  kill -TERM -- "-${pid}" 2>/dev/null || kill -TERM "${pid}" 2>/dev/null || true
}

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  stop_group "${relay_pid}"
  stop_group "${camera_pid}"
  [[ -z "${relay_pid}" ]] || wait "${relay_pid}" 2>/dev/null || true
  [[ -z "${camera_pid}" ]] || wait "${camera_pid}" 2>/dev/null || true
  exit "${status}"
}
trap cleanup EXIT INT TERM

echo '[D435 Optimized] Camera host mode'
echo "[D435 Optimized] ROS_DOMAIN_ID=${ROS_DOMAIN_ID}"
echo '[D435 Optimized] Starting 1920x1080x15 RGB + aligned depth...'
setsid "${script_dir}/../calibration/run_d435_rgbd_stable.sh" &
camera_pid=$!

camera_ready=0
for _attempt in {1..25}; do
  if ! kill -0 "${camera_pid}" 2>/dev/null; then
    echo '[D435 Optimized] RealSense process stopped during startup.' >&2
    exit 1
  fi
  if timeout 2 ros2 topic echo \
    /camera/camera/color/image_raw \
    --once --qos-reliability best_effort >/dev/null 2>&1; then
    camera_ready=1
    break
  fi
  sleep 0.5
done

if [[ "${camera_ready}" -ne 1 ]]; then
  echo '[D435 Optimized] No D435 color frame received within the startup timeout.' >&2
  exit 1
fi

echo '[D435 Optimized] Starting latest-frame high-quality network relay...'
setsid "${script_dir}/run_d435_ai_stream_camera_host.sh" &
relay_pid=$!

echo '[D435 Optimized] Local precision inputs:'
echo '  /camera/camera/color/image_raw'
echo '  /camera/camera/aligned_depth_to_color/image_raw'
echo '[D435 Optimized] Remote viewer/AI input:'
echo '  /camera/camera/color/image_ai/compressed'
echo '[D435 Optimized] Ctrl+C stops both the D435 and relay cleanly.'

wait -n "${camera_pid}" "${relay_pid}"
echo '[D435 Optimized] A required process stopped; shutting down the other process.' >&2
exit 1
