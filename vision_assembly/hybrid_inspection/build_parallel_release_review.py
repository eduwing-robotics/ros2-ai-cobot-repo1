"""Consolidate verification evidence, without promoting providers or production results."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review_report(report):
    counts = Counter()
    authoritative_fail = []
    unavailable = []
    for slot in report.get('slots', []):
        for stage_name, stage in slot.get('stages', {}).items():
            authority = stage.get('authority', 'MISSING')
            counts[authority] += 1
            if authority == 'AUTHORITATIVE' and stage.get('status') == 'FAIL':
                authoritative_fail.append(dict(slot=slot.get('slot_id'), stage=stage_name))
            if authority in ('UNAVAILABLE', 'DISABLED', 'INVALID', 'MISSING'):
                unavailable.append(dict(slot=slot.get('slot_id'), stage=stage_name, authority=authority))
    # Review-only output: even an authority string is not independent validation.
    return dict(production_decision=report.get('status', 'UNKNOWN'),
                stage_authority_counts=dict(counts), unavailable=unavailable,
                reported_authoritative_failures=authoritative_fail,
                review_disposition='NOT_RELEASED',
                provider_promotion_performed=False,
                reason='Independent validation and calibration must be evidenced before release; this tool never promotes.')


def build(report_path, evidence_paths):
    report = json.loads(report_path.read_text())
    source = Path(report['input_image'])
    if sha(source) != report['input_sha256']:
        raise ValueError('Source image hash mismatch')
    evidence = []
    for path in evidence_paths:
        content = json.loads(path.read_text())
        evidence.append(dict(path=str(path.resolve()), sha256=sha(path), content=content))
    return dict(schema_version=1, purpose='RELEASE_READINESS_NOT_INSPECTION_RESULT',
                current_report=str(report_path.resolve()), report_sha256=sha(report_path),
                source_sha256=report['input_sha256'], review=review_report(report),
                evidence=evidence, runtime_changed=False,
                robot_command_sent=False, conveyor_command_sent=False,
                limitation='Parallel processing shortens review time, not the evidence required for confirmed PASS/FAIL.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--evidence', nargs='+', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.report, args.evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result['review'], indent=2))


if __name__ == '__main__':
    main()
