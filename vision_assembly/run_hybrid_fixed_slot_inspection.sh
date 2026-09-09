#!/usr/bin/env bash
set -Eeo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv="${script_dir}/.venv_patchcore"
if [[ ! -x "${venv}/bin/python" ]]; then
  echo "Missing Anomalib environment: ${venv}" >&2
  exit 1
fi
export MPLCONFIGDIR="${script_dir}/hybrid_inspection/.matplotlib"
export HF_HUB_OFFLINE=1
mkdir -p "${MPLCONFIGDIR}"
exec "${venv}/bin/python" \
  "${script_dir}/hybrid_inspection/main.py" "$@"
