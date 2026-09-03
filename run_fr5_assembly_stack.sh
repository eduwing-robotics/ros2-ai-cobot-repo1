#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${root}/scripts/ksmc_env.sh"

runtime_dir="${KSMC_ASSEMBLY_RUNTIME_DIR:-${root}/runtime/assembly_stack}"
pid_dir="${runtime_dir}/pids"
log_dir="${runtime_dir}/logs"
endpoint_root="${KSMC_UNITY_ENDPOINT_ROOT:-/home/juchan-yoon/Ros2UnityEndopoint_PKG_0.1v/Ros2UnityEndopoint_PKG}"
camera_profile="${KSMC_ASSEMBLY_CAMERA_PROFILE:-standard}"
smd_set_index="${KSMC_SMD_SET_INDEX:-1}"
mkdir -p "${pid_dir}" "${log_dir}"

components=(unity_fairino camera tray_vision board_view board_pose_3d image_mux vision_api)
duplicate_patterns=(
  "run_with_fairino.sh"
  "ros2_cmd_server"
  "default_server_endpoint"
  "realsense2_camera_node"
  "rs_launch.py"
  "run_tray_merged_detection.sh"
  "view_tray_sections.py"
  "render_tray_live.py"
  "detect_smd_close_live.py"
  "detect_tray_parts.py"
  "view_board_center.py"
  "track_board_pose_3d.py"
  "assembly_image_mux.py"
  "orchestration_action_server"
)
cleanup_failed_start=false
on_exit() {
  local status=$?
  trap - EXIT
  if [[ "${cleanup_failed_start}" == true && ${status} -ne 0 ]]; then
    echo "Stack startup failed; stopping components started in this attempt." >&2
    stop_managed
  fi
  exit "${status}"
}
trap on_exit EXIT

usage() {
  cat <<'EOF'
Usage: ./run_fr5_assembly_stack.sh COMMAND [OPTION]

Commands:
  start             Stop duplicate FR5 assembly processes, then start the stack
  stop              Stop processes started by this supervisor
  restart           Stop/clean, then start the stack
  clean             Stop managed and matching stale/duplicate processes
  status            Show managed processes, ROS nodes/topics, and TCP port 10000
  check             Read one robot-state sample and show essential topics
  logs [NAME]       Show recent logs for all components or one component
  follow [NAME]     Follow logs for all components or one component
  view              Open RQT on the compressed assembly operator view

Options:
  --camera standard  1280x720 RGB-D (default; TrayHome + SMD close view)
  --camera smd       1920x1080 RGB + aligned depth (diagnostic only)
  --camera none      Do not manage the D435 process
  --smd-set 1|2      Select one 5-part SMD set from the 10-part tray (default: 1)

This launcher starts command/vision services only. It never sends a robot-motion
or gripper command.
EOF
}

pid_file() {
  printf '%s/%s.pid\n' "${pid_dir}" "$1"
}

is_alive() {
  kill -0 "$1" 2>/dev/null
}

managed_pid() {
  local file
  file="$(pid_file "$1")"
  [[ -f "${file}" ]] || return 1
  local pid
  read -r pid < "${file}"
  [[ "${pid}" =~ ^[0-9]+$ ]] || return 1
  printf '%s\n' "${pid}"
}

start_component() {
  local name="$1"
  shift
  local old_pid
  if old_pid="$(managed_pid "${name}")" && is_alive "${old_pid}"; then
    echo "${name} is already managed (PID ${old_pid})." >&2
    return 1
  fi
  unlink "$(pid_file "${name}")" 2>/dev/null || true
  echo "Starting ${name}..."
  setsid "$@" >>"${log_dir}/${name}.log" 2>&1 &
  local pid=$!
  printf '%s\n' "${pid}" > "$(pid_file "${name}")"
  sleep 0.3
  if ! is_alive "${pid}"; then
    echo "${name} exited during startup. See ${log_dir}/${name}.log" >&2
    tail -n 40 "${log_dir}/${name}.log" >&2 || true
    return 1
  fi
}

