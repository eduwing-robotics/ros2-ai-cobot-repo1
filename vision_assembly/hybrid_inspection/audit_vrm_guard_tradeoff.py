"""Offline sensitivity review, never a threshold selector or runtime writer."""
import argparse
import hashlib
import json
import math
from pathlib import Path

try:
    from .vrm_boundary_advisory import BASE, LEFT, WEIGHT_HASH, measure
except ImportError:
    from vrm_boundary_advisory import BASE, LEFT, WEIGHT_HASH, measure

ROOT = Path(__file__).resolve().parents[2]


def guard_flags(excess, guards=(1., 2., 3., 4.)):
    if len(excess) != 2 or not all(math.isfinite(v) for v in excess):
        raise ValueError('Two finite excess values required')
    return {str(g): all(v > g for v in excess) for g in guards}


def summarize(rows, guard):
    selected = [r for r in rows if r['intent'] in ('LEFT_SEATED', 'RIGHT_SHIFT')]
    return {label: {'count': sum(r['intent'] == label for r in selected),
                    'flagged': sum(r['intent'] == label and r['flags'][guard] for r in selected)}
            for label in ('LEFT_SEATED', 'RIGHT_SHIFT')}


def audit(fresh_report, output):
    hashes = {}
    def read(path):
        blob = path.read_bytes()
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(blob).hexdigest()
        return json.loads(blob)
    def saved(stamp):
        report = read(BASE / f'fresh_s22_inspection_roi_20260906_{stamp}_last/report.json')
        if report['weights_sha256'] != WEIGHT_HASH:
            raise ValueError('Boundary weight identity mismatch')
        return report
    refs = {}
    for stamp in LEFT:
        for row in saved(stamp)['rows']:
            value = measure(row['primary']['polygon'], row['crop_origin_px'])
            refs.setdefault(row['slot'], []).append(value['position'])
    margins = [max(max(p[i] for p in v)-min(p[i] for p in v) for v in refs.values())
               for i in range(3)]
    labels = read(BASE / 'placement_uncertainty_replay.json')
    rows = []
    seen = set()
    for item in labels['rows']:
        if item['intent'] not in ('LEFT_SEATED', 'RIGHT_SHIFT'):
            continue
        stamp, sid = item['capture'], item['slot']
        if (stamp, sid) in seen:
            raise ValueError('Repeated scene/slot; resolve provenance first')
        seen.add((stamp, sid))
        row = next(r for r in saved(stamp)['rows'] if r['slot'] == sid)
        value = measure(row['primary']['polygon'], row['crop_origin_px'])
        if value is None:
            raise ValueError('Missing boundary in review case')
        excess = [value['position'][i]-max(p[i] for p in refs[sid])-margins[i] for i in (0, 2)]
        rows.append(dict(capture=stamp, slot=sid, intent=item['intent'],
                         reference_member=stamp in LEFT, excess_px=excess, flags=guard_flags(excess)))
    fresh = read(fresh_report)
    observations = []
    for row in fresh['slots']:
        stage = row['stages'].get('vrm_boundary', {})
        if 'right_excess_px' not in stage:
            continue
        observations.append(dict(slot=row['slot_id'], codes=stage['codes'],
                                 excess_px=stage['right_excess_px'],
                                 flags=guard_flags(stage['right_excess_px'])))
    result = dict(authority='ADVISORY_ONLY', runtime_changed=False, selected_guard=None,
                  summary={str(g): summarize(rows, str(g)) for g in (1., 2., 3., 4.)},
                  rows=rows, fresh_reserved_observations=observations, source_hashes=hashes,
                  limitations=['Sensitivity analysis only; no selected threshold.',
                               'Historical intent is not measured wall clearance or height.',
                               'Reference scenes overlap historical normal controls.',
                               'Fresh reserved scene is not used for fitting or threshold selection.',
                               'Repeated slots in a scene are not independent trials.'])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fresh-report', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = audit(args.fresh_report.resolve(), args.output.resolve())
    print(json.dumps(result['summary'], indent=2))
