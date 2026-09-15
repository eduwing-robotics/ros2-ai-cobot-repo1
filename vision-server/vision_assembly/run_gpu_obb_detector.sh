#!/usr/bin/env bash
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source /opt/ros/jazzy/setup.bash
source "${script_dir}/../ros2_ws/install/setup.bash"
export MPLCONFIGDIR="${script_dir}/obb/.matplotlib"
mkdir -p "${MPLCONFIGDIR}"
camera_config="${script_dir}/../ros2_ws/src/vision_server/config/cameras_gpu_obb.yaml"
if [[ "${GPU_OBB_USE_DEPTH:-0}" == "1" ]]; then
  camera_config="${script_dir}/../ros2_ws/src/vision_server/config/cameras_gpu_obb_rgbd.yaml"
  echo '[GPU OBB] RGB-D mode: remote aligned depth will also be subscribed.'
else
  echo '[GPU OBB] RGB-only mode: no remote raw depth subscription.'
fi
exec "${script_dir}/.venv_obb/bin/python" -c \
  'from vision_server.part_detector import main; main()' \
  --ros-args \
  -p camera_config:="${camera_config}" \
  -p yolo_config:="${script_dir}/../ros2_ws/src/vision_server/config/gpu_obb.yaml" "$@"
