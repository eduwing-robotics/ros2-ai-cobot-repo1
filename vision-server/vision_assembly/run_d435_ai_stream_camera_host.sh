#!/usr/bin/env bash
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runtime_dir="${script_dir}/../runtime"
source "${script_dir}/../scripts/ksmc_env.sh"
export ROS_LOG_DIR="${ROS_LOG_DIR:-${runtime_dir}/ros_log}"
mkdir -p "${ROS_LOG_DIR}"

# Keep one relay only. Duplicate JPEG encoders waste CPU and network bandwidth.
lock_file="${runtime_dir}/d435_ai_stream.lock"
exec 9>"${lock_file}"
if ! flock -n 9; then
  echo '[D435 AI Stream] Another camera-host relay is already running.' >&2
  exit 1
fi

remote_fps="${D435_REMOTE_FPS:-15}"
remote_jpeg_quality="${D435_REMOTE_JPEG_QUALITY:-92}"

echo '[D435 AI Stream] Run this ONLY on the computer physically connected to D435.'
echo "[D435 AI Stream] ROS_DOMAIN_ID=${ROS_DOMAIN_ID}"
echo '[D435 AI Stream] Local inspection stays on raw RGB-D; this is the remote high-quality stream.'
echo "[D435 AI Stream] 1920x1080 target, ${remote_fps} FPS, JPEG ${remote_jpeg_quality}"
echo '[D435 AI Stream] Output: /camera/camera/color/image_ai/compressed'
exec python3 \
  "${script_dir}/../ros2_ws/src/vision_server/vision_server/d435_ai_stream.py" \
  --ros-args \
  -p input_topic:=/camera/camera/color/image_raw \
  -p output_topic:=/camera/camera/color/image_ai/compressed \
  -p max_fps:="${remote_fps}" \
  -p jpeg_quality:="${remote_jpeg_quality}"
