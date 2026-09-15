#!/usr/bin/env bash
set -Eeo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${script_dir}/segmentation/build_s22_seg_dataset.py" "$@"
