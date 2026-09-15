#!/usr/bin/env bash
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${script_dir}/obb/label_gpu_obb.py" "$@"
