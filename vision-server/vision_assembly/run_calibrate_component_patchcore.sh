#!/usr/bin/env bash
set -euo pipefail

KSMC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$KSMC_ROOT/vision_assembly/.venv_patchcore"
export MPLCONFIGDIR="$KSMC_ROOT/runtime/matplotlib"
export HF_HOME="$KSMC_ROOT/runtime/huggingface"
mkdir -p "$MPLCONFIGDIR" "$HF_HOME"
exec "$VENV/bin/python" \
  "$KSMC_ROOT/vision_assembly/inspection/calibrate_component_patchcore.py" "$@"
