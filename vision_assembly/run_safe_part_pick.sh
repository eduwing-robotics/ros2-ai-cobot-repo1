#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "${script_dir}/.." && pwd)"
source "${repo_dir}/scripts/ksmc_env.sh"
exec "${repo_dir}/.venv-vision/bin/python" "${script_dir}/scripts/safe_part_pick.py" "$@"
