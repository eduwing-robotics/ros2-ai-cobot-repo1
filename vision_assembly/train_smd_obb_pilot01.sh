#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "${script_dir}/.." && pwd)"

exec "${repo_dir}/.venv-vision/bin/yolo" obb train \
  model=yolo11n-obb.pt \
  data="${script_dir}/datasets/smd_obb/dataset.yaml" \
  epochs=80 imgsz=960 batch=4 device=0 workers=4 patience=15 \
  degrees=18 translate=0.05 scale=0.20 flipud=0.0 fliplr=0.5 mosaic=0.10 close_mosaic=8 \
  project="${script_dir}/models/smd_obb" name=pilot_01 exist_ok=true
