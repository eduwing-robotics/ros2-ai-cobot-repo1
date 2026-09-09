#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Some chat/terminal copy paths preserve indentation as part of an argument.
# Normalize only outer whitespace; option values themselves are unchanged.
forward_args=()
for arg in "$@"; do
  arg="${arg#"${arg%%[![:space:]]*}"}"
  arg="${arg%"${arg##*[![:space:]]}"}"
  forward_args+=("${arg}")
done

exec "${script_dir}/run_pick_smd_with_gripper_camera.sh" \
  --approach-only \
  --approach-offset-mm 50 \
  --xy-speed-percent 20 \
  --vertical-speed-percent 15 \
  --rotation-speed-percent 20 \
  "${forward_args[@]}"
