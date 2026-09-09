"""Replay stored evidence without modifying captures or provider measurements."""
import json
from pathlib import Path
from main import build_advisory_candidates

ROOT=Path(__file__).resolve().parents[2]


def main():
    sources={
      'hybrid_fixed_slot/20260906_205818_570243':'normal',
      'hybrid_smd01_lip_worst_normal_regression/20260904_141942_759205':'normal',
      'hybrid_all_smd_recovery_full_142508/20260904_142746_328777':'normal',
      'hybrid_smd01_lip_seating_verified/20260904_141847_556412':'defect',
      'hybrid_smd_mixed_verified/20260904_144104_172098':'defect'}
    rows=[]
    for source,label in sources.items():
        report=json.loads((ROOT/'runtime/inspection'/source/'hybrid_report.json').read_text())
        slot=next(r for r in report['slots'] if r['slot_id']=='smd_capacitor_01')
        candidates=build_advisory_candidates([slot])
        codes=candidates[0]['codes'] if candidates else []
        rows.append(dict(source=source,label=label,codes=codes,
                         correct=not codes if label=='normal' else bool(codes),
                         measured=slot['stages']['pose'].get('measured'),
                         sha256=report.get('input_sha256')))
    out=ROOT/'runtime/inspection/smd01_normal_margin_20260906.json'
    out.write_text(json.dumps(dict(rows=rows,all_passed=all(r['correct'] for r in rows),
        limitation='Five selected development scenes; raw evidence replay, not fresh image inference or production validation.'),indent=2))
    print(json.dumps([dict(label=r['label'],codes=r['codes'],correct=r['correct']) for r in rows]))
    if not all(r['correct'] for r in rows):
        raise RuntimeError('Regression failure')


if __name__=='__main__':
    main()
