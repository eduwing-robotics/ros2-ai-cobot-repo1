"""Replay retained evidence, checking scope, inputs and SMD01 nominations."""
import json
from copy import deepcopy
from pathlib import Path
from main import build_advisory_candidates

ROOT = Path(__file__).resolve().parents[2]


def main():
    base = ROOT/'runtime/inspection'
    cases = json.loads((base/'smd01_small_lip_candidate_20260907.json').read_text())['results'][0]['cases']
    cases = [(Path(c['report']), c['truth']) for c in cases]
    for stamp, truth in [('121829_086609','defect'), ('122104_842085','normal'),
                         ('130800_689089','defect'), ('131107_594576','normal')]:
        cases.append((base/f'hybrid_fixed_slot/20260907_{stamp}/hybrid_report.json',truth))
    rows = []
    for path, truth in cases:
        report = json.loads(path.read_text())
        original = deepcopy(report['slots'])
        result = build_advisory_candidates(report['slots'])
        assert report['slots'] == original, 'Provider evidence mutated'
        codes = [c for c in result if c['slot_id']=='smd_capacitor_01']
        old_other = [c for c in report['advisory_candidates']['items'] if c['slot_id']!='smd_capacitor_01']
        new_other = [c for c in result if c['slot_id']!='smd_capacitor_01']
        # Reports may include renderer metadata; compare semantic codes only.
        signature = lambda items: {c['slot_id']: sorted(c['codes']) for c in items}
        assert signature(old_other) == signature(new_other), f'Other slot changed: {path}'
        assert bool(codes) == (truth=='defect'), f'Unexpected nomination: {path}'
        assert all(c['authority']=='ADVISORY_ONLY' and not c['confirmed_defect'] for c in codes)
        rows.append(dict(report=str(path),truth=truth,codes=[c['codes'] for c in codes]))
    out = base/'smd01_small_lip_integration_20260907.json'
    out.write_text(json.dumps(dict(rows=rows,count=len(rows),all_matched=True,
        limitation='Saved evidence integration replay, includes development and repeated placements; not independent accuracy.'),indent=2))
    print(f'{len(rows)} cases matched; other-slot codes and raw stages unchanged')


if __name__=='__main__':
    main()
