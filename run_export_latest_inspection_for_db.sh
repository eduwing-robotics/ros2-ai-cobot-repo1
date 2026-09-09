#!/usr/bin/env bash
set -Eeo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 \
  "${project_dir}/vision_assembly/integration/export_inspection_result.py" "$@"

