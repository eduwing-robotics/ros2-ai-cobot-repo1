#!/usr/bin/env bash
set -euo pipefail
export ROS_DOMAIN_ID=5

package_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
setup_file="$package_root/install/setup.bash"
build_marker="$package_root/install/.built_for"

set +e +u
[[ -f "$HOME/.bashrc" ]] && source "$HOME/.bashrc"
set -euo pipefail

needs_build=false
if [[ ! -f "$setup_file" || ! -f "$build_marker" || "$(<"$build_marker")" != "$package_root" ]]; then
  needs_build=true
elif find "$package_root/src" "$package_root/install.sh" -type f ! -path "*/__pycache__/*" ! -name "*.pyc" -newer "$build_marker" -print -quit | grep -q .; then
  needs_build=true
fi

if [[ "$needs_build" == true ]]; then
  echo "Endpoint install is missing, copied, or stale; building it now..."
  if ! "$package_root/install.sh"; then
    echo "Endpoint automatic build failed." >&2
    exit 1
  fi
fi
set +u
source "$setup_file"
set -u

endpoint_prefix="$(ros2 pkg prefix ros_tcp_endpoint 2>/dev/null || true)"
if [[ "$endpoint_prefix" != "$package_root/install/ros_tcp_endpoint" ]]; then
  echo "This folder's ros_tcp_endpoint build is not active." >&2
  echo "Remove copied build/install/log and run ./run.sh again." >&2
  exit 1
fi
if ! ros2 pkg prefix fairino_msgs >/dev/null 2>&1; then
  echo "Warning: fairino_msgs is unavailable; real robot message types will not work." >&2
fi
exec ros2 run ros_tcp_endpoint default_server_endpoint --ros-args \
  -p ROS_IP:="${ROS_IP:-0.0.0.0}" \
  -p ROS_TCP_PORT:="${ROS_TCP_PORT:-10000}"
