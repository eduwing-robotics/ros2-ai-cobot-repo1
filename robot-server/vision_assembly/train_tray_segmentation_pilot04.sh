#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "${script_dir}/.." && pwd)"

"${repo_dir}/.venv-vision/bin/python" "${script_dir}/scripts/prepare_tray_segmentation_dataset.py" \
  --val-frames 12 --test-frames 0
exec "${repo_dir}/.venv-vision/bin/yolo" segment train \
  model="${script_dir}/models/tray_segmentation/pilot_03/weights/best.pt" \
  data="${script_dir}/datasets/tray_segmentation/yolo/dataset.yaml" \
  epochs=100 imgsz=640 batch=8 device=0 workers=4 patience=30 \
  degrees=180 fliplr=0.5 flipud=0.5 mosaic=0.5 close_mosaic=10 \
  project="${script_dir}/models/tray_segmentation" name=pilot_04 exist_ok=true
