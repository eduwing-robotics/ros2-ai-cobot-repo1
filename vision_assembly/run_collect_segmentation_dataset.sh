#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"

tracker_pid=""
cleanup() {
  if [[ -n "${tracker_pid}" ]] && kill -0 "${tracker_pid}" 2>/dev/null; then
    kill -INT "${tracker_pid}" 2>/dev/null || true
    wait "${tracker_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if ! ros2 topic list 2>/dev/null | grep -qx '/vision/tray/registration'; then
  python3 "${script_dir}/scripts/view_tray_sections.py" --registration-only &
  tracker_pid=$!
fi

python3 "${script_dir}/scripts/collect_tray_segmentation_dataset.py" "$@"
