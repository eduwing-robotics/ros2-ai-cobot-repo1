#!/usr/bin/env bash
set -Eeo pipefail

# After assembly is confirmed complete, move that PCB to the downstream
# S22 stop line (vision-inspection station). This never auto-starts itself.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "${PROJECT_DIR}/run_conveyor_auto_stop.sh" --station inspection "$@"
