#!/usr/bin/env bash
set -Eeo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
source "${project_dir}/scripts/ksmc_env.sh"

phone_serial="${PHONE_SERIAL:-}"
inspection_dir="${S22_INSPECTION_DIR:-${project_dir}/runtime/inspection}"
control_dir="${S22_CAMERA_CONTROL_DIR:-${project_dir}/runtime/s22_camera_control}"
launcher_pid_file="${control_dir}/launcher.pid"
pause_request_file="${control_dir}/pause.request"
paused_state_file="${control_dir}/paused.state"
running_state_file="${control_dir}/running.state"
lock_dir="${control_dir}/optical_capture.lock"
camera_package="com.sec.android.app.camera"
remote_camera_dir="/sdcard/DCIM/Camera"
inspection_zoom="${S22_INSPECTION_ZOOM:-3.5}"
inspection_flash="${S22_INSPECTION_FLASH:-off}"
focus_x_percent="${S22_INSPECTION_FOCUS_X_PERCENT:-50}"
focus_y_percent="${S22_INSPECTION_FOCUS_Y_PERCENT:-38}"
overview_was_running=0
pause_requested=0
capture_succeeded=0
lock_owned=0
camera_owned=0

log() {
  printf '[S22 telephoto capture] %s\n' "$*"
}

fail() {
  log "ERROR: $*" >&2
  exit 1
}

validate_capture_settings() {
  # Reject unsupported UI coordinates/settings before pausing the overview
  # or touching Samsung Camera. Keep all existing supported choices intact.
  case "${inspection_zoom}" in
    3|3.0|3.5|4|4.0|4.7) ;;
    *) fail 'S22_INSPECTION_ZOOM must be 3.0, 3.5, 4.0, or 4.7.' ;;
  esac
  case "${inspection_flash,,}" in
    on|1|true|off|0|false) ;;
    *) fail 'S22_INSPECTION_FLASH must be on or off.' ;;
  esac
  local focus_percent
  for focus_percent in "$focus_x_percent" "$focus_y_percent"; do
    [[ "$focus_percent" =~ ^[1-9][0-9]?$ ]] \
      || fail 'Focus percentages must be integer 1..99.'
  done
}

latest_remote_jpeg() {
  adb -s "${phone_serial}" shell ls -1t "${remote_camera_dir}" 2>/dev/null \
    | tr -d '\r' \
    | awk 'tolower($0) ~ /\.jpe?g$/ {print; exit}'
}

wait_for_file() {
  local path="$1"
  local expected_pid="${2:-}"
  local attempt
  for attempt in $(seq 1 100); do
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

cleanup() {
  if (( camera_owned )); then
    camera_owned=0
    adb -s "${phone_serial}" shell am force-stop "${camera_package}" \
      >/dev/null 2>&1 || true
  fi
  if (( pause_requested )); then
    rm -f "${pause_request_file}"
    pause_requested=0
  fi
  if (( lock_owned )); then
    rmdir "${lock_dir}" 2>/dev/null || true
    lock_owned=0
  fi
}

validate_capture_settings

command -v adb >/dev/null 2>&1 || fail 'adb is not installed.'
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
mkdir "${lock_dir}" 2>/dev/null \
  || fail 'Another optical inspection capture is already in progress.'
lock_owned=1
# A losing capture must not stop the owner's camera or remove its lock.
# Signals exit first, then EXIT performs cleanup exactly once.
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ -f "${launcher_pid_file}" ]]; then
  launcher_pid="$(<"${launcher_pid_file}")"
  if [[ "${launcher_pid}" =~ ^[0-9]+$ ]] \
    && kill -0 "${launcher_pid}" 2>/dev/null; then
    overview_was_running=1
    printf '%s\n' "$$" >"${pause_request_file}"
    pause_requested=1
    log 'Waiting for the conveyor overview to release the S22 camera.'
    wait_for_file "${paused_state_file}" "${launcher_pid}" \
      || fail 'The overview launcher did not enter optical-capture pause mode.'
  fi
fi

if (( ! overview_was_running )); then
  if pgrep -f 'scrcpy.*--video-source=camera' >/dev/null 2>&1; then
    fail 'An unmanaged S22 camera stream is active. Stop it or use run_s22_conveyor_hq.sh so optical capture can pause and resume safely.'
  fi
  log 'No managed conveyor overview is running; capturing without auto-resume.'
fi

# The scrcpy Camera2 zoom request remains on the main physical lens on this
# SM-S901N. Samsung Camera must select its 3x lens button to activate physical
# camera 52 (7.0 mm, 69 mm full-frame equivalent).
camera_owned=1
adb -s "${phone_serial}" shell am force-stop "${camera_package}" \
  >/dev/null 2>&1 || true

