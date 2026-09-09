"""Offline reference-locked pin evidence. No alignment or production verdict."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from audit_hbm_pin_columns import locate_columns


def compare_columns(reference, sample, *, lateral_probe=False):
    columns = locate_columns(reference)
    sample_columns = locate_columns(sample)
    if reference.shape != sample.shape:
        raise ValueError('Crop shapes differ')
    masks = []
    for rgb in (reference, sample):
        masks.append((cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)[:, :, 0] >= 130)
                     & (cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[:, :, 1] <= 105))
    dx = 0.0
    correction_usable = True
    if lateral_probe:
        shifts = []
        for side in ('left', 'right'):
            a, b = columns[side]['fit'], sample_columns[side]['fit']
            if a is not None and b is not None:
                shifts.append((b['x_per_y']-a['x_per_y'])*reference.shape[0]*.4
                              +b['x_intercept']-a['x_intercept'])
        correction_usable = len(shifts)==2 and abs(shifts[0]-shifts[1])<=2 and max(map(abs,shifts))<=12
        if correction_usable:
            dx = float(np.mean(shifts))
    result = {}
    for side, column in columns.items():
        item = {'status': 'UNKNOWN', 'reason': 'REFERENCE_COLUMN_UNRESOLVED', 'anchors': []}
        result[side] = item
        item['lateral_probe_dx_px'] = dx
        item['reference_y_locked'] = True
        if lateral_probe and not correction_usable:
            item['reason'] = 'PAIRED_COLUMN_SHIFT_UNRESOLVED'
            continue
        if column['fit'] is None:
            continue
        for x, y, _ in column['anchors_px']:
            cx, cy = int(round(x)), int(round(y))
            region = (slice(max(0, cy-3), cy+4), slice(max(0, cx-3), cx+4))
            sx = int(round(x+dx))
            if sx-3 < 0 or sx+4 > sample.shape[1]:
                raise ValueError('Shifted evidence window clipped')
            sample_region = (region[0], slice(sx-3,sx+4))
            base = int(masks[0][region].sum())
            current = int(masks[1][sample_region].sum())
            item['anchors'].append({'xy_px': [x, y], 'reference_white': base,
                                    'sample_white': current, 'ratio': current / base if base else None})
        valid = [a for a in item['anchors'] if a['ratio'] is not None]
        retained = sum(a['ratio'] >= .3 for a in valid)
        item['retained_anchors'] = retained
        item['near_absent_xy_px'] = [a['xy_px'] for a in valid if a['ratio'] < .05]
        item['reason'] = ('SAMPLE_SUPPORT_UNRESOLVED' if retained < 3 else
                          'REFERENCE_WHITE_DEFICIT_CANDIDATE' if item['near_absent_xy_px'] else
                          'NO_NEAR_ABSENCE_AT_TESTED_ANCHORS')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--lateral-probe', action='store_true', help='Offline paired-column x-only correction; no y fitting')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root/'vision_assembly/config/hbm_pin_reference.json').read_text())
    rows = []
    for run in args.run:
        for slot, entry in manifest['slots'].items():
            ref = root / entry['path']
            if hashlib.sha256(ref.read_bytes()).hexdigest() != entry['sha256']:
                raise ValueError('Reference hash mismatch')
            path = run/'fixed_slots/hbm'/f'{slot}.png'
            images = []
            for file in (ref, path):
                bgr = cv2.imread(str(file))
                if bgr is None:
                    raise ValueError(str(file))
                images.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
            sides = compare_columns(*images, lateral_probe=args.lateral_probe)
            rows.append({'run': str(run), 'slot_id': slot, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'reference_sha256': entry['sha256'], 'sides': sides})
            print(run.name, slot, {s: (v['reason'], len(v.get('near_absent_xy_px', []))) for s,v in sides.items()})
    with args.output.open('x') as stream:
        json.dump({'authority': 'OFFLINE_ONLY', 'status': 'UNKNOWN',
                   'lateral_probe': args.lateral_probe,
                   'limitation': 'No lower endpoint coverage; no pose/lighting compensation or calibrated pin verdict', 'rows': rows}, stream, indent=2)


if __name__ == '__main__':
    main()
