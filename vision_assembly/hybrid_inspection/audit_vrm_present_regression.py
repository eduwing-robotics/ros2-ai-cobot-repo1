"""Check missing-candidate false positives only on explicitly PRESENT controls."""
import argparse
import hashlib
import json
from pathlib import Path

from audit_confirmed_controls import ROOT, validate_image


def evaluate(directory):
    config_path = ROOT / 'vision_assembly/config/vrm_presence_context_holdout_20260905.json'
    config_bytes = config_path.read_bytes()
    scenes = json.loads(config_bytes)['scenes']
    rows = []
    for stamp in ('170142', '185803'):
        scene = next(s for s in scenes if s['image'].endswith(f'_{stamp}.png'))
        paths = list(directory.glob(f'extended_normal_{stamp}/*/hybrid_report.json'))
        if len(paths) != 1:
            raise ValueError(f'Expected one completed replay for {stamp}')
        report = json.loads(paths[0].read_text())
        digest = validate_image(report)
        if digest != scene['image_sha256']:
            raise ValueError('Historical label source hash mismatch')
        for sid, truth in scene['labels'].items():
            if truth != 'PRESENT':
                continue
            matches = [s for s in report['slots'] if s['slot_id'] == sid]
            if len(matches) != 1:
                raise ValueError('Missing or duplicate labelled slot')
            slot = matches[0]
            context = slot.get('vrm_presence_context') or {}
            codes = [code for c in report['advisory_candidates']['items'] if c['slot_id'] == sid
                     for code in c['codes']]
            rows.append(dict(scene=scene['physical_scene_id'], slot=sid, truth='PRESENT',
                             input_sha256=digest, provenance=scene['label_source'],
                             report=str(paths[0]), presence=slot['stages']['presence'],
                             context=context, codes=codes, missing_false_positive='MISSING?' in codes,
                             evaluated=context.get('available') is True,
                             fused_board_status=report['status']))
    return dict(rows=rows, label_config_sha256=hashlib.sha256(config_bytes).hexdigest(),
                labelled_present=len(rows), context_unavailable=sum(not r['evaluated'] for r in rows),
                missing_false_positives=sum(r['missing_false_positive'] for r in rows),
                scope='PRESENCE_DISPLAY_ONLY_NOT_POSE_ACCURACY', independent_validation=False,
                robot_command_sent=False, conveyor_command_sent=False,
                limitation='Reused labelled scenes. Wall-near PRESENT does not certify gripper clearance or physical seating.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.directory)
    with (args.directory / 'extended_normal_summary.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
