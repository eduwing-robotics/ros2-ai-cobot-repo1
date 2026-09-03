#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "${script_dir}/.." && pwd)"

exec "${repo_dir}/.venv-vision/bin/yolo" segment train \
  model="${script_dir}/models/tray_segmentation/pilot_05/weights/best.pt" \
  data="${script_dir}/datasets/tray_segmentation/yolo/dataset.yaml" \
  epochs=30 imgsz=960 batch=4 device=0 workers=4 patience=10 \
  degrees=8 translate=0.06 scale=0.25 flipud=0.0 fliplr=0.5 mosaic=0.20 close_mosaic=5 \
  project="${script_dir}/models/tray_segmentation" name=pilot_06 exist_ok=true
