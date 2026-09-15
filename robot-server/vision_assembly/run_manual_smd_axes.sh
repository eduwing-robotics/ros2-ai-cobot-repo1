#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"

set_index="${KSMC_SMD_SET_INDEX:-1}"
exec "${script_dir}/../.venv-vision/bin/python" -u \
  "${script_dir}/scripts/manual_set_smd_axes.py" \
  --set-index "${set_index}" "$@"
