#!/usr/bin/env bash

set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"
exec python3 "${script_dir}/scripts/capture_charuco_intrinsic_image.py" "$@"