# scrcpy camera streaming works while Android is locked, but Samsung Camera
# does not expose its shutter UI in that state. Wake and dismiss the keyguard
# before launching the photo activity. A secure PIN/password still requires
# the user to unlock the phone once.
adb -s "${phone_serial}" shell svc power stayon usb >/dev/null 2>&1 || true
adb -s "${phone_serial}" shell input keyevent 224 >/dev/null
adb -s "${phone_serial}" shell wm dismiss-keyguard >/dev/null 2>&1 || true
sleep 1

before_file="$(latest_remote_jpeg || true)"
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

# Keep illumination deterministic for inspection.  Samsung Camera exposes
# Off / Auto / On but no user-selectable intensity.  Selecting On makes the
# still-photo capture fire the phone's normal main flash; this is the strongest
# repeatable mode the stock camera UI provides.  Ratios are based on the
# accessibility bounds and remain valid when display scaling changes.
case "${inspection_flash,,}" in
  on|1|true)
    flash_menu_x=$((display_width * 633 / 1000))
    flash_menu_y=$((display_height * 54 / 1000))
    flash_on_x=$((display_width * 661 / 1000))
    flash_on_y=$((display_height * 119 / 1000))
    adb -s "${phone_serial}" shell input tap \
      "${flash_menu_x}" "${flash_menu_y}"
    sleep 1
    adb -s "${phone_serial}" shell input tap \
      "${flash_on_x}" "${flash_on_y}"
    sleep 1
    log 'Samsung Camera flash forced ON.'
    ;;
  off|0|false)
    flash_menu_x=$((display_width * 633 / 1000))
    flash_menu_y=$((display_height * 54 / 1000))
    flash_off_x=$((display_width * 339 / 1000))
    flash_off_y=$((display_height * 119 / 1000))
    adb -s "${phone_serial}" shell input tap \
      "${flash_menu_x}" "${flash_menu_y}"
    sleep 1
    adb -s "${phone_serial}" shell input tap \
      "${flash_off_x}" "${flash_off_y}"
    sleep 1
    log 'Samsung Camera flash forced OFF.'
    ;;
  *)
    fail 'S22_INSPECTION_FLASH must be on or off.'
    ;;
esac

# Samsung Camera portrait UI on the S22 places the 3x lens button at the
# normalized centre (0.625, 0.735). Ratios keep the tap valid if display
# resolution scaling changes while the physical orientation stays fixed.
zoom_x=$((display_width * 5 / 8))
zoom_y=$((display_height * 147 / 200))
adb -s "${phone_serial}" shell input tap "${zoom_x}" "${zoom_y}"
sleep 2

case "${inspection_zoom}" in
  3|3.0)
    zoom_label='3x'
    ;;
  3.5)
    # A short 16 px left drag on the 1080 px S22 display selects exactly
    # 3.5x in Samsung Camera while physical telephoto camera 52 stays active.
    zoom_drag_x=$((zoom_x - display_width * 15 / 1000))
    adb -s "${phone_serial}" shell input swipe \
      "${zoom_x}" "${zoom_y}" "${zoom_drag_x}" "${zoom_y}" 900
    sleep 2
    zoom_label='3p5x'
    ;;
  4|4.0)
    # Select the true 3x telephoto lens first, then move Samsung Camera's
    # zoom control to 4.0x. This changes capture framing before the JPEG is
    # taken; it is not a post-capture ROI enlargement.
    # 33 px on the current 1080 px S22 display was verified on-screen as
    # exactly 4.0x (30/31 px remained at 3.9x).
    zoom_drag_x=$((zoom_x - display_width * 31 / 1000))
    adb -s "${phone_serial}" shell input swipe \
      "${zoom_x}" "${zoom_y}" "${zoom_drag_x}" "${zoom_y}" 900
    sleep 2
    zoom_label='4x'
    ;;
  4.7)
    # On this S22 Camera version, dragging the selected 3x button left by
    # roughly 10.6% of display width selects 4.7x while physical camera 52
    # remains active. This is telephoto capture plus in-camera zoom, not a
    # post-capture ROI crop.
    zoom_drag_x=$((zoom_x - display_width * 106 / 1000))
    adb -s "${phone_serial}" shell input swipe \
      "${zoom_x}" "${zoom_y}" "${zoom_drag_x}" "${zoom_y}" 900
    sleep 2
    zoom_label='4p7x'
    ;;
  *)
    fail 'S22_INSPECTION_ZOOM must be 3.0, 3.5, 4.0, or 4.7.'
    ;;
