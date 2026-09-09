#!/usr/bin/env bash
set -Eeo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
source "${project_dir}/scripts/ksmc_env.sh"

scrcpy_bin="${SCRCPY_BIN:-${project_dir}/runtime/tools/scrcpy-linux-x86_64-v4.1/scrcpy}"
phone_serial="${PHONE_SERIAL:-}"
camera_package="com.sec.android.app.camera"
remote_camera_dir="/sdcard/DCIM/Camera"
control_dir="${S22_CAMERA_CONTROL_DIR:-${project_dir}/runtime/s22_camera_control}"
launcher_pid_file="${control_dir}/launcher.pid"
pause_request_file="${control_dir}/pause.request"
paused_state_file="${control_dir}/paused.state"
running_state_file="${control_dir}/running.state"
inspection_dir="${S22_INSPECTION_DIR:-${project_dir}/runtime/inspection}"
source_root="${script_dir}/segmentation/s22_source"
scene=""
board_state=""
expected_count=""
notes=""
label_after=0
pause_requested=0
overview_was_running=0
session_tmp=""
control_scrcpy_pid=""

usage() {
  cat <<'EOF'
Usage:
  run_capture_s22_segmentation_manual.sh --scene NAME --board-state STATE [options]

Required:
  --scene NAME             One physical board arrangement/session group.
  --board-state STATE      normal, controlled_defect, print_variation, or unknown.

Options:
  --expected-count N       Visible component count (0-25). Normal defaults to 25.
  --notes TEXT             Note copied into every imported image metadata file.
  --label-after            Open the segmentation labeler after import.
  -h, --help               Show this help.

The managed conveyor view is paused, Samsung Camera is opened with the verified
3.5x telephoto/flash-off preset, and a controllable scrcpy window is displayed.
Take 2-3 photos of ONE unchanged physical arrangement, then close the scrcpy
window or press Enter in the launch terminal. Only new DCIM/Camera JPEGs are
pulled over USB, rectified to 1600x1266, and registered as S22 segmentation
labelling sources.
EOF
}

log() {
  printf '[S22 manual segmentation capture] %s\n' "$*"
}

fail() {
  log "ERROR: $*" >&2
  exit 1
}

wait_for_file() {
  local path="$1"
  local expected_pid="${2:-}"
  local attempt
  for attempt in $(seq 1 120); do
    if [[ -e "${path}" ]]; then
      if [[ -z "${expected_pid}" ]] \
        || [[ "$(<"${path}")" == "${expected_pid}" ]]; then
        return 0
      fi
    fi
    sleep 0.1
  done
  return 1
}

list_remote_jpegs() {
  adb -s "${phone_serial}" shell ls -1 "${remote_camera_dir}" 2>/dev/null \
    | tr -d '\r' \
    | awk 'tolower($0) ~ /\.jpe?g$/ {print}' \
    | LC_ALL=C sort
}

cleanup() {
  if [[ -n "${control_scrcpy_pid}" ]] \
    && kill -0 "${control_scrcpy_pid}" 2>/dev/null; then
    kill "${control_scrcpy_pid}" 2>/dev/null || true
    wait "${control_scrcpy_pid}" 2>/dev/null || true
  fi
  adb -s "${phone_serial}" shell am force-stop "${camera_package}" \
    >/dev/null 2>&1 || true
  if (( pause_requested )); then
    rm -f "${pause_request_file}"
    pause_requested=0
  fi
  if [[ -n "${session_tmp}" ]] && [[ -d "${session_tmp}" ]]; then
    rm -rf "${session_tmp}"
  fi
}
trap cleanup EXIT INT TERM

