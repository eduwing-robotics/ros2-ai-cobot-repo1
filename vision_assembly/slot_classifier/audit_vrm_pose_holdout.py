"""Read-only model regression on user-labelled presence/pose holdouts."""
import json
from dataclasses import asdict
from pathlib import Path

import cv2
import torch

from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper
from preprocessor_and_cropper import VrmStateClassifier, VrmSeatingClassifier


def main():
    torch.set_num_threads(2)
    spec = json.loads((ROOT / 'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())
    cropper = FixedSlotCropper(ROOT / 'vision_assembly/config/full_board_inspection.json')
    models = ROOT / 'vision_assembly/slot_classifier/models'
    state = VrmStateClassifier(models, device='cpu')
    seating = VrmSeatingClassifier(models, device='cpu')
    rows = []
    for scene in spec['scenes']:
        board = cropper.register(cv2.imread(str(ROOT / scene['image'])))
        if board.alignment_reason != 'OK' or board.alignment_score < float(cropper.config['global_alignment']['minimum_score']):
            raise ValueError('Uncertain registration: ' + scene['image'])
        for slot in cropper.fixed_slots(board.image_bgr):
            if slot.component_type != 'VRM':
                continue
            evidence = state.inspect(slot, board.image_bgr)
            row = dict(image=scene['image'], slot=slot.slot_id,
                       expected_presence=scene['labels'][slot.slot_id],
                       expected_pose=scene.get('expected_pose', {}).get(slot.slot_id),
                       state=asdict(evidence),
                       seating=asdict(seating.inspect(slot, board.image_bgr,
                           non_empty_confidence=0.0)),
                       final_status='UNKNOWN')
            rows.append(row)
    output = ROOT / 'runtime/inspection/vrm_pose_holdout_audit_20260905.json'
    output.write_text(json.dumps(dict(authority='ADVISORY_ONLY',
        note='No model refit or activation. Seating respects disabled runtime metadata.',
        robot_command_sent=False, conveyor_command_sent=False, rows=rows), indent=2))
    for row in rows:
        if row['expected_pose']:
            print(json.dumps(row))
    print(output)


if __name__ == '__main__':
    main()
