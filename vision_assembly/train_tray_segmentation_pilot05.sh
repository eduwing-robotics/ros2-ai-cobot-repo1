#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "${script_dir}/.." && pwd)"

"${repo_dir}/.venv-vision/bin/python" "${script_dir}/scripts/prepare_tray_segmentation_dataset.py" \
  --val-frames 15 --test-frames 0
exec "${repo_dir}/.venv-vision/bin/yolo" segment train \
  model="${script_dir}/models/tray_segmentation/pilot_04/weights/best.pt" \
  data="${script_dir}/datasets/tray_segmentation/yolo/dataset.yaml" \
  epochs=50 imgsz=640 batch=8 device=0 workers=4 patience=15 \
  degrees=180 fliplr=0.5 flipud=0.5 mosaic=0.35 close_mosaic=8 \
  project="${script_dir}/models/tray_segmentation" name=pilot_05 exist_ok=true
