"""Fixed-frame boundary displacement evidence, never a seating/height verdict."""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def displacement(reference, current):
    result = dict(status='UNKNOWN', authority='ADVISORY_ONLY', measured_height_mm=None,
                  confirmed_defect=False)
    arrays = []
    for row in (reference, current):
        samples = row['samples']
        if len(samples) != 5 or any(s['unique_count'] != 1 or s['primary'] is None for s in samples):
            return dict(result, reason='BOUNDARY_SAMPLING_UNAVAILABLE_OR_AMBIGUOUS')
        bounds = np.asarray([s['primary']['extent_in_fixed_crop'] for s in samples], dtype=float)
        if bounds.shape != (5, 4) or not np.isfinite(bounds).all():
            raise ValueError('Invalid boundary extents')
        arrays.append(bounds)
    a, b = arrays
    return dict(result, reason='FIXED_FRAME_DISPLACEMENT_EVIDENCE',
        edge_order=['left', 'top', 'right', 'bottom'],
        delta_lower_px=(b.min(axis=0)-a.max(axis=0)).tolist(),
        delta_upper_px=(b.max(axis=0)-a.min(axis=0)).tolist(),
        note='Range across artificial crop-window perturbations, not a statistical confidence interval. '
             'Relative to one normal placement, not a measured socket wall or acceptance limit.')


def main():
    directory = ROOT / 'runtime/inspection/vrm_seating_pairs'
    results = []
    for name in ('boundary320', 'boundary640'):
        data = json.loads((directory/name/'report.json').read_text())
        normal, lip = data['rows']
        assert normal['label'] == 'flat' and lip['label'] == 'seating'
        results.append(dict(provider=name, weights_sha256=data['weights_sha256'],
            source_hashes=[normal['source_sha256'], lip['source_sha256']],
            evidence=displacement(normal, lip)))
    (directory/'boundary_displacement.json').write_text(json.dumps(dict(results=results,
        runtime_changed=False, training=False, robot_command_sent=False,
        conveyor_command_sent=False), indent=2))
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
