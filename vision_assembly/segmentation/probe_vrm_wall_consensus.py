"""Check repeatability of wall candidates without declaring their physical identity."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def shared_candidates(first, second, tolerance=3):
    if tolerance<0:
        raise ValueError('Negative tolerance')
    return [dict(first_x=a['x'],second_x=b['x'],difference_px=abs(a['x']-b['x']))
            for a in first for b in second if abs(a['x']-b['x'])<=tolerance]


def main():
    base=ROOT/'vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1/socket_wall_probe'
    data=json.loads((base/'report.json').read_text())
    a,b=[r for r in data['rows'] if r['empty_reference']]
    result=dict(status='UNKNOWN',authority='ADVISORY_ONLY',runtime_enabled=False,
        diagnostic_repeatability_band_px=3,
        clahe_pairs=shared_candidates(a['clahe_candidates'],b['clahe_candidates']),
        raw_pairs=shared_candidates(a['raw_candidates'],b['raw_candidates']),
        limitation='Three pixels is a diagnostic comparison band, not calibrated wall uncertainty. Repeatable edges may be shadows or socket bottom edges, not the gripper-entry wall at component height. No mm conversion or clearance verdict.')
    path=base/'consensus.json'
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
