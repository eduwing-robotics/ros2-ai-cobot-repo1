"""Read-only archived-provider review of the SMD01 pixel deadband."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from main import build_advisory_candidates
from smd01_small_lip import RULE

ROOT = Path(__file__).resolve().parents[2]


def run(output):
    original = RULE['boundary_deadband_px']
    try:
        RULE['boundary_deadband_px'] = 1.0
        return _run(output)
    finally:
        RULE['boundary_deadband_px'] = original


def _run(output):
    base = ROOT / 'runtime/inspection'
    source = base / 'smd01_small_lip_candidate_20260907.json'
    cases = [(Path(c['report']), c['truth']) for c in
             json.loads(source.read_text())['results'][0]['cases']]
    for stamp, truth in [('121829_086609', 'defect'), ('122104_842085', 'normal'),
                         ('130800_689089', 'defect'), ('131107_594576', 'normal')]:
        cases.append((base/f'hybrid_fixed_slot/20260907_{stamp}/hybrid_report.json', truth))
    for run_dir, truth in [
        ('smd01_lip_validation_20260908_132035/20260908_132108_768224', 'defect'),
        ('smd01_recovery_20260908_132402/20260908_132425_543863', 'normal')]:
        cases.append((base/run_dir/'hybrid_report.json', truth))
    rows, seen = [], set()
    for path, truth in cases:
        if not path.is_absolute():
            path = ROOT / path
        blob = path.read_bytes()
        report = json.loads(blob)
        image = Path(report['input_image'])
        if not image.is_absolute():
            image = ROOT/image
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        if digest != report['input_sha256']:
            raise ValueError('Image hash mismatch')
        if digest in seen:
            continue
        seen.add(digest)
        slots = deepcopy(report['slots'])
        original_stages = [deepcopy(s['stages']) for s in slots]
        candidates = build_advisory_candidates(slots)
        assert [s['stages'] for s in slots] == original_stages
        candidate = [c for c in candidates if c['slot_id'] == 'smd_capacitor_01']
        rows.append(dict(report=str(path), report_sha256=hashlib.sha256(blob).hexdigest(),
                         input_sha256=digest, truth=truth, candidates=candidate,
                         matched=bool(candidate) == (truth == 'defect')))
    result = dict(rows=rows, mismatches=[r for r in rows if not r['matched']],
                  independent_validation=False, authority='ADVISORY_ONLY',
                  limitation='Archived providers and reused labels, not new model inference or physical metrology.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as f:
        json.dump(result, f, indent=2)
    print(json.dumps(dict(count=len(rows), mismatches=len(result['mismatches']),
                          failed=[(r['report'],r['truth']) for r in result['mismatches']])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    run(p.parse_args().output)
