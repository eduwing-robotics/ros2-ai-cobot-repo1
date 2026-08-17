#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../scripts/ksmc_env.sh"

set -u
export PYTHONPATH="$SCRIPT_DIR/third_party/open_gopro_multi_webcam${PYTHONPATH:+:$PYTHONPATH}"

exec python3 "$SCRIPT_DIR/notebooks/gopro_camera3_node.py" 198
