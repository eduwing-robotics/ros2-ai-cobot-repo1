#!/usr/bin/env bash
set -Eeo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
source "${project_dir}/scripts/ksmc_env.sh"

scrcpy_bin="${SCRCPY_BIN:-${project_dir}/runtime/tools/scrcpy-linux-x86_64-v4.1/scrcpy}"
device="${DEVICE:-/dev/video10}"
phone_serial="${PHONE_SERIAL:-}"
camera_id="${S22_CAMERA_ID:-0}"
camera_zoom="${S22_CAMERA_ZOOM:-1.0}"
source_size="${S22_SOURCE_SIZE:-1920x1080}"
source_fps="${S22_SOURCE_FPS:-30}"
video_codec="${S22_VIDEO_CODEC:-h264}"
video_bit_rate="${S22_VIDEO_BIT_RATE:-20M}"
preview_size="${S22_SIZE:-1920x1080}"
preview_fps="${S22_FPS:-30}"
jpeg_quality="${S22_JPEG_QUALITY:-92}"
stream_size="${S22_STREAM_SIZE:-960x540}"
stream_jpeg_quality="${S22_STREAM_JPEG_QUALITY:-84}"
analysis_fps="${S22_ANALYSIS_FPS:-5}"
inspection_dir="${S22_INSPECTION_DIR:-${project_dir}/runtime/inspection}"
max_restarts="${MAX_RESTARTS:-5}"
control_dir="${S22_CAMERA_CONTROL_DIR:-${project_dir}/runtime/s22_camera_control}"
launcher_pid_file="${control_dir}/launcher.pid"
pause_request_file="${control_dir}/pause.request"
paused_state_file="${control_dir}/paused.state"
running_state_file="${control_dir}/running.state"

source_width="${source_size%x*}"
source_height="${source_size#*x}"
preview_width="${preview_size%x*}"
preview_height="${preview_size#*x}"
stream_width="${stream_size%x*}"
stream_height="${stream_size#*x}"
scrcpy_pid=""
ros_pid=""
stop_requested=0

log() {
  printf '[S22 scrcpy HQ] %s\n' "$*"
}

cleanup_children() {
  rm -f "${running_state_file}"
  if [[ -n "${ros_pid}" ]] && kill -0 "${ros_pid}" 2>/dev/null; then
    kill "${ros_pid}" 2>/dev/null || true
    wait "${ros_pid}" 2>/dev/null || true
  fi
  if [[ -n "${scrcpy_pid}" ]] && kill -0 "${scrcpy_pid}" 2>/dev/null; then
    kill "${scrcpy_pid}" 2>/dev/null || true
    wait "${scrcpy_pid}" 2>/dev/null || true
  fi
  ros_pid=""
  scrcpy_pid=""
}

shutdown() {
  stop_requested=1
  cleanup_children
  rm -f "${paused_state_file}"
  if [[ -f "${launcher_pid_file}" ]] \
    && [[ "$(<"${launcher_pid_file}")" == "$$" ]]; then
    rm -f "${launcher_pid_file}"
  fi
}
trap shutdown EXIT INT TERM

pause_for_optical_capture() {
  [[ -e "${pause_request_file}" ]] || return 1

  cleanup_children
  printf '%s\n' "$$" >"${paused_state_file}"
  log 'Overview paused for a true optical inspection capture.'
  while [[ -e "${pause_request_file}" ]] && (( stop_requested == 0 )); do
    sleep 0.2
  done
  rm -f "${paused_state_file}"
  if (( stop_requested == 0 )); then
    # Ensure the Samsung camera app has released the lens before scrcpy
    # requests the overview stream again.
    adb -s "${phone_serial}" shell am force-stop com.sec.android.app.camera \
      >/dev/null 2>&1 || true
    sleep 1
    log 'Optical capture finished; restoring the conveyor overview.'
  fi
  return 0
}

if [[ ! -x "${scrcpy_bin}" ]]; then
  log "Missing scrcpy 4.1: ${scrcpy_bin}"
  log "Run: ${script_dir}/install_scrcpy.sh"
  exit 1
fi
if ! command -v adb >/dev/null 2>&1; then
  log 'adb is not installed.'
  exit 1
fi

