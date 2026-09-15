#!/usr/bin/env bash
set -Eeo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv="${script_dir}/.venv_obb"
if [[ ! -x "${venv}/bin/python" ]]; then
  echo "Missing YOLO environment: ${venv}" >&2
  exit 1
fi
export MPLCONFIGDIR="${script_dir}/segmentation/.matplotlib"
mkdir -p "${MPLCONFIGDIR}"
exec "${venv}/bin/python" \
  "${script_dir}/segmentation/predict_s22_parts_seg.py" "$@"
