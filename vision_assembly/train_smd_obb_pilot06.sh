#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "${script_dir}/.." && pwd)"

exec "${repo_dir}/.venv-vision/bin/yolo" obb train \
  model="${script_dir}/models/smd_obb/pilot_05/weights/best.pt" \
  data="${script_dir}/datasets/smd_obb_pilot06.yaml" \
  epochs=100 imgsz=960 batch=4 device=0 workers=4 patience=25 \
  lr0=0.002 degrees=180 translate=0.05 scale=0.25 flipud=0.5 fliplr=0.5 \
  mosaic=0.10 close_mosaic=10 \
  project="${script_dir}/models/smd_obb" name=pilot_06 exist_ok=false
