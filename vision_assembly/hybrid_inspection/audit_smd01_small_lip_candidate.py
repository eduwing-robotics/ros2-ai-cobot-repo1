"""Offline small-lip candidate. Never changes the live inspection policy."""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def main():
    base = ROOT / 'runtime/inspection'
    samples = []
    for folder, truth in [('smd01_normal_original_replay_20260907', 'normal'),
                          ('smd01_original_current_replay_20260907', 'defect')]:
        samples += [(p, truth) for p in sorted((base/folder).glob('*/hybrid_report.json'))]
    repeats = {'140856': 'defect', '141001': 'defect', '142332': 'normal',
               '142427': 'normal', '143229': 'defect', '143450': 'defect'}
    for path in sorted((base/'smd01_extended_replay_20260907').glob('*/hybrid_report.json')):
        report = json.loads(path.read_text())
        stamp = Path(report['input_image']).stem.rsplit('_', 1)[-1]
        samples.append((path, repeats[stamp]))
    for stamp, truth in [('114134_401329', 'normal'), ('120417_894943', 'normal'),
                         ('120657_287426', 'normal'), ('120941_804840', 'defect')]:
        samples.append((base/f'hybrid_fixed_slot/20260907_{stamp}/hybrid_report.json', truth))
    rows = []
    for path, truth in samples:
        report = json.loads(path.read_text())
        slot = next(s for s in report['slots'] if s['slot_id']=='smd_capacitor_01')
        stages = slot['stages']
        rows.append(dict(report=str(path), truth=truth,
                         raw_y=float(stages['pose']['measured']['raw_offset_mm'][1]),
                         confidence=stages['pose']['confidence'],
                         presence=stages['presence'].get('predicted_state'),
                         presence_confidence=stages['presence']['confidence'],
                         score=stages['surface']['score'],
                         current=any(c['slot_id']=='smd_capacitor_01' for c in report['advisory_candidates']['items'])))
    normal_y = [r['raw_y'] for r in rows if r['truth']=='normal']
    # Engineering sensitivity sweep, NOT fitted physical tolerance. The 0.25mm
    # nominal-scale probe exceeds the observed 2.5px centroid discrepancy.
    results = []
    for margin in [.20, .25, .30, .35]:
        lower, upper = min(normal_y)-margin, max(normal_y)+margin
        cases = []
        for row in rows:
            outside = row['raw_y'] < lower or row['raw_y'] > upper
            supplemental = bool(outside and row['presence']=='PRESENT'
                                and row['presence_confidence'] >= .90
                                and row['confidence'] >= .20 and row['score'] >= .10)
            cases.append(dict(**row, supplemental=supplemental,
                              combined=row['current'] or supplemental))
        results.append(dict(margin=margin, lower=lower, upper=upper,
                            normal_flags=sum(r['combined'] for r in cases if r['truth']=='normal'),
                            defect_hits=sum(r['combined'] for r in cases if r['truth']=='defect'),
                            cases=cases))
    out = base/'smd01_small_lip_candidate_20260907.json'
    out.write_text(json.dumps(dict(normal_count=len(normal_y),defect_count=len(rows)-len(normal_y),
        results=results, runtime_changed=False,
        limitation='Development sensitivity only; normals define envelope, latest defect motivated '
                   'the branch. Not holdout accuracy. Shared bias not removed in this candidate; '
                   'board registration and independent new scene validation required. No live thresholds changed.'),indent=2))
    print(json.dumps([dict(margin=r['margin'], normal_flags=r['normal_flags'],defect_hits=r['defect_hits']) for r in results]))


if __name__ == '__main__':
    main()