esac

# Re-run AF/AE after changing lens and zoom. The legacy default is not
# guaranteed to fall on the board: placement-dependent overrides are diagnostic.
# Diagnostic override uses normalized portrait display coordinates, not ROI pixels.
focus_x=$((display_width * focus_x_percent / 100))
focus_y=$((display_height * focus_y_percent / 100))
adb -s "${phone_serial}" shell input tap "${focus_x}" "${focus_y}"
sleep 2

# Opt-in diagnostic: request Samsung's AF/AE lock and archive the actual UI.
# This does not promise manual ISO/WB or a persistent lock across app restarts.
if [[ "${S22_INSPECTION_FOCUS_LOCK:-0}" == "1" ]]; then
  adb -s "${phone_serial}" shell input swipe \
    "${focus_x}" "${focus_y}" "${focus_x}" "${focus_y}" 1500
  sleep 2
  adb -s "${phone_serial}" exec-out screencap -p \
    >"${inspection_dir}/s22_focus_lock_diagnostic.png"
  log 'AF/AE long-press requested; diagnostic screenshot saved (lock not yet verified).'
fi

# Directly tap Samsung Camera's shutter. KEYCODE_CAMERA can be remapped by
# phone settings, while the on-screen shutter remains deterministic.
shutter_x=$((display_width / 2))
shutter_y=$((display_height * 83 / 100))
adb -s "${phone_serial}" shell input tap "${shutter_x}" "${shutter_y}"

after_file=""
for _attempt in $(seq 1 100); do
  after_file="$(latest_remote_jpeg || true)"
  if [[ -n "${after_file}" ]] && [[ "${after_file}" != "${before_file}" ]]; then
    break
  fi
  sleep 0.1
done
[[ -n "${after_file}" ]] && [[ "${after_file}" != "${before_file}" ]] \
  || fail 'Samsung Camera did not create a new JPEG.'

timestamp="$(date +%Y%m%d_%H%M%S)"
output_path="${inspection_dir}/s22_tele_${zoom_label}_${timestamp}.jpg"
adb -s "${phone_serial}" pull \
  "${remote_camera_dir}/${after_file}" "${output_path}" >/dev/null

if command -v identify >/dev/null 2>&1; then
  metadata="$(identify -format \
    '%w %h %[EXIF:FocalLength] %[EXIF:FocalLengthIn35mmFilm]' \
    "${output_path}")"
  read -r image_width image_height focal_length focal_35mm <<<"${metadata}"
  if [[ "${focal_35mm}" =~ ^[0-9]+$ ]] && (( focal_35mm < 60 )); then
    fail "Captured ${focal_35mm} mm-equivalent image; the 3x optical lens was not active."
  fi
  log "Verified optical image: ${image_width}x${image_height}, focal=${focal_length}, 35mm=${focal_35mm}mm"
else
  log 'ImageMagick identify is unavailable; focal-length EXIF was not verified.'
fi

ln -sfn "${output_path}" "${inspection_dir}/s22_telephoto_latest.jpg"
capture_succeeded=1
log "Saved raw optical photo: ${output_path}"
if [[ "${S22_EXTRACT_INSPECTION_ROI:-1}" == "1" ]]; then
  roi_output="${inspection_dir}/s22_inspection_roi_${timestamp}.png"
  upright_output="${inspection_dir}/s22_telephoto_upright_${timestamp}.png"
  roi_debug_output="${inspection_dir}/s22_inspection_roi_debug_${timestamp}.jpg"
  roi_metadata_output="${inspection_dir}/s22_inspection_roi_${timestamp}.json"
  if ! python3 "${script_dir}/extract_inspection_roi.py" \
    --input "${output_path}" \
    --output "${roi_output}" \
    --upright-output "${upright_output}" \
    --debug-output "${roi_debug_output}" \
    --metadata-output "${roi_metadata_output}"; then
    log 'WARNING: optical photo was saved, but no valid PCB ROI was produced.'
  fi
fi

adb -s "${phone_serial}" shell am force-stop "${camera_package}" \
  >/dev/null 2>&1 || true
camera_owned=0
if (( pause_requested )); then
  rm -f "${pause_request_file}"
  pause_requested=0
  log 'Waiting for the conveyor overview to return.'
  wait_for_file "${running_state_file}" "${launcher_pid}" \
    || fail 'Optical photo was saved, but the conveyor overview did not return in time.'
  log 'Conveyor overview restored.'
fi

(( capture_succeeded ))
