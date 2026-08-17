#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/../scripts/ksmc_env.sh"

target_slot="right_white_brown_01"
execute=0
confirm=0
while (($#)); do
  case "$1" in
    --target-slot) target_slot="$2"; shift 2 ;;
    --execute) execute=1; shift ;;
    --confirm-carry) confirm=1; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

if ((execute != 1 || confirm != 1)); then
  echo "Actual resume requires --execute --confirm-carry" >&2
  exit 2
fi

target_file="${script_dir}/data/board_target_last.json"
view_pid=""
cleanup() {
  if [[ -n "$view_pid" ]] && kill -0 "$view_pid" 2>/dev/null; then
    kill -INT "$view_pid" 2>/dev/null || true
    wait "$view_pid" 2>/dev/null || true
  fi
  ros2 topic pub --once /vision/board/selected_target std_msgs/msg/String "{data: ''}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "PCB RESUME: detect ${target_slot}, align horizontally, move to 100 mm hover"
ros2 topic pub --once /vision/board/selected_target std_msgs/msg/String "{data: '$target_slot'}" >/dev/null
"${script_dir}/run_board_view.sh" \
  --node-name board_target_capture \
  --target-slot "$target_slot" \
  --target-pose-topic /vision/board/capture/target_pose \
  --output-topic /vision/board/capture/image/compressed \
  >/dev/null 2>&1 &
view_pid=$!
sleep 2
"${script_dir}/run_capture_board_target.sh" \
  --topic /vision/board/capture/target_pose \
  --frames 30 \
  --target-slot "$target_slot" \
  --output "$target_file"
cleanup
view_pid=""

"${script_dir}/run_move_to_board_hover.sh" \
  --target-file "$target_file" \
  --hover-mm 100 \
  --safe-clearance-mm 150 \
  --rotation-speed-percent 50 \
  --speed-percent 50 \
  --vertical-speed-percent 50 \
  --execute \
  --confirm-carry
