#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$root/vision_assembly/scripts/fixed_cycle_snapshot.py" "$@"
