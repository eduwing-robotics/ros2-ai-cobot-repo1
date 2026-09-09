#!/usr/bin/env bash
set -Eeo pipefail

# One launcher for:
#   S22 low-latency conveyor overview + dual stop lines
#   inspection-station arrival trigger
#   true 3.5x optical still capture + ROI extraction + full PCB inspection
#
# This script never moves the conveyor.  Use run_conveyor_to_inspection.sh in
# another terminal after the conveyor/inspection launcher is ready.

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${project_dir}/scripts/ksmc_env.sh"
source "${project_dir}/scripts/vision_api_env.sh"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage:
  ~/KSMC/run_s22_conveyor_auto_inspection.sh [API options]

Starts the managed S22 HQ overview, dual conveyor stop-line detector, and the
Sequencer inspection API. It does NOT move the conveyor.

In another terminal, move one assembled board to inspection with:
  ~/KSMC/run_conveyor_to_inspection.sh

Fixed token loads from config/private/vision_api.token; otherwise set KSMC_VISION_API_TOKEN.
Useful API options:
  --host 0.0.0.0         Allow trusted LAN connections (default: localhost)
  --port 8766           HTTP port
  --timeout 300         Maximum capture/inspection execution time
Arrival alone does not capture: Sequencer must POST an inspection request.
Legacy local demo only: --legacy-arrival-trigger [old trigger options]

Outputs:
  runtime/inspection/api/<inspection_id>/state.json
  runtime/inspection/hybrid_fixed_slot/hybrid_report_latest.png
  runtime/inspection/hybrid_fixed_slot/hybrid_report_latest.json

Evidence is pulled by Sequencer. No automatic MainServer upload or DB write.
EOF
  exit 0
fi

camera_pid=""
trigger_pid=""

if [[ "${1:-}" != "--legacy-arrival-trigger" && ${#KSMC_VISION_API_TOKEN} -lt 32 ]]; then
  echo 'Set KSMC_VISION_API_TOKEN (32+ characters) before starting the camera.' >&2
  exit 2
fi

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

echo '[AUTO INSPECTION] Starting managed S22 HQ conveyor view.'
"${project_dir}/run_s22_conveyor_hq.sh" &
camera_pid=$!

echo '[AUTO INSPECTION] Starting request-driven inspection backend.'
"${project_dir}/vision_assembly/run_conveyor_inspection_trigger.sh" "$@" &
trigger_pid=$!

echo '[AUTO INSPECTION] Ready flow:'
echo '  1) Keep this terminal running.'
echo '  2) In another terminal run: ~/KSMC/run_conveyor_to_inspection.sh'
echo '  3) Sequencer requests inspection after STOP -> optical photo -> ROI -> inspection.'
echo '[AUTO INSPECTION] Overlay: /vision/conveyor/stop_image/compressed'
echo '[AUTO INSPECTION] Status: GET /api/v1/inspections/<inspection_id>'

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
