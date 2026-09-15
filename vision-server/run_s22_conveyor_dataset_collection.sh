#!/usr/bin/env bash
set -Eeo pipefail

# Managed S22 overview + dual stop lines + capture-only dataset trigger.
# This launcher never moves the conveyor and never emits an inspection verdict.

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${project_dir}/scripts/ksmc_env.sh"

dataset_split="unverified"
lighting_condition="ambient_unclassified"
board_state="unknown"
known_defects=""
trigger_args=()

while (($#)); do
  case "$1" in
    --split)
      [[ $# -ge 2 ]] || { echo 'Missing value after --split.' >&2; exit 2; }
      dataset_split="$2"
      shift 2
      ;;
    --lighting)
      [[ $# -ge 2 ]] || { echo 'Missing value after --lighting.' >&2; exit 2; }
      lighting_condition="$2"
      shift 2
      ;;
    --board-state)
      [[ $# -ge 2 ]] || { echo 'Missing value after --board-state.' >&2; exit 2; }
      board_state="$2"
      shift 2
      ;;
    --known-defects)
      [[ $# -ge 2 ]] || { echo 'Missing value after --known-defects.' >&2; exit 2; }
      known_defects="$2"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage:
  ~/KSMC/run_s22_conveyor_dataset_collection.sh [options]

Starts the S22 overview, both stop lines, and a capture-only trigger. It does
NOT move the conveyor and does NOT run the legacy OpenCV defect verdict.

Options:
  --split NAME       Dataset split; default: unverified
  --lighting NAME    Lighting label; e.g. evening_indoor or daylight_noon
  --board-state NAME unknown, known_defect, or normal_candidate
  --known-defects X  Comma-separated tags; e.g. missing_smd
  --once             Exit after one successful capture
  --settle-seconds N Delay after stop before capture; default: 0.35

Move one board from another terminal:
  ~/KSMC/run_conveyor_to_inspection.sh

Captured data:
  ~/KSMC/runtime/datasets/s22_aoi/<split>/<lighting>/<date>/
EOF
      exit 0
      ;;
    *)
      trigger_args+=("$1")
      shift
      ;;
  esac
done

export S22_DATASET_SPLIT="${dataset_split}"
export S22_LIGHTING_CONDITION="${lighting_condition}"
export S22_BOARD_STATE="${board_state}"
export S22_KNOWN_DEFECTS="${known_defects}"
export S22_INSPECTION_FLASH=off

case "${board_state}" in
  unknown|normal_candidate)
    if [[ -n "${known_defects}" ]]; then
      echo '[S22 DATASET] --known-defects requires --board-state known_defect.' >&2
      exit 2
    fi
    ;;
  known_defect)
    if [[ -z "${known_defects}" ]]; then
      echo '[S22 DATASET] known_defect requires at least one --known-defects tag.' >&2
      exit 2
    fi
    ;;
  *)
    echo '[S22 DATASET] --board-state must be unknown, known_defect, or normal_candidate.' >&2
    exit 2
    ;;
esac

camera_pid=""
trigger_pid=""

cleanup() {
  if [[ -n "${trigger_pid}" ]] && kill -0 "${trigger_pid}" 2>/dev/null; then
    kill "${trigger_pid}" 2>/dev/null || true
    wait "${trigger_pid}" 2>/dev/null || true
  fi
  if [[ -n "${camera_pid}" ]] && kill -0 "${camera_pid}" 2>/dev/null; then
    kill "${camera_pid}" 2>/dev/null || true
    wait "${camera_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo '[S22 DATASET] Starting managed S22 conveyor overview.'
"${project_dir}/run_s22_conveyor_hq.sh" &
camera_pid=$!

echo '[S22 DATASET] Arming capture-only inspection-station trigger.'
"${project_dir}/vision_assembly/run_conveyor_inspection_trigger.sh" \
  --pipeline "${project_dir}/vision_assembly/inspection/capture_conveyor_dataset_once.py" \
  --event-file "${project_dir}/runtime/inspection/dataset_capture_latest.json" \
  "${trigger_args[@]}" &
trigger_pid=$!

echo "[S22 DATASET] split=${dataset_split}, lighting=${lighting_condition}, flash=off"
echo "[S22 DATASET] board_state=${board_state}, known_defects=${known_defects:-none}"
echo '[S22 DATASET] This launcher does not move the belt.'
echo '[S22 DATASET] In another terminal run: ~/KSMC/run_conveyor_to_inspection.sh'
echo '[S22 DATASET] Overlay: /vision/conveyor/stop_image/compressed'

while true; do
  if ! kill -0 "${camera_pid}" 2>/dev/null; then
    wait "${camera_pid}"
    exit $?
  fi
  if ! kill -0 "${trigger_pid}" 2>/dev/null; then
    wait "${trigger_pid}"
    exit $?
  fi
  sleep 1
done
