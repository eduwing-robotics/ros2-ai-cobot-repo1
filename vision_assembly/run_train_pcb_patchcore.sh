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
  "$KSMC_ROOT/vision_assembly/inspection/train_pcb_patchcore.py" \
  --dataset "$KSMC_ROOT/vision_assembly/inspection/datasets/pcb_anomaly_v1" \
  --output "$KSMC_ROOT/runtime/inspection/patchcore/pcb_anomaly_v1" \
  "$@"
