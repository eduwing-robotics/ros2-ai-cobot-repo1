#!/usr/bin/env bash
set -Eeo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" != "--help" && "${1:-}" != "-h" ]]; then
  source "${project_dir}/scripts/ksmc_env.sh"
  source "${project_dir}/scripts/vision_api_env.sh"
fi
exec python3 "${project_dir}/vision_assembly/integration/server_bundle.py" "$@"
