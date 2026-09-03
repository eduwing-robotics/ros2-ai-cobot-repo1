#!/usr/bin/env bash

# Calibrated high-resolution RGB-D profile for the SMD close-view workflow.
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"

exec ros2 launch realsense2_camera rs_launch.py \
  rgb_camera.color_profile:=1920x1080x15 \
  enable_depth:=true \
  depth_module.depth_profile:=1280x720x15 \
  enable_sync:=true \
  align_depth.enable:=true \
  pointcloud.enable:=false \
  reconnect_timeout:=2.0 \
  initial_reset:=true
