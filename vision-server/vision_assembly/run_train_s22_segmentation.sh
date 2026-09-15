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
for arg in "$@"; do
  if [[ "${arg}" == "--help" ]] || [[ "${arg}" == "-h" ]]; then
    exec "${venv}/bin/python" \
      "${script_dir}/segmentation/train_s22_parts_seg.py" --help
  fi
done
"${script_dir}/run_build_s22_segmentation_dataset.sh"
cd "${script_dir}/.."
exec "${venv}/bin/python" \
  "${script_dir}/segmentation/train_s22_parts_seg.py" "$@"
