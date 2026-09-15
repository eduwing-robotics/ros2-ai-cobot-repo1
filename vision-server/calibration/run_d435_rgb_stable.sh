#!/usr/bin/env bash

# Stable RGB-only mode for ChArUco/ArUco calibration and targeting.
# Depth is intentionally disabled; enable it later in the depth-measurement phase.
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"

exec ros2 launch realsense2_camera rs_launch.py \
  rgb_camera.color_profile:=1920x1080x15 \
  enable_depth:=false \
  align_depth.enable:=false \
  reconnect_timeout:=2.0 \
  initial_reset:=true
