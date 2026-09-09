#!/usr/bin/env bash
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source /opt/ros/jazzy/setup.bash
exec python3 "${script_dir}/obb/capture_gpu_obb_images.py" "$@"
