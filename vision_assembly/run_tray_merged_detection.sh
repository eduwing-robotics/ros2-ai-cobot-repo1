#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"

section_pid=""
renderer_pid=""
cleanup() {
  if [[ -n "${renderer_pid}" ]] && kill -0 "${renderer_pid}" 2>/dev/null; then
    kill -INT "${renderer_pid}" 2>/dev/null || true
    wait "${renderer_pid}" 2>/dev/null || true
  fi
  if [[ -n "${section_pid}" ]] && kill -0 "${section_pid}" 2>/dev/null; then
    kill -INT "${section_pid}" 2>/dev/null || true
    wait "${section_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

python3 "${script_dir}/scripts/view_tray_sections.py" --registration-only &
section_pid=$!

python3 "${script_dir}/scripts/render_tray_live.py" &
renderer_pid=$!

exec "${script_dir}/../.venv-vision/bin/python" -u \
  "${script_dir}/scripts/detect_tray_parts.py" --process-hz 2.0 --display-hz 0 --overlay-hold-frames 1 --count-smoothing-frames 3 "$@"
