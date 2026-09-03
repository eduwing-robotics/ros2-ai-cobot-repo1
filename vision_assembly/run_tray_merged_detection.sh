#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"

smd_set_index="${KSMC_SMD_SET_INDEX:-1}"
case "${smd_set_index}" in
  1|2) ;;
  *) echo "KSMC_SMD_SET_INDEX must be 1 or 2" >&2; exit 2 ;;
esac

section_pid=""
renderer_pid=""
smd_pid=""
cleanup() {
  if [[ -n "${smd_pid}" ]] && kill -0 "${smd_pid}" 2>/dev/null; then
    kill -INT "${smd_pid}" 2>/dev/null || true
    wait "${smd_pid}" 2>/dev/null || true
  fi
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

"${script_dir}/../.venv-vision/bin/python" -u "${script_dir}/scripts/detect_smd_close_live.py" \
  --set-index "${smd_set_index}" &
smd_pid=$!

exec "${script_dir}/../.venv-vision/bin/python" -u \
  "${script_dir}/scripts/detect_tray_parts.py" --process-hz 2.0 --display-hz 0 --output-topic /vision/tray/detector_debug_image/compressed --overlay-hold-frames 5 --count-smoothing-frames 7 "$@"
