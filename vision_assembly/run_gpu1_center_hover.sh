#!/usr/bin/env bash
# Compatibility shortcut: refresh GPU #1 and stop exactly 50 mm above it.
set -eo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${script_dir}/run_tray_part_hover_5cm.sh" \
  --part-type gpu \
  --instance 1 \
  "$@"
