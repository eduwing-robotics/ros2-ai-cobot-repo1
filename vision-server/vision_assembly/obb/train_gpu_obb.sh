#!/usr/bin/env bash
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv="${script_dir}/../.venv_obb"
if [[ ! -x "${venv}/bin/yolo" ]]; then
  echo "Missing ${venv}. Run install_obb_env.sh first." >&2
  exit 1
fi
export MPLCONFIGDIR="${script_dir}/.matplotlib"
mkdir -p "${MPLCONFIGDIR}"
exec "${venv}/bin/python" "${script_dir}/train_gpu_obb.py" "$@"
