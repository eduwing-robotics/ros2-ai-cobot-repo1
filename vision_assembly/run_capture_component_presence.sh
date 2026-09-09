#!/usr/bin/env bash
set -Eeo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
venv="${script_dir}/.venv_patchcore"
latest="${project_dir}/runtime/inspection/s22_inspection_roi_latest.png"
skip_capture=0
collector_args=()

if [[ ! -x "${venv}/bin/python" ]]; then
  echo "Missing inspection environment: ${venv}" >&2
  exit 1
fi

for arg in "$@"; do
  case "${arg}" in
    -h|--help)
      exec "${venv}/bin/python" \
        "${script_dir}/slot_classifier/component_presence_dataset.py" --help
      ;;
    --skip-capture)
      skip_capture=1
      ;;
    --image|--image=*)
      echo 'The fresh ROI path is managed by this launcher.' >&2
      exit 2
      ;;
    *)
      collector_args+=("${arg}")
      ;;
  esac
done

before="$(readlink -f "${latest}" 2>/dev/null || true)"
if (( ! skip_capture )); then
  S22_INSPECTION_FLASH=off \
  S22_INSPECTION_ZOOM="${S22_INSPECTION_ZOOM:-3.5}" \
    "${project_dir}/run_s22_optical_inspection.sh"
fi
after="$(readlink -f "${latest}" 2>/dev/null || true)"
if [[ -z "${after}" ]] || [[ ! -f "${after}" ]]; then
  echo 'A valid S22 inspection ROI was not produced.' >&2
  exit 1
fi
if (( ! skip_capture )) && [[ -n "${before}" ]] && [[ "${after}" == "${before}" ]]; then
  echo 'Refusing to archive a stale S22 ROI.' >&2
  exit 1
fi

exec "${venv}/bin/python" \
  "${script_dir}/slot_classifier/component_presence_dataset.py" \
  "${collector_args[@]}" \
  --image "${after}"
