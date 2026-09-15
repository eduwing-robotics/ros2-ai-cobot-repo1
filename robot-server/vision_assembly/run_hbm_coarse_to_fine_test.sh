#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "${script_dir}/.." && pwd)"
source "${repo_dir}/scripts/ksmc_env.sh"
exec python3 "${script_dir}/scripts/run_hbm_coarse_to_fine_test.py" "$@"
