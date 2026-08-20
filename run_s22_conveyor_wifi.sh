#!/usr/bin/env bash
set -Eeo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CAMERA_MODE=wifi
exec "${PROJECT_DIR}/run_s22_conveyor.sh" "$@"
