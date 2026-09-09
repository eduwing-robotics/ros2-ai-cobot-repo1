#!/usr/bin/env bash
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runtime_dir="${script_dir}/../runtime"
pid_file="${runtime_dir}/parts_obb_detector.pid"
node_pid=''
mkdir -p "${runtime_dir}" "${script_dir}/obb/.matplotlib"

cleanup() {
  exit_code=$?
  trap - EXIT INT TERM
  if [[ -n "${node_pid}" ]] && kill -0 "${node_pid}" 2>/dev/null; then
    # The Python node owns a separate process group. Give rclpy a chance to
    # destroy publishers/subscriptions before escalating to SIGTERM.
    kill -INT -- "-${node_pid}" 2>/dev/null || kill -INT "${node_pid}" 2>/dev/null || true
    for _ in {1..50}; do
      kill -0 "${node_pid}" 2>/dev/null || break
      sleep 0.1
    done
    if kill -0 "${node_pid}" 2>/dev/null; then
      kill -TERM -- "-${node_pid}" 2>/dev/null || kill -TERM "${node_pid}" 2>/dev/null || true
    fi
    wait "${node_pid}" 2>/dev/null || true
  fi
  if [[ -f "${pid_file}" ]] && [[ "$(<"${pid_file}")" == "${node_pid}" ]]; then
    rm -f "${pid_file}"
  fi
  exit "${exit_code}"
}

if [[ -f "${pid_file}" ]]; then
  old_pid="$(<"${pid_file}")"
  if kill -0 "${old_pid}" 2>/dev/null; then
    echo "Parts OBB detector is already running (node PID ${old_pid})." >&2
    exit 1
  fi
  rm -f "${pid_file}"
fi
trap cleanup EXIT INT TERM
source /opt/ros/jazzy/setup.bash
source "${script_dir}/../ros2_ws/install/setup.bash"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-5}"
export ROS_LOG_DIR="${ROS_LOG_DIR:-${runtime_dir}/ros_log}"
mkdir -p "${ROS_LOG_DIR}"
export MPLCONFIGDIR="${script_dir}/obb/.matplotlib"
relay_camera_config="${script_dir}/../ros2_ws/src/vision_server/config/cameras_gpu_obb.yaml"
direct_camera_config="${script_dir}/../ros2_ws/src/vision_server/config/cameras_gpu_obb_direct.yaml"
yolo_config="${script_dir}/../ros2_ws/src/vision_server/config/parts_obb_preview.yaml"

# Prefer the camera-host relay because it limits the network stream before the
# image reaches this computer.  Keep a direct compressed-topic fallback so the
# detector still produces an image when the relay has not been started yet.
ros_nodes="$(timeout 3 ros2 node list 2>/dev/null || true)"
if printf '%s\n' "${ros_nodes}" | rg -q '^/d435_ai_stream(?:_[0-9]+)?$'; then
  camera_config="${relay_camera_config}"
  input_topic='/camera/camera/color/image_ai/compressed'
  input_mode='camera-host relay (optimized)'
else
  camera_config="${direct_camera_config}"
  input_topic='/camera/camera/color/image_raw/compressed'
  input_mode='direct compressed fallback'
fi

echo '[Parts OBB] GPU, HBM, Power Module, VRM, Inductor preview model'
echo "[Parts OBB] ROS_DOMAIN_ID=${ROS_DOMAIN_ID}"
echo "[Parts OBB] Input: ${input_topic} (${input_mode})"
if [[ "${input_mode}" == 'direct compressed fallback' ]]; then
  echo '[Parts OBB] Relay not found. The screen will work, but network load may be higher.'
  echo '[Parts OBB] For optimized transfer, run this on the D435 computer first:'
  echo '            ~/KSMC/vision_assembly/run_d435_ai_stream_camera_host.sh'
fi
echo '[Parts OBB] View: /vision/parts_obb/image/compressed'
setsid "${script_dir}/.venv_obb/bin/python" -c \
  'from vision_server.part_detector import main; main()' \
  --ros-args \
  -r __node:=parts_obb_detector \
  -p camera_config:="${camera_config}" \
  -p yolo_config:="${yolo_config}" "$@" &
node_pid=$!
echo "${node_pid}" > "${pid_file}"
wait "${node_pid}"
