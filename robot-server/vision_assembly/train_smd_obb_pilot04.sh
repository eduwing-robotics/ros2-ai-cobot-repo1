#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "${script_dir}/.." && pwd)"

exec "${repo_dir}/.venv-vision/bin/yolo" obb train \
  model="${script_dir}/models/smd_obb/pilot_03/weights/best.pt" \
  data="${script_dir}/datasets/smd_obb_pilot04.yaml" \
  epochs=80 imgsz=960 batch=4 device=0 workers=4 patience=20 \
  degrees=45 translate=0.04 scale=0.20 flipud=0.0 fliplr=0.5 mosaic=0.05 close_mosaic=8 \
  project="${script_dir}/models/smd_obb" name=pilot_04 exist_ok=false
