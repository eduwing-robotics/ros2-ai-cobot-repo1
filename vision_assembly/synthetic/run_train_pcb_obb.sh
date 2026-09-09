#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv="${script_dir}/../.venv_obb"
if [[ ! -x "${venv}/bin/python" ]]; then
  echo "Missing OBB environment: ${venv}" >&2
  exit 1
fi
export MPLCONFIGDIR="${script_dir}/.matplotlib"
mkdir -p "${MPLCONFIGDIR}"
exec "${venv}/bin/python" "${script_dir}/train_pcb_obb.py" "$@"