if [[ -z "${phone_serial}" ]]; then
  mapfile -t adb_serials < <(adb devices | awk '$2 == "device" {print $1}')
  if [[ ${#adb_serials[@]} -ne 1 ]]; then
    log 'Set PHONE_SERIAL when zero or multiple ADB devices are connected.'
    adb devices -l
    exit 1
  fi
  phone_serial="${adb_serials[0]}"
fi
if ! adb devices | awk -v serial="${phone_serial}" \
  '$1 == serial && $2 == "device" {found=1} END {exit !found}'; then
  log "S22 ${phone_serial} is not authorized over USB."
  exit 1
fi

mkdir -p "${control_dir}"
if [[ -f "${launcher_pid_file}" ]]; then
  previous_pid="$(<"${launcher_pid_file}")"
  previous_cmdline=""
  if [[ "${previous_pid}" =~ ^[0-9]+$ ]] \
    && [[ -r "/proc/${previous_pid}/cmdline" ]]; then
    previous_cmdline="$(tr '\0' ' ' <"/proc/${previous_pid}/cmdline")"
  fi
  if [[ "${previous_pid}" =~ ^[0-9]+$ ]] \
    && [[ "${previous_pid}" != "$$" ]] \
    && [[ "${previous_pid}" != "${BASHPID}" ]] \
    && kill -0 "${previous_pid}" 2>/dev/null \
    && [[ "${previous_cmdline}" == *"camera2_scrcpy/run_camera2_scrcpy.sh"* ]]; then
    log "Another S22 scrcpy launcher is already running (PID ${previous_pid})."
    exit 1
  fi
fi
rm -f "${launcher_pid_file}" "${paused_state_file}" "${running_state_file}"
# A pause request cannot be valid before this launcher exists. Removing a
# stale request prevents a previous interrupted capture from blocking startup.
rm -f "${pause_request_file}"
printf '%s\n' "$$" >"${launcher_pid_file}"

if [[ ! -e "${device}" ]]; then
  log "${device} is missing; loading v4l2loopback."
  sudo modprobe v4l2loopback \
    video_nr="${device##*/video}" \
    card_label="S22-scrcpy-HQ" \
    exclusive_caps=1
fi

# Clear any stale V4L2 format lock before scrcpy negotiates the low-latency
# overview format. The loopback device is used only by this managed launcher.
if command -v v4l2-ctl >/dev/null 2>&1; then
  v4l2-ctl -d "${device}" -c keep_format=0 >/dev/null 2>&1 || true
fi

log "Source: camera ${camera_id}, zoom ${camera_zoom}x, ${source_size}@${source_fps}, ${video_codec} ${video_bit_rate}"
log "ROS preview: ${preview_size}@${preview_fps}, JPEG ${jpeg_quality}"
log "Network stream: ${stream_size}@${preview_fps}, JPEG ${stream_jpeg_quality}"
log "Lossless inspection directory: ${inspection_dir}"

restart_count=0
while (( stop_requested == 0 )); do
  if pause_for_optical_capture; then
    restart_count=0
    continue
  fi

  restart_count=$((restart_count + 1))
  if (( restart_count > max_restarts )); then
    log "Stream failed after ${max_restarts} attempts."
    exit 1
  fi

  "${scrcpy_bin}" \
    --serial "${phone_serial}" \
    --video-source=camera \
    --camera-id="${camera_id}" \
    --camera-zoom="${camera_zoom}" \
    --camera-size="${source_size}" \
    --camera-fps="${source_fps}" \
    --video-codec="${video_codec}" \
    --video-bit-rate="${video_bit_rate}" \
    --video-buffer=0 \
    --v4l2-sink="${device}" \
    --v4l2-buffer=0 \
    --no-playback \
    --no-audio &
  scrcpy_pid=$!

  sleep 3
  if ! kill -0 "${scrcpy_pid}" 2>/dev/null; then
    log 'scrcpy camera source failed; retrying.'
    cleanup_children
    sleep 1
    continue
  fi

  python3 "${script_dir}/camera2_ros_node.py" \
    --device "${device}" \
    --fps "${preview_fps}" \
    --jpeg-quality "${jpeg_quality}" \
    --expected-width "${source_width}" \
    --expected-height "${source_height}" \
    --output-width "${preview_width}" \
    --output-height "${preview_height}" \
    --stream-width "${stream_width}" \
    --stream-height "${stream_height}" \
    --stream-jpeg-quality "${stream_jpeg_quality}" \
    --analysis-fps "${analysis_fps}" \
    --inspection-dir "${inspection_dir}" &
  ros_pid=$!

  sleep 3
  if ! kill -0 "${ros_pid}" 2>/dev/null; then
    log 'ROS camera2 node could not open the scrcpy V4L2 stream; retrying.'
    cleanup_children
    sleep 1
    continue
  fi

  log 'Running: /camera2/image_raw/compressed'
  log 'Low-latency local/remote view: /camera2/image_stream/compressed'
  log 'Overview snapshot service: /camera2/capture_inspection_frame'
  printf '%s\n' "$$" >"${running_state_file}"
  restart_count=0
  while kill -0 "${scrcpy_pid}" 2>/dev/null \
    && kill -0 "${ros_pid}" 2>/dev/null \
    && [[ ! -e "${pause_request_file}" ]]; do
    sleep 0.2
  done

  if (( stop_requested == 0 )); then
    if pause_for_optical_capture; then
      restart_count=0
    else
      log 'Stream stopped unexpectedly; reconnecting.'
      cleanup_children
      sleep 1
    fi
  fi
done