stop_component() {
  local name="$1"
  local pid
  if ! pid="$(managed_pid "${name}")"; then
    unlink "$(pid_file "${name}")" 2>/dev/null || true
    return 0
  fi
  if is_alive "${pid}"; then
    echo "Stopping ${name} (process group ${pid})..."
    kill -INT -- "-${pid}" 2>/dev/null || kill -INT "${pid}" 2>/dev/null || true
    for _ in $(seq 1 30); do
      is_alive "${pid}" || break
      sleep 0.1
    done
    if is_alive "${pid}"; then
      kill -TERM -- "-${pid}" 2>/dev/null || kill -TERM "${pid}" 2>/dev/null || true
    fi
  fi
  unlink "$(pid_file "${name}")" 2>/dev/null || true
}

stop_managed() {
  local index
  for ((index=${#components[@]}-1; index>=0; index--)); do
    stop_component "${components[index]}"
  done
}

matching_duplicate_pids() {
  local pattern pid
  for pattern in "${duplicate_patterns[@]}"; do
    while read -r pid; do
      [[ -n "${pid}" && "${pid}" != "$$" && "${pid}" != "${PPID}" ]] || continue
      printf '%s\n' "${pid}"
    done < <(pgrep -f -- "${pattern}" 2>/dev/null || true)
  done | sort -nu
}

assert_safe_to_stop_driver() {
  local duplicates state
  duplicates="$(matching_duplicate_pids)"
  [[ -n "${duplicates}" ]] || return 0
  state="$(timeout 3 ros2 topic echo --once /nonrt_state_data 2>/dev/null || true)"
  if [[ -n "${state}" ]] && ! grep -Eq '^robot_motion_done:[[:space:]]*1([[:space:]]*)$' <<<"${state}"; then
    echo "Refusing cleanup: robot state is available but robot_motion_done is not 1." >&2
    echo "Stop the robot safely and retry. No matching process was killed." >&2
    return 1
  fi
}

clean_duplicates() {
  assert_safe_to_stop_driver
  local pids pid
  pids="$(matching_duplicate_pids)"
  if [[ -z "${pids}" ]]; then
    echo "No stale or duplicate FR5 assembly processes found."
    return 0
  fi
  echo "Stopping stale/duplicate FR5 assembly PIDs: $(tr '\n' ' ' <<<"${pids}")"
  while read -r pid; do
    [[ -n "${pid}" ]] && kill -INT "${pid}" 2>/dev/null || true
  done <<<"${pids}"
  sleep 1
  pids="$(matching_duplicate_pids)"
  while read -r pid; do
    [[ -n "${pid}" ]] && kill -TERM "${pid}" 2>/dev/null || true
  done <<<"${pids}"
  sleep 1
  pids="$(matching_duplicate_pids)"
  if [[ -n "${pids}" ]]; then
    echo "Processes still alive after TERM: $(tr '\n' ' ' <<<"${pids}")" >&2
    echo "Inspect them manually; this script will not use SIGKILL." >&2
    return 1
  fi
}

wait_for_topic() {
  local topic="$1"
  local seconds="$2"
  local label="$3"
  local count
  local info
  for count in $(seq 1 "$((seconds * 2))"); do
    info="$(ros2 topic info "${topic}" 2>/dev/null || true)"
    if grep -Eq '^Publisher count: [1-9][0-9]*$' <<<"${info}"; then
      echo "Ready: ${label} (${topic})"
      return 0
    fi
    sleep 0.5
  done
  echo "Timed out waiting for ${label}: ${topic}" >&2
  return 1
}

wait_for_node() {
  local node="$1"
  local seconds="$2"
  local count
  for count in $(seq 1 "$((seconds * 2))"); do
    if ros2 node list 2>/dev/null | grep -Fxq -- "${node}"; then
      echo "Ready: ROS node ${node}"
      return 0
    fi
    sleep 0.5
  done
  echo "Timed out waiting for ROS node: ${node}" >&2
  return 1
}

wait_for_node_absent() {
  local node="$1"
  local seconds="$2"
  local count
  local absent_count=0
  for count in $(seq 1 "$((seconds * 2))"); do
    if ros2 node list 2>/dev/null | grep -Fxq -- "${node}"; then
      absent_count=0
    else
      absent_count=$((absent_count + 1))
      if (( absent_count >= 2 )); then
        return 0
      fi
    fi
    sleep 0.5
  done
  echo "Timed out waiting for old ROS node to disappear: ${node}" >&2
  return 1
}

wait_for_port() {
  local port="$1"
  local seconds="$2"
  local count
  for count in $(seq 1 "$((seconds * 2))"); do
    if ss -ltn 2>/dev/null | grep -Eq "[:.]${port}[[:space:]]"; then
      echo "Ready: TCP port ${port}"
      return 0
    fi
    sleep 0.5
  done
  echo "Timed out waiting for TCP port ${port}" >&2
  return 1
}

parse_start_options() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --camera)
        [[ $# -ge 2 ]] || { echo "--camera needs a value" >&2; exit 2; }
        camera_profile="$2"
        shift 2
        ;;
      --smd-set)
        [[ $# -ge 2 ]] || { echo "--smd-set needs a value" >&2; exit 2; }
        smd_set_index="$2"
        shift 2
        ;;
      *)
        echo "Unknown option: $1" >&2
        usage
        exit 2
        ;;
    esac
  done
  case "${camera_profile}" in
    smd|standard|none) ;;
    *) echo "Invalid camera profile: ${camera_profile}" >&2; exit 2 ;;
  esac
  case "${smd_set_index}" in
    1|2) ;;
    *) echo "Invalid SMD set index: ${smd_set_index} (use 1 or 2)" >&2; exit 2 ;;
  esac
}

