#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source scripts/ksmc_env.sh
exec python3 vision_assembly/scripts/assembly_api_client.py --recover "$@"