while (( $# )); do
  case "$1" in
    --scene)
      [[ $# -ge 2 ]] || fail '--scene requires a value.'
      scene="$2"
      shift 2
      ;;
    --board-state)
      [[ $# -ge 2 ]] || fail '--board-state requires a value.'
      board_state="$2"
      shift 2
      ;;
    --expected-count)
      [[ $# -ge 2 ]] || fail '--expected-count requires a value.'
      expected_count="$2"
      shift 2
      ;;
    --notes)
      [[ $# -ge 2 ]] || fail '--notes requires a value.'
      notes="$2"
      shift 2
      ;;
    --label-after)
      label_after=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

[[ -n "${scene}" ]] || fail '--scene is required.'
case "${board_state}" in
  normal|controlled_defect|print_variation|unknown) ;;
  *) fail '--board-state must be normal, controlled_defect, print_variation, or unknown.' ;;
esac
if [[ -n "${expected_count}" ]]; then
  [[ "${expected_count}" =~ ^[0-9]+$ ]] \
    && (( expected_count >= 0 && expected_count <= 25 )) \
    || fail '--expected-count must be an integer from 0 to 25.'
fi
if [[ "${board_state}" == "normal" || "${board_state}" == "print_variation" ]]; then
  if [[ -n "${expected_count}" ]] && (( expected_count != 25 )); then
    fail 'normal and print_variation sessions must have --expected-count 25.'
  fi
  expected_count=25
fi

command -v adb >/dev/null 2>&1 || fail 'adb is not installed.'
[[ -x "${scrcpy_bin}" ]] \
  || fail "Missing scrcpy 4.1: ${scrcpy_bin}"
if [[ -z "${phone_serial}" ]]; then
  mapfile -t adb_serials < <(adb devices | awk '$2 == "device" {print $1}')
  [[ ${#adb_serials[@]} -eq 1 ]] \
    || fail 'Set PHONE_SERIAL when zero or multiple ADB devices are connected.'
  phone_serial="${adb_serials[0]}"
fi
adb devices | awk -v serial="${phone_serial}" \
  '$1 == serial && $2 == "device" {found=1} END {exit !found}' \
  || fail "S22 ${phone_serial} is not connected and authorized over USB."

mkdir -p "${control_dir}" "${inspection_dir}"
session_tmp="$(mktemp -d -p "${control_dir}" manual_capture.XXXXXX)"
before_list="${session_tmp}/before.txt"
after_list="${session_tmp}/after.txt"
new_list="${session_tmp}/new.txt"
list_remote_jpegs >"${before_list}"

if [[ -f "${launcher_pid_file}" ]]; then
  launcher_pid="$(<"${launcher_pid_file}")"
  if [[ "${launcher_pid}" =~ ^[0-9]+$ ]] \
    && kill -0 "${launcher_pid}" 2>/dev/null; then
    overview_was_running=1
    printf '%s\n' "$$" >"${pause_request_file}"
    pause_requested=1
    log 'Waiting for the conveyor overview to release the S22 camera.'
    wait_for_file "${paused_state_file}" "${launcher_pid}" \
      || fail 'The managed S22 overview did not enter pause mode.'
  fi
fi
if (( ! overview_was_running )) \
  && pgrep -f 'scrcpy.*--video-source=camera' >/dev/null 2>&1; then
  fail 'An unmanaged S22 camera stream is active. Stop it before manual capture.'
fi

adb -s "${phone_serial}" shell am force-stop "${camera_package}" \
  >/dev/null 2>&1 || true
adb -s "${phone_serial}" shell svc power stayon usb >/dev/null 2>&1 || true
adb -s "${phone_serial}" shell input keyevent 224 >/dev/null
adb -s "${phone_serial}" shell wm dismiss-keyguard >/dev/null 2>&1 || true
sleep 1
adb -s "${phone_serial}" shell am start \
  -a android.media.action.STILL_IMAGE_CAMERA >/dev/null
sleep 3

focused_window="$(adb -s "${phone_serial}" shell dumpsys window 2>/dev/null \
  | tr -d '\r' | awk '/mCurrentFocus=/ {print; exit}')"
[[ "${focused_window}" == *"${camera_package}"* ]] \
  || fail 'Samsung Camera did not open. Unlock the S22 once and retry.'

display_size="$(adb -s "${phone_serial}" shell wm size \
  | tr -d '\r' | awk '/Physical size:/ {print $3; exit}')"
[[ "${display_size}" =~ ^([0-9]+)x([0-9]+)$ ]] \
  || fail "Could not read S22 display size: ${display_size}"
display_width="${BASH_REMATCH[1]}"
display_height="${BASH_REMATCH[2]}"

# Apply the same verified stock-camera preset as the automatic inspection
# capture. The operator may tap focus and shutter, but should not change zoom,
# flash, aspect ratio, or camera while collecting one labelled scene.
flash_menu_x=$((display_width * 633 / 1000))
flash_menu_y=$((display_height * 54 / 1000))
flash_off_x=$((display_width * 339 / 1000))
flash_off_y=$((display_height * 119 / 1000))
adb -s "${phone_serial}" shell input tap "${flash_menu_x}" "${flash_menu_y}"
sleep 1
adb -s "${phone_serial}" shell input tap "${flash_off_x}" "${flash_off_y}"
sleep 1

zoom_x=$((display_width * 5 / 8))
zoom_y=$((display_height * 147 / 200))
zoom_drag_x=$((zoom_x - display_width * 15 / 1000))
adb -s "${phone_serial}" shell input tap "${zoom_x}" "${zoom_y}"
sleep 2
adb -s "${phone_serial}" shell input swipe \
  "${zoom_x}" "${zoom_y}" "${zoom_drag_x}" "${zoom_y}" 900
sleep 2

log 'Opening the controllable S22 screen.'
log 'Preset: rear 3x telephoto lens + 3.5x framing, flash OFF.'
log 'Take photos without moving parts; press Enter HERE when capture is complete.'
"${scrcpy_bin}" \
  --serial "${phone_serial}" \
  --window-title='S22 Manual Segmentation Capture - close window to import' \
  --max-size=1920 \
  --max-fps=30 \
  --video-codec=h264 \
  --video-bit-rate=16M \
  --video-buffer=0 \
  --no-audio \
  --stay-awake &
control_scrcpy_pid=$!

while kill -0 "${control_scrcpy_pid}" 2>/dev/null; do
  if read -r -t 0.25 _capture_finished; then
    log 'Enter received; closing only the S22 control viewer and importing photos.'
    kill "${control_scrcpy_pid}" 2>/dev/null || true
    break
  fi
done
if wait "${control_scrcpy_pid}"; then
  log 'S22 control window closed normally; importing new photos.'
else
  scrcpy_status=$?
  # Closing the desktop window may return a non-zero scrcpy status even though
  # Samsung Camera has already saved valid photos. Import is therefore gated
  # by the DCIM before/after list, not by the viewer's exit status.
  log "S22 control window exited with status ${scrcpy_status}; checking DCIM for saved photos."
fi
control_scrcpy_pid=""

sleep 1
list_remote_jpegs >"${after_list}"
comm -13 "${before_list}" "${after_list}" >"${new_list}"
mapfile -t new_files <"${new_list}"
(( ${#new_files[@]} > 0 )) \
  || fail 'No new Samsung Camera JPEG was found. Take photos before closing the UI.'

session_id="$(date +%Y%m%d_%H%M%S)"
session_dir="${inspection_dir}/manual_seg_${session_id}"
raw_dir="${session_dir}/raw"
roi_dir="${session_dir}/roi"
mkdir -p "${raw_dir}" "${roi_dir}"
imported=0
rejected=0
for remote_name in "${new_files[@]}"; do
  safe_name="$(printf '%s' "${remote_name}" | tr -cs '[:alnum:]._- ' '_' | tr ' ' '_')"
  raw_path="${raw_dir}/${safe_name}"
  log "Pulling ${remote_name}"
  if ! adb -s "${phone_serial}" pull \
    "${remote_camera_dir}/${remote_name}" "${raw_path}" >/dev/null; then
    log "WARNING: pull failed: ${remote_name}"
    rejected=$((rejected + 1))
    continue
  fi

  flash_status="unknown"
  if command -v identify >/dev/null 2>&1; then
    metadata="$(identify -format \
      '%w %h %[EXIF:FocalLength] %[EXIF:FocalLengthIn35mmFilm] %[EXIF:Flash]' \
      "${raw_path}" 2>/dev/null || true)"
    read -r image_width image_height focal_length focal_35mm flash_status <<<"${metadata}"
    if [[ ! "${focal_35mm}" =~ ^[0-9]+$ ]] || (( focal_35mm < 60 )); then
      log "WARNING: rejected non-telephoto/unverified image ${remote_name} (35mm=${focal_35mm:-missing})."
      rejected=$((rejected + 1))
      continue
    fi
    log "Verified ${image_width}x${image_height}, focal=${focal_length}, 35mm=${focal_35mm}mm, flash=${flash_status:-unknown}."
  else
    log 'WARNING: ImageMagick identify is unavailable; EXIF lens verification was skipped.'
  fi

  stem="${safe_name%.*}"
  roi_path="${roi_dir}/${stem}_roi.png"
  upright_path="${roi_dir}/${stem}_upright.png"
  debug_path="${roi_dir}/${stem}_debug.jpg"
  metadata_path="${roi_dir}/${stem}_roi.json"
  if ! python3 "${project_dir}/camera2_scrcpy/extract_inspection_roi.py" \
    --input "${raw_path}" \
    --output "${roi_path}" \
    --upright-output "${upright_path}" \
    --debug-output "${debug_path}" \
    --metadata-output "${metadata_path}"; then
    log "WARNING: PCB ROI extraction failed: ${remote_name}"
    rejected=$((rejected + 1))
    continue
  fi

  archive_args=(
    --source "${roi_path}"
    --source-metadata "${metadata_path}"
    --output "${source_root}"
    --scene "${scene}"
    --board-state "${board_state}"
    --notes "manual S22 UI session ${session_id}; remote=${remote_name}; EXIF flash=${flash_status:-unknown}; ${notes}"
  )
  if [[ -n "${expected_count}" ]]; then
    archive_args+=(--expected-count "${expected_count}")
  fi
  if python3 "${script_dir}/segmentation/archive_s22_capture.py" \
    "${archive_args[@]}"; then
    ln -sfn "${raw_path}" "${inspection_dir}/s22_telephoto_latest.jpg"
    imported=$((imported + 1))
  else
    log "WARNING: labelling-source registration failed: ${remote_name}"
    rejected=$((rejected + 1))
  fi
done

adb -s "${phone_serial}" shell am force-stop "${camera_package}" \
  >/dev/null 2>&1 || true
if (( pause_requested )); then
  rm -f "${pause_request_file}"
  pause_requested=0
  log 'Waiting for the conveyor overview to return.'
  wait_for_file "${running_state_file}" "${launcher_pid}" \
    || fail 'Images were imported, but the managed conveyor overview did not return.'
fi

log "Imported ${imported} image(s); rejected ${rejected}; session=${session_dir}"
(( imported > 0 )) || fail 'No valid S22 image was registered for labelling.'

if (( label_after )); then
  cleanup
  trap - EXIT INT TERM
  exec "${script_dir}/run_label_s22_segmentation.sh"
fi
log "Label next: ${script_dir}/run_label_s22_segmentation.sh"
