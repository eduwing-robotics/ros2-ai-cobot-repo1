#!/usr/bin/env bash

# Low-latency operator preview for positioning the eye-in-hand camera.
# Do not use this profile for calibrated 1920x1080 targeting or final grasp poses.
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"

exec ros2 launch realsense2_camera rs_launch.py \
  rgb_camera.color_profile:=1280x720x30 \
  enable_depth:=false \
  align_depth.enable:=false \
  enable_sync:=false \
  pointcloud.enable:=false \
  reconnect_timeout:=2.0 \
  initial_reset:=false
