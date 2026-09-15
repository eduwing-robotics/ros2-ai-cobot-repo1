#!/usr/bin/env bash
set -Eeo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${project_dir}/scripts/ksmc_env.sh"

exec python3 \
  "${project_dir}/vision_assembly/inspection/capture_conveyor_dataset_once.py" \
  "$@"
