#!/usr/bin/env bash
set -Eeo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${script_dir}/.venv_patchcore/bin/python" \
  "${script_dir}/slot_classifier/train_component_presence_classifiers.py" "$@"
