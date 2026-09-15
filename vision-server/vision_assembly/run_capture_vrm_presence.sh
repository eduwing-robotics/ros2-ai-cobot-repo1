#!/usr/bin/env bash
set -Eeo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv="${script_dir}/.venv_patchcore"
if [[ ! -x "${venv}/bin/python" ]]; then
  echo "Missing inspection environment: ${venv}" >&2
  exit 1
fi
exec "${venv}/bin/python" \
  "${script_dir}/slot_classifier/vrm_presence_dataset.py" "$@"
