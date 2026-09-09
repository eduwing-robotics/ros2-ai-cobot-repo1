"""Summarize explicitly documented Sept4 repeat captures, without calibration."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {'140856': True, '141001': True, '142332': False,
            '142427': False, '143229': True, '143450': True}


def main():
    directory = ROOT / 'runtime/inspection/smd01_extended_replay_20260907'
    results = {}
    for path in sorted(directory.glob('*/hybrid_report.json')):
        report = json.loads(path.read_text())
        source = Path(report['input_image'])
        stamp = source.stem.rsplit('_', 1)[-1]
        if stamp not in EXPECTED:
            raise ValueError(f'Unexpected input: {source}')
        if stamp in results:
            raise ValueError(f'Duplicate replay: {stamp}')
        slot = next(s for s in report['slots'] if s['slot_id'] == 'smd_capacitor_01')
        items = [c for c in report['advisory_candidates']['items'] if c['slot_id'] == 'smd_capacitor_01']
        codes = sorted({code for c in items for code in c['codes']})
        results[stamp] = dict(report=str(path), source=str(source),
            sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            truth='seating_defect' if EXPECTED[stamp] else 'normal', codes=codes,
            matched=(bool(codes) == EXPECTED[stamp]),
            seating_retained='SEATING?' in codes,
            slot_status=slot['status'],
            pose=slot['stages']['pose']['measured'],
            surface_score=slot['stages']['surface']['score'])
    missing = sorted(set(EXPECTED)-set(results))
    payload = dict(rows=results, missing=missing,
        complete=not missing, matched_count=sum(r['matched'] for r in results.values()),
        policy='Labels from Sept4 grouped work log; same physical trials repeated, '
               'NOT independent scenes or production accuracy. SMD01-only ground truth. '
               'No model fitting, runtime mutation, new capture or motion.')
    (directory / 'summary.json').write_text(json.dumps(payload, indent=2))
    print(json.dumps(dict(missing=missing, rows={k:dict(truth=v['truth'],codes=v['codes'],matched=v['matched'])
                                               for k,v in results.items()}), indent=2))
    if missing:
        raise RuntimeError('Incomplete replay; do not report final counts')


if __name__ == '__main__':
    main()