start_stack() {
  [[ -x "${endpoint_root}/run_with_fairino.sh" ]] || {
    echo "Unity Endpoint launcher not found: ${endpoint_root}/run_with_fairino.sh" >&2
    echo "Set KSMC_UNITY_ENDPOINT_ROOT in config/ksmc.env." >&2
    return 1
  }
  cleanup_failed_start=true

  assert_safe_to_stop_driver
  stop_managed
  clean_duplicates
  wait_for_node_absent /fr_command_server 20

  start_component unity_fairino "${endpoint_root}/run_with_fairino.sh"
  wait_for_topic /nonrt_state_data 30 "FAIRINO state"
  wait_for_port 10000 20

  case "${camera_profile}" in
    smd)
      start_component camera "${root}/calibration/run_d435_rgbd_smd_close.sh"
      ;;
    standard)
      start_component camera "${root}/calibration/run_d435_rgbd_stable.sh"
      ;;
    none)
      echo "Camera management disabled."
      ;;
  esac
  if [[ "${camera_profile}" != "none" ]]; then
    wait_for_topic /camera/camera/color/image_raw 35 "D435 color"
    wait_for_topic /camera/camera/aligned_depth_to_color/image_raw 35 "D435 aligned depth"
  fi

  export KSMC_SMD_SET_INDEX="${smd_set_index}"
  start_component tray_vision "${root}/vision_assembly/run_tray_merged_detection.sh"
  start_component board_view "${root}/vision_assembly/run_board_view.sh"
  start_component board_pose_3d python3 "${root}/vision_assembly/scripts/track_board_pose_3d.py" --target GPU-01
  start_component image_mux "${root}/vision_assembly/run_assembly_image_mux.sh"
  start_component vision_api "${root}/vision_assembly/run_orchestration_api.sh"

  wait_for_topic /vision/tray/part_counts 25 "tray detection"
  wait_for_topic /vision/board/image/compressed 25 "board view"
  wait_for_topic /vision/board/pose_3d/status 25 "board 3D pose"
  wait_for_topic /vision/assembly/image/compressed 25 "assembly operator view"
  wait_for_node /vision_orchestration_action_server 15

  cleanup_failed_start=false
  echo
  echo "FR5 assembly stack started. No robot-motion command was sent."
  echo "Camera profile: ${camera_profile}; SMD set: ${smd_set_index} (5 of 10 parts)"
  echo "Run: ${root}/run_fr5_assembly_stack.sh check"
  echo "Logs: ${root}/run_fr5_assembly_stack.sh logs"
}

