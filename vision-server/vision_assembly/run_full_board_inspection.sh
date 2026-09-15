#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 \
  "${project_dir}/vision_assembly/inspection/full_board_inspector.py" \
  "$@"
