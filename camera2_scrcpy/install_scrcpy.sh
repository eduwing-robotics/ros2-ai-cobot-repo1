#!/usr/bin/env bash
set -euo pipefail

version="4.1"
archive="scrcpy-linux-x86_64-v${version}.tar.gz"
expected_sha256="ad56ae8bfeedf41e824945c11dbf55fcb092b3e615b9b486f48a50e30d389635"
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tools_dir="${project_dir}/runtime/tools"
install_dir="${tools_dir}/scrcpy-linux-x86_64-v${version}"
download_path="${tools_dir}/${archive}"
url="https://github.com/Genymobile/scrcpy/releases/download/v${version}/${archive}"

mkdir -p "${tools_dir}"
if [[ -x "${install_dir}/scrcpy" ]]; then
  "${install_dir}/scrcpy" --version
  exit 0
fi

curl -fL "${url}" -o "${download_path}"
printf '%s  %s\n' "${expected_sha256}" "${download_path}" | sha256sum --check
tar -xzf "${download_path}" -C "${tools_dir}"
"${install_dir}/scrcpy" --version

