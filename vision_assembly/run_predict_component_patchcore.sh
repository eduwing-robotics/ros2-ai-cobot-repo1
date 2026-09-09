#!/usr/bin/env bash
set -euo pipefail

KSMC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$KSMC_ROOT/vision_assembly/.venv_patchcore"
if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Missing PatchCore environment: $VENV" >&2
  exit 1
fi
export MPLCONFIGDIR="$KSMC_ROOT/runtime/matplotlib"
export HF_HOME="$KSMC_ROOT/runtime/huggingface"
mkdir -p "$MPLCONFIGDIR" "$HF_HOME"
exec "$VENV/bin/python" \
  "$KSMC_ROOT/vision_assembly/inspection/predict_component_patchcore.py" \
  "$@"
