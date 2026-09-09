"""Measure original-coordinate column displacement; never compensate or judge pins."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from audit_hbm_pin_columns import locate_columns


def displacement(reference, sample):
    if reference.shape != sample.shape:
        raise ValueError('Mismatched crops')
    r, s = locate_columns(reference), locate_columns(sample)
    y = reference.shape[0] * .4
    result = {}
    for side in ('left', 'right'):
        a, b = r[side], s[side]
        out = {'status': 'UNKNOWN', 'reference_reason': a['reason'], 'sample_reason': b['reason'],
               'dx_px': None, 'comparison_y_px': y, 'reference_anchors': a['anchors_px'],
               'sample_anchors': b['anchors_px']}
        if a['fit'] is not None and b['fit'] is not None:
            out['dx_px'] = ((b['fit']['x_per_y']-a['fit']['x_per_y'])*y
                            + b['fit']['x_intercept']-a['fit']['x_intercept'])
            # Nearest y distances describe pattern mismatch, not pin identity.
            ay, by = np.array(a['anchors_px'])[:,1], np.array(b['anchors_px'])[:,1]
            out['nearest_y_distance_median_px'] = float(np.median(np.min(np.abs(ay[:,None]-by[None,:]),axis=1)))
        result[side] = out
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root/'vision_assembly/config/hbm_pin_reference.json').read_text())
    rows = []
    for run in args.run:
        for slot, entry in manifest['slots'].items():
            paths = [root/entry['path'], run/'fixed_slots/hbm'/f'{slot}.png']
            hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
            if hashes[0] != entry['sha256']:
                raise ValueError('Reference hash mismatch')
            images = [cv2.imread(str(p)) for p in paths]
            if any(im is None for im in images):
                raise ValueError('Unreadable crop')
            sides = displacement(*[cv2.cvtColor(im,cv2.COLOR_BGR2RGB) for im in images])
            rows.append({'run': str(run), 'slot_id': slot, 'sha256': hashes, 'sides': sides})
            print(run.name, slot, {side: round(v['dx_px'],2) if v['dx_px'] is not None else None for side,v in sides.items()})
    with args.output.open('x') as stream:
        json.dump({'authority':'OFFLINE_ONLY','status':'UNKNOWN','rows':rows,
                   'limitation':'No compensation; nearest y distances do not identify individual pins or their loss'},stream,indent=2)


if __name__ == '__main__':
    main()
