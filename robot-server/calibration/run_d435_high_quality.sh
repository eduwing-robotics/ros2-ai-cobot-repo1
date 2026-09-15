#!/usr/bin/env bash
# Validated assembly RGB-D profile; run one camera process at a time.
set -eo pipefail
precision_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROS_LOG_DIR="${precision_root}/runtime/log"
source /home/juchan-yoon/FR5_robot_control/scripts/ksmc_env.sh
exec ros2 launch realsense2_camera rs_launch.py \
  rgb_camera.color_profile:=1280x720x15 \
  enable_depth:=true \
  depth_module.depth_profile:=1280x720x15 \
  enable_sync:=true \
  align_depth.enable:=true \
  pointcloud.enable:=false \
  reconnect_timeout:=2.0 \
  initial_reset:=false
