"""Offline signed-axis separation and leave-one-normal-out stability audit."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def envelope_audit(points, normal):
    points = np.asarray(points, dtype=float)
    normal = np.asarray(normal, dtype=bool)
    good, bad = points[normal], points[~normal]
    if len(good) < 3 or not len(bad):
        raise ValueError('Need at least three normals and one defect')
    low, high = good.min(axis=0), good.max(axis=0)
    # Signed outside distance on each axis; positive means outside normal box.
    outside = np.maximum(low - bad, bad - high)
    loo = []
    for i, point in enumerate(good):
        remaining = np.delete(good, i, axis=0)
        residual = np.maximum(remaining.min(axis=0)-point, point-remaining.max(axis=0))
        loo.append(np.maximum(residual, 0).tolist())
    return dict(normal_min=low.tolist(), normal_max=high.tolist(),
                defect_outside_by_axis=outside.tolist(),
                leave_one_normal_out_required_expansion=loo,
                max_normal_expansion=np.max(loo, axis=0).tolist())


def main():
    base = ROOT / 'runtime/inspection'
    data = json.loads((base / 'smd01_center_comparison_20260907/audit.json').read_text())['rows']
    normal = [r['truth'] in ('normal', 'user_restored_normal') for r in data]
    result = {'sources': [dict(source=r['source'], truth=r['truth']) for r in data]}
    for name, field in [('raw_xy_mm', 'raw_offset_mm'), ('corrected_xy_mm', 'offset_mm')]:
        result[name] = envelope_audit([r['measured'][field] for r in data], normal)
    result['policy'] = ('Six selected development scenes, historical measurements. '
                        'No threshold fitted or deployed. Leave-one-out extrema test is '
                        'a stability diagnostic, not production accuracy. Millimetres '
                        'are nominal board-scale estimates, not measured socket clearance.')
    result['runtime_changed'] = False
    (base / 'smd01_directional_limits_20260907.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
