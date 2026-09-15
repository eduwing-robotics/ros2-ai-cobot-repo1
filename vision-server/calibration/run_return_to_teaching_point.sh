#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"

exec python3 "${script_dir}/scripts/return_to_teaching_point.py" "$@"
