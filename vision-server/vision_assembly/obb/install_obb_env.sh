#!/usr/bin/env bash
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv="${script_dir}/../.venv_obb"
python3 -m venv --system-site-packages "${venv}"
"${venv}/bin/python" -m pip install --upgrade pip
"${venv}/bin/python" -m pip install \
  'numpy>=1.26,<2' \
  'opencv-python>=4.8,<4.12' \
  'matplotlib>=3.8' \
  'setuptools>=77,<80' \
  ultralytics
"${venv}/bin/python" -m pip install --no-deps 'nvidia-cudnn-cu13==9.24.0.43'
"${venv}/bin/python" -c 'from ultralytics import YOLO; import torch; print("Ultralytics OK; CUDA:", torch.cuda.is_available())'