show_status() {
  local name pid state
  echo "Managed processes:"
  for name in "${components[@]}"; do
    if pid="$(managed_pid "${name}")" && is_alive "${pid}"; then
      state="RUNNING pid=${pid}"
    else
      state="STOPPED"
    fi
    printf '  %-16s %s\n' "${name}" "${state}"
  done
  echo
  echo "TCP endpoint:"
  ss -ltn 2>/dev/null | grep -E '[:.]10000[[:space:]]' || echo "  port 10000 not listening"
  echo
  echo "Relevant ROS nodes:"
  ros2 node list 2>/dev/null | grep -E 'fr_command_server|camera|tray|smd|board|assembly_image_mux|vision_orchestration' || echo "  none"
  echo
  echo "Essential topics:"
  ros2 topic list 2>/dev/null | grep -E '^/nonrt_state_data$|^/camera/camera/(color|aligned_depth)|^/vision/(tray|board|assembly)' || echo "  none"
}

check_stack() {
  show_status
  echo
  echo "Robot state summary (one sample):"
  local state
  state="$(timeout 5 ros2 topic echo --once /nonrt_state_data 2>/dev/null || true)"
  if [[ -z "${state}" ]]; then
    echo "  no /nonrt_state_data sample" >&2
    return 1
  fi
  grep -E '^(robot_mode|tool_num|work_num|abnormal_stop|emg|robot_motion_done|grip_motion_done|gripper_position|gripper_feedback_valid|gripperfaultnum|main_error_code|sub_error_code|collision_err|cart_[xyzabc]_cur_pos):' <<<"${state}" | sed 's/^/  /'
}

show_logs() {
  local mode="$1"
  local requested="${2:-}"
  local name file
  if [[ -n "${requested}" ]]; then
    file="${log_dir}/${requested}.log"
    [[ -f "${file}" ]] || { echo "Unknown or empty log: ${requested}" >&2; return 1; }
    if [[ "${mode}" == "follow" ]]; then tail -n 80 -F "${file}"; else tail -n 120 "${file}"; fi
    return
  fi
  if [[ "${mode}" == "follow" ]]; then
    compgen -G "${log_dir}/*.log" >/dev/null || { echo "No logs yet."; return 0; }
    tail -n 40 -F "${log_dir}"/*.log
    return
  fi
  for name in "${components[@]}"; do
    file="${log_dir}/${name}.log"
    [[ -f "${file}" ]] || continue
    echo "===== ${name} ====="
    tail -n 30 "${file}"
  done
}

command="${1:-}"
shift || true
case "${command}" in
  start)
    parse_start_options "$@"
    start_stack
    ;;
  stop)
    assert_safe_to_stop_driver
    stop_managed
    ;;
  restart)
    parse_start_options "$@"
    start_stack
    ;;
  clean)
    [[ $# -eq 0 ]] || { usage; exit 2; }
    assert_safe_to_stop_driver
    stop_managed
    clean_duplicates
    ;;
  status)
    [[ $# -eq 0 ]] || { usage; exit 2; }
    show_status
    ;;
  check)
    [[ $# -eq 0 ]] || { usage; exit 2; }
    check_stack
    ;;
  logs|follow)
    [[ $# -le 1 ]] || { usage; exit 2; }
    show_logs "${command}" "${1:-}"
    ;;
  view)
    [[ $# -eq 0 ]] || { usage; exit 2; }
    exec ros2 run rqt_image_view rqt_image_view /vision/assembly/image --ros-args -p image_transport:=compressed
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    echo "Unknown command: ${command}" >&2
    usage
    exit 2
    ;;
esac
