"""Saved-data sensitivity and historical control audit. No runtime authority."""
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path
from replay_vrm_placement_envelopes import BASE, LEFT, RIGHT, WEIGHTS, compare, features


def load_frames():
    frames, provenance = {}, {}
    for path in sorted(BASE.glob('fresh_s22_inspection_roi_20260906_*_last/report.json')):
        stamp = path.parent.name.split('_')[-2]
        report = json.loads(path.read_text())
        if report['weights_sha256'] != WEIGHTS:
            raise ValueError('Weight mismatch')
        for row in report['rows']:
            if hashlib.sha256(Path(row['source_image']).read_bytes()).hexdigest() != row['image_sha256']:
                raise ValueError('Image changed')
        frames[stamp] = {r['slot']: r for r in report['rows']}
        provenance[stamp] = hashlib.sha256(path.read_bytes()).hexdigest()
    return frames, provenance


def reference(frames, stamps):
    if len(stamps) < 2 or len(set(stamps)) != len(stamps):
        raise ValueError('Need distinct reference captures')
    refs = {slot: [features(frames[t][slot]) for t in stamps] for slot in frames[stamps[0]]}
    if any(p is None for values in refs.values() for p in values):
        raise ValueError('Missing reference geometry')
    margin = [max(max(p[i] for p in values)-min(p[i] for p in values)
                  for values in refs.values()) for i in range(3)]
    return refs, margin


def main():
    output = BASE / 'placement_robustness_audit.json'
    if output.exists():
        raise FileExistsError(output)
    frames, provenance = load_frames()
    folds = []
    for excluded in itertools.combinations(LEFT, 2):
        train = [t for t in LEFT if t not in excluded]
        refs, margin = reference(frames, train)
        counts, alarms = Counter(), []
        for stamp in excluded:
            for slot, row in frames[stamp].items():
                evidence = compare(features(row), refs[slot], margin)
                counts['left/' + evidence] += 1
                if evidence == 'RIGHT_SHIFT_CANDIDATE':
                    alarms.append([stamp, slot])
        for stamp, numbers in RIGHT.items():
            for number in numbers:
                slot = f'vrm_{number:02d}'
                counts['right/' + compare(features(frames[stamp][slot]), refs[slot], margin)] += 1
        folds.append(dict(excluded=excluded, reference_captures=train,
                          margin_px=margin, counts=dict(counts), false_candidates=alarms))
    refs, margin = reference(frames, LEFT)
    history = []
    for stamp in ['131407', '131700', '132000', '132330', '132543', '141441']:
        for slot, row in frames[stamp].items():
            initial = frames['131407'][slot]['primary']
            p = row['primary']
            angle = None if not p or not initial else (p['long_axis_deg']-initial['long_axis_deg']+90)%180-90
            history.append(dict(capture=stamp, slot=slot, mask_present=p is not None,
                                right_evidence=compare(features(row), refs[slot], margin),
                                angle_delta_from_initial_deg=angle, status='UNKNOWN'))
    presence = Counter()
    for stamp in ['131700', '132000']:
        metadata = json.loads((BASE / f'fresh_s22_inspection_roi_20260906_{stamp}_last/observation.json').read_text())
        for slot, truth in metadata['observed_presence'].items():
            found = frames[stamp][slot]['primary'] is not None
            presence[f'{truth}/mask_{found}'] += 1
    totals = Counter()
    for fold in folds:
        totals.update(fold['counts'])
    result = dict(authority='ADVISORY_ONLY', runtime_enabled=False, status='UNKNOWN',
                  report_sha256=provenance, weights_sha256=WEIGHTS,
                  folds=folds, repeated_fold_totals=dict(totals), presence_controls=dict(presence),
                  historical_controls=history,
                  limitation='15 overlapping leave-two-scene-out folds, not150 independent normals or105 independent defects. Historical normal captures precede left-flush requirement: do not relabel them. Rotation angles are descriptive; missing mask is not an authoritative EMPTY verdict. No threshold tuning or runtime changes.')
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps(dict(fold_count=len(folds), repeated_fold_totals=dict(totals),
                         false_candidate_cases=sorted({tuple(x) for f in folds for x in f['false_candidates']}),
                         presence_controls=dict(presence),
                         vrm4_controls=[r for r in history if r['slot']=='vrm_04']), indent=2))


if __name__ == '__main__':
    main()
