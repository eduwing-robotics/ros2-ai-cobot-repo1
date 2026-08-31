#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${script_dir}/../.venv-vision/bin/python" \
  "${script_dir}/scripts/annotate_tray_parts_with_sam.py" "$@"
