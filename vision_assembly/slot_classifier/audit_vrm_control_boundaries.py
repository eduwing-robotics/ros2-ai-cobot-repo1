"""Compare frozen boundary diagnostics, never turn mask drift into a verdict."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def summarize(rows, baseline, expected):
    references = {r['slot']: r for r in rows if r['stamp'] == baseline}
    output = []
    for row in rows:
        if row['stamp'] == baseline:
            continue
        current, reference = row['grabcut'], references[row['slot']]['grabcut']
        if current is None or reference is None:
            output.append(dict(stamp=row['stamp'], slot=row['slot'], status='UNKNOWN', reason='NO_BOUNDARY'))
            continue
        center, size, angle = current['rect']
        rc, rs, ra = reference['rect']
        # Axis-normalized sizes solely for diagnostics; no image is transformed.
        width_height = sorted(size)
        reference_size = sorted(rs)
        delta = (np.array(center)-rc).tolist()
        output.append(dict(stamp=row['stamp'], slot=row['slot'],
            expected=expected[row['stamp']][row['slot']], status='UNKNOWN',
            center_delta_px=delta, center_distance_px=float(np.linalg.norm(delta)),
            size_ratio=(np.array(width_height)/reference_size).tolist(),
            fill=current['fill'], reference_fill=reference['fill'],
            axis_angle_delta_deg=float((angle-ra+45)%90-45),
            note='Mask-derived position, not measured socket clearance or seating height.'))
    return output


def main():
    directory = ROOT/'runtime/inspection/vrm_outline_controls_160027'
    report = json.loads((directory/'edges.json').read_text())
    manifest = json.loads((ROOT/'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())
    expected = {Path(s['image']).stem.rsplit('_', 1)[-1]: s['expected_pose']
                for s in manifest['scenes'] if s.get('expected_pose')}
    rows = summarize(report['rows'], '154927', expected)
    normals = [r['center_distance_px'] for r in rows if r.get('expected') == 'PASS']
    defects = [r['center_distance_px'] for r in rows if r.get('expected') == 'FAIL']
    result = dict(authority='ADVISORY_ONLY', runtime_enabled=False, baseline='154927',
        normal_max_center_delta_px=max(normals), defect_min_center_delta_px=min(defects),
        center_threshold_separates_controls=bool(max(normals) < min(defects)),
        conclusion='Do not use center-only threshold when control distributions overlap. Mask instability and physical displacement are not separated.',
        robot_command_sent=False, conveyor_command_sent=False, rows=rows)
    (directory/'boundary_deltas.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
