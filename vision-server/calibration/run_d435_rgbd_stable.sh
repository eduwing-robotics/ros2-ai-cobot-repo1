#!/usr/bin/env bash

# RGB-D mode for part localization. Color remains 1920x1080x15 so the same
# color CameraInfo/Hand-Eye contract is used; depth is aligned to color.
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"
config_file="${script_dir}/config/d435_rgbd_minimal.yaml"

exec ros2 launch realsense2_camera rs_launch.py \
  config_file:="${config_file}" \
  rgb_camera.color_profile:=1920x1080x15 \
  enable_depth:=true \
  enable_infra:=false \
  enable_infra1:=false \
  enable_infra2:=false \
  enable_rgbd:=false \
  enable_gyro:=false \
  enable_accel:=false \
  enable_motion:=false \
  depth_module.depth_profile:=1280x720x15 \
  enable_sync:=true \
  align_depth.enable:=true \
  pointcloud.enable:=false \
  reconnect_timeout:=2.0 \
  initial_reset:=true
