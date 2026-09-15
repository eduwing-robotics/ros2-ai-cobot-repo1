"""Descriptive multi-feature envelope replay; never a production verdict."""
import hashlib
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1'
WEIGHTS = '98572682b1df4aef452d7d5727c3cf6acf6abc7e6d954fdce7a214046d6f10cc'
LEFT = ['152933', '153345', '153918', '154722', '155607', '160026']
RIGHT = {'153632': [4], '154508': [2], '155131': [1, 2, 3, 4, 5]}


def features(row):
    p = row['primary']
    if not p:
        return None
    x, y = row['crop_origin_px']
    return [p['center_px'][0] + x, p['center_px'][1] + y,
            max(v[0] for v in p['polygon']) + x]


def compare(sample, references, uncertainty=None):
    if sample is None or not references or any(r is None for r in references):
        return 'UNKNOWN'
    bounds = [(min(r[i] for r in references), max(r[i] for r in references)) for i in range(3)]
    if not all(math.isfinite(v) for r in [sample, *references] for v in r):
        return 'UNKNOWN'
    margin = uncertainty if uncertainty is not None else [0, 0, 0]
    if len(margin) != 3 or any(not math.isfinite(v) or v < 0 for v in margin):
        return 'UNKNOWN'
    if all(lo <= value <= hi for value, (lo, hi) in zip(sample, bounds)):
        return 'WITHIN_OBSERVED_LEFT_ENVELOPE'
    if sample[0] > bounds[0][1] + margin[0] and sample[2] > bounds[2][1] + margin[2]:
        return 'RIGHT_SHIFT_CANDIDATE'
    return 'UNKNOWN'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--uncertainty-aware', action='store_true')
    args = parser.parse_args()
    frames = {}
    for stamp in sorted(set(LEFT) | set(RIGHT) | {'161036'}):
        report = json.loads((BASE / f'fresh_s22_inspection_roi_20260906_{stamp}_last/report.json').read_text())
        assert report['weights_sha256'] == WEIGHTS
        for row in report['rows']:
            assert hashlib.sha256(Path(row['source_image']).read_bytes()).hexdigest() == row['image_sha256']
        frames[stamp] = {r['slot']: r for r in report['rows']}
    results = []
    for number in range(1, 6):
        slot = f'vrm_{number:02d}'
        for stamp in frames:
            if stamp in RIGHT and number not in RIGHT[stamp]:
                continue
            # Leave each normal capture out; never test its self-fitted envelope.
            refs = [features(frames[t][slot]) for t in LEFT if t != stamp]
            sample = features(frames[stamp][slot])
            # Pool the largest normal range across slots, excluding the entire
            # evaluated capture. This is a development heuristic, not calibrated noise.
            margin = [0.0, 0.0, 0.0]
            if args.uncertainty_aware:
                for ref_slot in frames[LEFT[0]]:
                    pool = [features(frames[t][ref_slot]) for t in LEFT if t != stamp]
                    if len(pool) < 2 or any(p is None for p in pool):
                        raise ValueError('Insufficient normal references')
                    margin = [max(margin[i], max(p[i] for p in pool)-min(p[i] for p in pool)) for i in range(3)]
            results.append(dict(slot=slot, capture=stamp,
                                intent='LEFT_SEATED' if stamp in LEFT else 'RIGHT_SHIFT' if stamp in RIGHT else 'UNLABELLED_MIDDLE',
                                evidence=compare(sample, refs, margin), uncertainty_px=margin, status='UNKNOWN'))
    summary = {}
    for row in results:
        key = row['intent'] + '/' + row['evidence']
        summary[key] = summary.get(key, 0) + 1
    output = BASE / ('placement_uncertainty_replay.json' if args.uncertainty_aware else 'placement_envelope_replay.json')
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(dict(authority='ADVISORY_ONLY', runtime_enabled=False,
        summary=summary, rows=results, uncertainty_aware=args.uncertainty_aware,
        limitation='Development replay, not independent validation. Optional margin is maximum normal feature range pooled across slots, a heuristic proposed after observed false alarm; not calibrated uncertainty. Entire evaluated normal scene excluded. No defect-based margin optimization. Borderline evidence stays UNKNOWN, not PASS. Axis angle and vertical seating are not certified. No millimeter conversion or part recentering.'), indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
