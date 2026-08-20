#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../scripts/ksmc_env.sh"
exec python3 "$SCRIPT_DIR/scripts/capture_charuco_handeye_sample.py" "$@"
