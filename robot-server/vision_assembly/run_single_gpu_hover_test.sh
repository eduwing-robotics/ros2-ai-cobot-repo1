#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "${script_dir}/.." && pwd)"
source "${repo_dir}/scripts/ksmc_env.sh"

execute=0
confirm=0
for arg in "$@"; do
  [[ "${arg}" == "--execute" ]] && execute=1
  [[ "${arg}" == "--confirm-hover" ]] && confirm=1
done
if [[ "${execute}" -ne "${confirm}" ]]; then
  echo "Actual hover requires both --execute and --confirm-hover" >&2
  exit 2
fi

target="${script_dir}/data/gpu_hover_target.json"
python3 "${script_dir}/scripts/capture_single_vrm_hover_target.py" \
  --part-type gpu --display-name GPU --output "${target}"

move=(
  "${repo_dir}/calibration/run_object_approach.sh"
  --target-file "${target}"
  --approach-offset-mm 100
  --align-part --gripper-axis tool_y
  --speed-percent 30 --descent-speed-percent 15 --rotation-speed-percent 20
  --safe-clearance-mm 100 --max-distance-mm 450
  --joint-limit-margin-deg 10 --max-joint-step-deg 90
  --workspace-x-min -700 --workspace-x-max -150
  --workspace-y-min -350 --workspace-y-max 350
  --workspace-z-min 40 --workspace-z-max 650
)
if [[ "${execute}" -eq 1 ]]; then
  exec "${move[@]}" --execute --confirm-move
else
  exec "${move[@]}" --dry-run
fi
