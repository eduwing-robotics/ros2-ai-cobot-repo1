#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="${script_dir}"
vendor_dir="${workspace_dir}/src/vendor"
classroom_src="${CLASSROOM_FR5_SRC:-${HOME}/fr5_jazzy_test_ws/src}"
upstream_url="https://github.com/FAIR-INNOVATION/frcobot_ros2.git"
upstream_commit="867cb32bc24a73c1e60bef4e6c16762e7357c5e1"

usage() {
  echo "Usage: $0 --from-classroom-workspace | --from-official"
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

mkdir -p "${vendor_dir}"

case "$1" in
  --from-classroom-workspace)
    for package in fairino_msgs fairino_hardware_v3_9_7 fairino_description fairino5_v6_moveit2_config; do
      if [[ ! -d "${classroom_src}/${package}" ]]; then
        echo "Missing source package: ${classroom_src}/${package}" >&2
        exit 1
      fi
      if [[ -e "${vendor_dir}/${package}" ]]; then
        echo "Already exists: ${vendor_dir}/${package}" >&2
        exit 1
      fi
      cp -a "${classroom_src}/${package}" "${vendor_dir}/${package}"
    done
    ;;
  --from-official)
    checkout_dir="${vendor_dir}/frcobot_ros2"
    if [[ -e "${checkout_dir}" ]]; then
      echo "Already exists: ${checkout_dir}" >&2
      exit 1
    fi
    git clone "${upstream_url}" "${checkout_dir}"
    git -C "${checkout_dir}" checkout --detach "${upstream_commit}"
    ;;
  *)
    usage
    exit 2
    ;;
esac

echo "FAIRINO vendor source prepared under ${vendor_dir}"
echo "This directory is intentionally excluded from KSMC Git history."
