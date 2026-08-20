#!/usr/bin/env bash
set -Eeo pipefail

# Move one PCB to the first S22 stop line (assembly station).
# Requires run_s22_conveyor.sh and TurtleBot bringup to already be running.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "${PROJECT_DIR}/run_conveyor_auto_stop.sh" --station assembly "$@"
