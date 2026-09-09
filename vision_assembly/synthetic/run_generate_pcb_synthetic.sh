#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec blender -b --factory-startup \
  --python "$SCRIPT_DIR/scripts/generate_pcb_obb_dataset.py" -- "$@"
