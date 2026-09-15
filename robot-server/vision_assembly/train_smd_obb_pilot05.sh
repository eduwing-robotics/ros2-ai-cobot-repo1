#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "${script_dir}/.." && pwd)"

# Only consistently elongated, terminal-inclusive labels are used here.  Full
# rotation augmentation transfers the real-camera appearance to arbitrary SMD
# orientations without mixing in the legacy square-body annotations.
exec "${repo_dir}/.venv-vision/bin/yolo" obb train \
  model="${repo_dir}/yolo11n-obb.pt" \
  data="${script_dir}/datasets/smd_obb_pilot05.yaml" \
  epochs=120 imgsz=960 batch=4 device=0 workers=4 patience=30 \
  degrees=180 translate=0.05 scale=0.25 flipud=0.5 fliplr=0.5 \
  mosaic=0.10 close_mosaic=10 \
  project="${script_dir}/models/smd_obb" name=pilot_05 exist_ok=false
