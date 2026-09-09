#!/usr/bin/env bash
set -Eeo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${project_dir}/camera2_scrcpy/capture_optical_inspection.sh" "$@"
