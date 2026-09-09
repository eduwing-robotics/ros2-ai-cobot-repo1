#!/usr/bin/env bash
set -euo pipefail
KSMC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 \
  "$KSMC_ROOT/vision_assembly/inspection/prepare_current_normal_dataset.py" \
  "$@"
