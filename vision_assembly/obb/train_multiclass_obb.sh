#!/usr/bin/env bash
set -eo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${SCRIPT_DIR}/../.venv_obb"
if [[ ! -x "${VENV}/bin/python" ]]; then
  echo "Missing ${VENV}. Run install_obb_env.sh first." >&2
  exit 1
fi
export MPLCONFIGDIR="${SCRIPT_DIR}/.matplotlib"
mkdir -p "${MPLCONFIGDIR}"
"${VENV}/bin/python" "$SCRIPT_DIR/build_multiclass_dataset.py"
exec "${VENV}/bin/python" "$SCRIPT_DIR/train_multiclass_obb.py" "$@"
