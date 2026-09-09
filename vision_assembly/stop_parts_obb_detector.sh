#!/usr/bin/env bash
set -eo pipefail
pid_file="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/runtime/parts_obb_detector.pid"
if [[ ! -f "${pid_file}" ]]; then
  echo 'Parts OBB detector is not running.'
  exit 0
fi
pid="$(<"${pid_file}")"
if kill -0 "${pid}" 2>/dev/null; then
  echo "Stopping Parts OBB detector (node PID ${pid})..."
  kill -INT -- "-${pid}" 2>/dev/null || kill -INT "${pid}" 2>/dev/null || true
  for _ in {1..50}; do
    kill -0 "${pid}" 2>/dev/null || break
    sleep 0.1
  done
  if kill -0 "${pid}" 2>/dev/null; then
    echo 'Graceful shutdown timed out; sending SIGTERM.' >&2
    kill -TERM -- "-${pid}" 2>/dev/null || kill -TERM "${pid}" 2>/dev/null || true
    for _ in {1..20}; do
      kill -0 "${pid}" 2>/dev/null || break
      sleep 0.1
    done
  fi
  if kill -0 "${pid}" 2>/dev/null; then
    echo "Could not stop Parts OBB detector PID ${pid}." >&2
    exit 1
  fi
  echo "Stopped Parts OBB detector (node PID ${pid})."
else
  echo 'Removed stale Parts OBB PID file.'
fi
rm -f "${pid_file}"
