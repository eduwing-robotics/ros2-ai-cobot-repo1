#!/usr/bin/env bash
set -Eeo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_bin="${script_dir}/.venv_obb/bin/python"
if [[ ! -x "${python_bin}" ]]; then
  python_bin="python3"
fi
exec "${python_bin}" "${script_dir}/segmentation/label_s22_parts_seg.py" "$@"
