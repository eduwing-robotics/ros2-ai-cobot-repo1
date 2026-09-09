"""Counterfactual diagnostic; never reuse a previous frame bias in production."""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def main():
    base = ROOT/'runtime/inspection/hybrid_fixed_slot'
    before = json.loads((base/'20260907_132341_467727/hybrid_report.json').read_text())
    after = json.loads((base/'20260907_134026_750188/hybrid_report.json').read_text())
    results = []
    for sid in ['vrm_03','vrm_05']:
        old = next(s for s in before['slots'] if s['slot_id']==sid)['stages']
        new = next(s for s in after['slots'] if s['slot_id']==sid)['stages']
        a,b = old['pose']['measured'],new['pose']['measured']
        frozen = np.array(b['raw_offset_mm'])-a['common_bias_correction_mm']-b['slot_reference_correction_mm']
        boundary = new['vrm_boundary']
        limits = boundary['position_bounds_px']
        margins = boundary['position_margin_px']
        results.append(dict(slot_id=sid, raw_delta_mm=(np.array(b['raw_offset_mm'])-a['raw_offset_mm']).tolist(),
            bias_delta_mm=(np.array(b['common_bias_correction_mm'])-a['common_bias_correction_mm']).tolist(),
            current_radial_mm=b['position_error_mm'],
            counterfactual_previous_bias_radial_mm=float(np.linalg.norm(frozen)),
            boundary_delta_px=(np.array(boundary['measured']['position'])-old['vrm_boundary']['measured']['position']).tolist(),
            boundary_right_excess_px=[boundary['measured']['position'][i]-limits[i][1]-margins[i] for i in [0,2]]))
    out = ROOT/'runtime/inspection/vrm_mixed_false_positive_audit_20260907.json'
    out.write_text(json.dumps(dict(rows=results,
        policy='Diagnostic only: no cached previous-frame correction in runtime, no thresholds changed. '
               'User confirms latest VRM03/05 normal. Does not imply all historical VRMs normal.'),indent=2))
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    main()
