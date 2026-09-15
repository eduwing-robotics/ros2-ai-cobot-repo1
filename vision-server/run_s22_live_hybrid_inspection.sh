#!/usr/bin/env bash
set -Eeo pipefail

# Capture the board currently visible to the S22 and immediately inspect all
# 25 fixed assembly slots.  This launcher never sends robot or conveyor motion
# commands.  A managed S22 overview is paused and restored by the capture
# script when it is already running.

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${project_dir}/scripts/ksmc_env.sh"

latest_roi="${project_dir}/runtime/inspection/s22_inspection_roi_latest.png"
capture_script="${project_dir}/run_s22_optical_inspection.sh"
inspector_script="${project_dir}/vision_assembly/run_hybrid_fixed_slot_inspection.sh"
skip_capture=0
inspection_args=()

usage() {
  cat <<'EOF'
Usage:
  ~/KSMC/run_s22_live_hybrid_inspection.sh [options]

Default flow:
  current S22 view -> fresh 3.5x optical still (flash off) -> PCB ROI
  -> 25 fixed-slot hybrid inspection

Options:
  --skip-capture    Inspect the current latest ROI without taking a new photo.
  --skip-yolo       Forwarded to the hybrid inspector for a diagnostic run.
  --skip-patchcore  Forwarded to the hybrid inspector for a diagnostic run.
  --patchcore-accelerator auto|cpu|gpu
                    Select PatchCore execution device (auto is the default).
  -h, --help        Show this help.

Full inspection is the default; do not pass either skip option for normal use.
The pipeline inspects GPU 1, HBM 8, Power Module 4, VRM 5, Inductor 2,
and SMD Capacitor 5. Unvalidated providers remain ADVISORY_ONLY.
EOF
}

for arg in "$@"; do
  case "${arg}" in
    -h|--help)
      usage
      exit 0
      ;;
    --skip-capture)
      skip_capture=1
      ;;
    --image|--image=*)
      echo '[S22 LIVE AOI] --image is managed by this launcher.' >&2
      exit 2
      ;;
    *)
      inspection_args+=("${arg}")
      ;;
  esac
done

before="$(readlink -f "${latest_roi}" 2>/dev/null || true)"
if (( ! skip_capture )); then
  echo '[S22 LIVE AOI] Capturing the board currently visible to the S22.'
  S22_INSPECTION_FLASH=off \
  S22_INSPECTION_ZOOM="${S22_INSPECTION_ZOOM:-3.5}" \
    "${capture_script}"
fi

after="$(readlink -f "${latest_roi}" 2>/dev/null || true)"
if [[ -z "${after}" ]] || [[ ! -f "${after}" ]]; then
  echo '[S22 LIVE AOI] A valid PCB ROI was not produced.' >&2
  exit 1
fi
if (( ! skip_capture )) && [[ -n "${before}" ]] && [[ "${after}" == "${before}" ]]; then
  echo '[S22 LIVE AOI] Refusing to inspect a stale S22 ROI.' >&2
  exit 1
fi

echo "[S22 LIVE AOI] Fresh ROI: ${after}"
echo '[S22 LIVE AOI] Running the complete 25-slot hybrid inspection.'
"${inspector_script}" \
  "${inspection_args[@]}" \
  --image "${after}"

echo '[S22 LIVE AOI] Complete.'
echo '[S22 LIVE AOI] Use the HYBRID_REPORT and HYBRID_VISUALIZATION paths printed above (including custom --output runs).'
