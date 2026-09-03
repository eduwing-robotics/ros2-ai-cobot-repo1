#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
source "$root/scripts/ksmc_env.sh"
exec python3 "$root/vision_assembly/scripts/execute_cached_hbm_remaining.py" "$@"
