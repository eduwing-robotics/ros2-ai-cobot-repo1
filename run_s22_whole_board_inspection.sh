#!/usr/bin/env bash
set -Eeo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${project_dir}/run_s22_component_patchcore_inspection.sh" "$@"
