"""Join current offline replays to labelled controls by exact source hash and slot."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from audit_confirmed_controls import validate_image


def summarize(audit, reports):
    index = {}
    for path in reports:
        report = json.loads(path.read_text())
        digest = validate_image(report)
        if digest in index:
            raise ValueError('duplicate replay for source image')
        index[digest] = (path, report)
    rows, missing = [], []
    for control in audit['rows']:
        if control['track'] != 'direction' or control['truth'] != 'NORMAL':
            continue
        entry = index.get(control['input_sha256'])
        if entry is None:
            missing.append(control)
            continue
        path, report = entry
        slots = [s for s in report['slots'] if s['slot_id'] == control['slot']]
        if len(slots) != 1:
            raise ValueError('missing or duplicate labelled slot')
        stage = slots[0]['stages'].get('orientation', {})
        candidates = report.get('advisory_candidates', {}).get('items', [])
        codes = [code for c in candidates if c['slot_id'] == control['slot']
                 for code in c.get('codes', [])]
        rows.append(dict(slot=control['slot'], input_sha256=control['input_sha256'],
                         provenance=control['provenance'], truth='NORMAL_DIRECTION',
                         report=str(path), report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         orientation_status=stage.get('status', 'UNKNOWN'),
                         reason=stage.get('reason'), confidence=stage.get('confidence'),
                         advisory_codes=codes, fused_board_status=report.get('status')))
    return dict(mode='CURRENT_FULL_PIPELINE_SAVED_IMAGE_REPLAY', rows=rows,
                missing=missing, orientation_counts=dict(Counter(r['orientation_status'] for r in rows)),
                limitations=['Reused development controls, not independent validation.',
                             'Only labelled normal inductor direction is evaluated; other tasks are unlabelled.',
                             'Stage PASS does not grant production PASS; surface warnings are not direction errors.'],
                robot_command_sent=False, conveyor_command_sent=False, fresh_capture=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    audit = json.loads((args.directory / 'audit.json').read_text())
    result = summarize(audit, sorted(args.directory.glob('normal_replay_*/*/hybrid_report.json')))
    with (args.directory / 'normal_current_summary.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(counts=result['orientation_counts'], missing=len(result['missing']))))


if __name__ == '__main__':
    main()
