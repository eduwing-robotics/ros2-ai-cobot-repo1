#!/usr/bin/env bash
set -Eeo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
latest="${project_dir}/runtime/inspection/s22_inspection_roi_latest.png"
skip_capture=0
predict_args=()
for arg in "$@"; do
  if [[ "${arg}" == "--help" ]] || [[ "${arg}" == "-h" ]]; then
    exec "${project_dir}/vision_assembly/run_predict_s22_segmentation.sh" --help
  elif [[ "${arg}" == "--skip-capture" ]]; then
    skip_capture=1
  else
    predict_args+=("${arg}")
  fi
done

if (( ! skip_capture )); then
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
    echo 'Refusing to infer from a stale S22 ROI.' >&2
    exit 1
  fi
fi

exec "${project_dir}/vision_assembly/run_predict_s22_segmentation.sh" \
  "${predict_args[@]}"
