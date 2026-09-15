#!/usr/bin/env bash
set -Eeo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
latest="${project_dir}/runtime/inspection/s22_inspection_roi_latest.png"
for arg in "$@"; do
  if [[ "${arg}" == "--help" ]] || [[ "${arg}" == "-h" ]]; then
    exec python3 "${script_dir}/segmentation/archive_s22_capture.py" --help
  fi
done
before="$(readlink -f "${latest}" 2>/dev/null || true)"

S22_INSPECTION_FLASH="${S22_INSPECTION_FLASH:-off}" \
S22_INSPECTION_ZOOM="${S22_INSPECTION_ZOOM:-3.5}" \
  "${project_dir}/run_s22_optical_inspection.sh"

after="$(readlink -f "${latest}" 2>/dev/null || true)"
if [[ -z "${after}" ]] || [[ ! -f "${after}" ]]; then
  echo 'Fresh S22 inspection ROI was not created.' >&2
  exit 1
fi
if [[ -n "${before}" ]] && [[ "${after}" == "${before}" ]]; then
  echo 'Capture finished without replacing the latest S22 ROI; refusing stale reuse.' >&2
  exit 1
fi

exec python3 "${script_dir}/segmentation/archive_s22_capture.py" "$@"
