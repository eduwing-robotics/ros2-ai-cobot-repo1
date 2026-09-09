"""Replay saved geometry without inference; never installs a calibration."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'runtime/inspection'


def main():
    sources = {
        'historical_normal': 'hybrid_vrm_pose_calibration_normal_151315/20260904_190832_071549/hybrid_report.json',
        'historical_lip': 'hybrid_vrm02_lip_repeat_gpu_180801/20260904_181923_667872/hybrid_report.json',
        'current_normal_165914': 'vrm_bridge_full_report_test/20260905_172632_641217/hybrid_report.json',
        'current_normal_170142': 'vrm_bridge_full_report_test/20260905_174122_517050/hybrid_report.json',
    }
    reference = np.array([-0.7187, 0.2383])
    rows = []
    for label, source in sources.items():
        report = json.loads((BASE/source).read_text())
        slot = next(s for s in report['slots'] if s['slot_id'] == 'vrm_02')
        m = slot['stages']['pose']['measured']
        raw = np.array(m['raw_offset_mm'])
        bias = np.array(m['common_bias_correction_mm'])
        rows.append(dict(case=label, source=source, raw_mm=raw.tolist(),
                         common_bias_mm=bias.tolist(),
                         current_reference_error_mm=float(np.linalg.norm(raw-bias-reference)),
                         same_centroid_without_common_bias_mm=float(np.linalg.norm(raw-reference))))
    # Same image/centroid/reference: only the availability of the common term changes.
    normal = rows[0]
    assert normal['current_reference_error_mm'] < .70
    assert normal['same_centroid_without_common_bias_mm'] > .70
    result = dict(rows=rows, reproducible_context_sensitive_warning=True,
                  authority='ADVISORY_ONLY', runtime_changed=False,
                  note='Diagnostic counterfactual, not a proposed replacement calibration. '
                       'Do not infer physical millimetres from an uncalibrated segmentation centroid. '
                       'Whole-board registration must be independent of part occupancy.',
                  robot_command_sent=False, conveyor_command_sent=False)
    out = BASE/'vrm02_pose_boundary_review/context_audit.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
