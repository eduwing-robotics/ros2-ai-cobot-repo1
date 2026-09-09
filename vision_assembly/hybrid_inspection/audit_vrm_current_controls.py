"""Evaluate bounded labelled VRM saved-image replays without changing runtime policy."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from audit_confirmed_controls import ROOT, validate_image

CONFIG = ROOT / 'vision_assembly/config/vrm_presence_context_holdout_20260905.json'


def presence_outcome(truth, state):
    if state not in ('EMPTY', 'CORRECT', 'ROTATED', 'PRESENT'):
        return 'ABSTAIN'
    return 'MATCH' if (truth == 'EMPTY') == (state == 'EMPTY') else 'MISMATCH'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-directory', type=Path, required=True)
    args = parser.parse_args()
    config_bytes = CONFIG.read_bytes()
    config = json.loads(config_bytes)
    selected = ('141311', '141603', '142337')
    rows = []
    for stamp in selected:
        scene = next(s for s in config['scenes'] if s['image'].endswith(f'_{stamp}.png'))
        reports = list(args.output_directory.glob(f'replay_{stamp}/*/hybrid_report.json'))
        if len(reports) != 1:
            raise ValueError(f'Expected exactly one replay for {stamp}, got {len(reports)}')
        path = reports[0]
        report = json.loads(path.read_text())
        digest = validate_image(report)
        source_hash = hashlib.sha256((ROOT / scene['image']).read_bytes()).hexdigest()
        if digest != source_hash or (scene.get('image_sha256') and digest != scene['image_sha256']):
            raise ValueError('Labelled image/replay mismatch')
        for slot_id, truth in scene['labels'].items():
            matches = [s for s in report['slots'] if s['slot_id'] == slot_id]
            if len(matches) != 1:
                raise ValueError('Missing or duplicate labelled slot')
            stages = matches[0]['stages']
            p = stages['presence']
            items = report.get('advisory_candidates', {}).get('items', [])
            codes = [code for c in items if c['slot_id'] == slot_id for code in c['codes']]
            rows.append(dict(scene=scene['physical_scene_id'], slot=slot_id,
                             source_hash=digest, label_source=scene['label_source'],
                             historical_label_hash_available=bool(scene.get('image_sha256')),
                             report=str(path), presence_truth=truth,
                             state=p.get('predicted_state'), presence_status=p.get('status'),
                             presence_reason=p.get('reason'), presence_confidence=p.get('confidence'),
                             presence_outcome=presence_outcome(truth, p.get('predicted_state')),
                             expected_pose=scene.get('expected_pose', {}).get(slot_id),
                             defect_reason=scene.get('defect_reason', {}).get(slot_id),
                             pose_status=stages.get('pose', {}).get('status'),
                             codes=codes, fused_board_status=report['status']))
    normal_path = ROOT / 'runtime/inspection/hybrid_fixed_slot/20260907_134026_750188/hybrid_report.json'
    normal_old = json.loads(normal_path.read_text())
    normal_reports = list(args.output_directory.glob('normal_134016/*/hybrid_report.json'))
    if len(normal_reports) != 1:
        raise ValueError('Expected one current normal replay')
    normal = json.loads(normal_reports[0].read_text())
    if validate_image(normal) != validate_image(normal_old):
        raise ValueError('Normal source mismatch')
    normal_rows = []
    for sid in ('vrm_03', 'vrm_05'):
        stage = next(s for s in normal['slots'] if s['slot_id'] == sid)['stages']
        normal_rows.append(dict(slot=sid, truth='NORMAL_POSITION',
                                provenance='audit_vrm_mixed_false_positive.py: latest user-confirmed normal only',
                                report=str(normal_reports[0]),
                                pose_status=stage['pose']['status'],
                                candidates=[c for c in normal['advisory_candidates']['items'] if c['slot_id'] == sid]))
    payload = dict(rows=rows, normal_position_controls=normal_rows,
                   label_config_sha256=hashlib.sha256(config_bytes).hexdigest(),
                   presence_counts=dict(Counter(r['presence_outcome'] for r in rows)),
                   independent_accuracy_claim=False, runtime_changed=False,
                   robot_command_sent=False, conveyor_command_sent=False,
                   limitations=['Reused historical development/holdout controls; not independent deployment accuracy.',
                                'Presence labels do not imply normal pose, pins or surface.',
                                'Model states and advisory candidates do not grant production verdict authority.',
                                'Missing historical image hashes are explicitly marked; current source hashes are verified.'])
    with (args.output_directory / 'audit.json').open('x') as stream:
        json.dump(payload, stream, indent=2)
        stream.write('\n')
    print(json.dumps(payload, indent=2))


if __name__ == '__main__':
    main()
