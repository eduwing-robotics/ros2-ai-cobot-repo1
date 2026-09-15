#!/usr/bin/env bash
set -Eeuo pipefail

# Start the conveyor server and the S22/ROI stack as one owned cell. This is
# intentionally separate from the team-managed ROS-TCP endpoint: the endpoint
# process and its port 10000 lifecycle remain the teammate's responsibility.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${PROJECT_DIR}/scripts/ksmc_env.sh"

usage() {
  cat <<'EOF'
Usage:
  run_conveyor_cell.sh --monitor-only
  run_conveyor_cell.sh --execute --confirm-motion

The server starts in IDLE/armed (depending on the selected mode); it never
issues a move at startup. Ctrl+C stops only the conveyor server and any S22
launcher started by this command. A pre-existing S22 launcher is reused and
is left running when this command exits.
EOF
}

if [[ ($# -eq 1 && "$1" == "--help") || ($# -eq 1 && "$1" == "-h") ]]; then
  usage
  exit 0
fi
if [[ ! (($# -eq 1 && "$1" == "--monitor-only") || \
         ($# -eq 2 && "$1" == "--execute" && "$2" == "--confirm-motion")) ]]; then
  usage >&2
  exit 2
fi

SERVER_PID=""
S22_PID=""
S22_OWNED=0

find_existing_s22_launcher() {
  local proc pid cwd args arg resolved
  for proc in /proc/[0-9]*; do
    pid="${proc#/proc/}"
    [[ "${pid}" == "$$" ]] && continue
    [[ -r "${proc}/cmdline" ]] || continue
    cwd="$(readlink -f "${proc}/cwd" 2>/dev/null || true)"
    args="$(tr '\0' '\n' <"${proc}/cmdline" 2>/dev/null || true)"
    # A launcher can appear as `bash ./run_s22_conveyor_hq.sh` or with an
    # absolute path. Compare the resolved script argument instead of requiring
    # one spelling; otherwise --with-s22 starts a second HQ launcher, whose
    # startup cleanup kills the first launcher's ROI and camera.
    while IFS= read -r arg; do
      case "${arg}" in
        run_s22_conveyor_hq.sh|./run_s22_conveyor_hq.sh|*/run_s22_conveyor_hq.sh)
          if [[ "${arg}" == /* ]]; then
            resolved="$(readlink -f -- "${arg}" 2>/dev/null || true)"
          else
            resolved="$(readlink -f -- "${cwd}/${arg}" 2>/dev/null || true)"
          fi
          if [[ "${resolved}" == "${PROJECT_DIR}/run_s22_conveyor_hq.sh" ]]; then
            printf '%s\n' "${pid}"
            return 0
          fi
          ;;
      esac
    done <<<"${args}"
  done
  return 1
}

group_alive() {
  local pgid="${1:-}"
  [[ "${pgid}" =~ ^[0-9]+$ ]] || return 1
  # `setsid` below makes the PID a dedicated process-group ID. Looking for a
  # non-zombie member handles both the ros2 CLI parent and its executable
  # child, while treating a lock-refused zombie as stopped.
  ps -eo pgid=,stat= 2>/dev/null |
    awk -v wanted="${pgid}" '$1 == wanted && $2 !~ /^Z/ {found=1} END {exit(found ? 0 : 1)}'
}

signal_group() {
  local pgid="${1:-}"
  [[ "${pgid}" =~ ^[0-9]+$ ]] || return 0
  kill -INT -- "-${pgid}" 2>/dev/null || true
}

cleanup() {
  local pid any_alive
  # Signal only process groups started by this launcher. Each entrypoint has
  # its own cleanup trap; no process-name pkill is used here.
  for pid in "${S22_PID}" "${SERVER_PID}"; do
    if group_alive "${pid}"; then
      signal_group "${pid}"
    fi
  done
  for _ in {1..40}; do
    any_alive=0
    for pid in "${S22_PID}" "${SERVER_PID}"; do
      if group_alive "${pid}"; then
        any_alive=1
      fi
    done
    (( any_alive == 0 )) && break
    sleep 0.2
  done
  for pid in "${S22_PID}" "${SERVER_PID}"; do
    if group_alive "${pid}"; then
      kill -TERM -- "-${pid}" 2>/dev/null || true
    fi
    [[ "${pid}" =~ ^[0-9]+$ ]] && wait "${pid}" 2>/dev/null || true
  done
}

on_signal() {
  exit 130
}
trap cleanup EXIT
trap on_signal INT TERM

# Acquire the conveyor server first. If another server already owns the
# command lock, this exits before touching the camera stack.
echo '[KSMC Cell] Starting the conveyor remote server.'
# Dedicated process groups let cleanup stop the ros2 CLI and its executable
# child together, including the lock-holding process.
setsid "${PROJECT_DIR}/run_conveyor_remote_server.sh" "$@" &
SERVER_PID=$!
sleep 1
if ! group_alive "${SERVER_PID}"; then
  wait "${SERVER_PID}" 2>/dev/null || true
  echo '[KSMC Cell] Conveyor server did not stay running; S22 was not started.' >&2
  exit 1
fi

existing_s22=""
if existing_s22="$(find_existing_s22_launcher)"; then
  echo "[KSMC Cell] Reusing existing S22/ROI launcher (PID ${existing_s22})."
  echo '[KSMC Cell] The reused launcher is external and will not be stopped here.'
else
  echo '[KSMC Cell] Starting S22 camera and assembly/inspection ROI.'
  setsid "${PROJECT_DIR}/run_s22_conveyor_hq.sh" &
  S22_PID=$!
  S22_OWNED=1
fi

# A concurrent HQ invocation can win the short race between the /proc scan and
# the child startup lock. If that child refused because an existing launcher
# owns the lock, reuse the existing launcher instead of tearing down the
# already-running server.
if (( S22_OWNED )) && ! group_alive "${S22_PID}"; then
  if existing_s22="$(find_existing_s22_launcher)"; then
    echo "[KSMC Cell] S22 startup raced with an existing launcher (PID ${existing_s22}); reusing it."
    S22_PID=""
    S22_OWNED=0
  else
    echo '[KSMC Cell] S22/ROI launcher exited during startup.' >&2
    exit 1
  fi
fi

# Give a newly started HQ launcher time to bring up scrcpy and ROI. Process
# liveness is the gate here; camera readiness/stop-line evidence remains the
# conveyor server's existing interlock and is never replaced by a sleep.
for _ in {1..15}; do
  if ! group_alive "${SERVER_PID}"; then
    echo '[KSMC Cell] Conveyor server exited during startup.' >&2
    exit 1
  fi
  if (( S22_OWNED )) && ! group_alive "${S22_PID}"; then
    echo '[KSMC Cell] S22/ROI launcher exited during startup.' >&2
    exit 1
  fi
  sleep 1
done

if (( S22_OWNED )); then
  echo "[KSMC Cell] Cell is running (server PID ${SERVER_PID}, S22 PID ${S22_PID})."
else
  echo "[KSMC Cell] Cell is running (server PID ${SERVER_PID}, reused S22 PID ${existing_s22})."
fi
echo '[KSMC Cell] Endpoint port 10000 is not started by this command.'

while true; do
  if ! group_alive "${SERVER_PID}"; then
    echo '[KSMC Cell] Conveyor server exited; stopping owned peers.' >&2
    exit 1
  fi
  if (( S22_OWNED )) && ! group_alive "${S22_PID}"; then
    echo '[KSMC Cell] S22/ROI launcher exited; stopping the conveyor server.' >&2
    exit 1
  fi
  sleep 2
done
