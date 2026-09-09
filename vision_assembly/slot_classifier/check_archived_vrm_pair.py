"""Offline frozen seating diagnostic; never activates or trains a model."""
import json
import sys
from dataclasses import asdict
import cv2
import torch
from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper

sys.path.insert(0, str(ROOT / 'vision_assembly/hybrid_inspection'))
from preprocessor_and_cropper import VrmSeatingClassifier


def main():
    torch.set_num_threads(2)
    bridge = ROOT / 'runtime/inspection/vrm_seating_fresh_vrm5_20260907/integration_bridge'
    metadata = json.loads((bridge / 'vrm_seating.json').read_text())
    assert metadata['runtime_enabled'] is False
    provider = VrmSeatingClassifier(bridge, device='cpu')
    provider.model = torch.jit.load(str(bridge / 'vrm_seating.torchscript.pt')).eval()
    provider.model_path = bridge / 'vrm_seating.torchscript.pt'
    provider.metadata = {**metadata, 'runtime_enabled': True, 'seating_min_probability': .5}
    cropper = FixedSlotCropper(ROOT / 'vision_assembly/config/full_board_inspection.json')
    rows = []
    for timestamp in ('183823', '184132'):
        archive = ROOT / f'runtime/inspection/vrm_seating_pairs/s22_inspection_roi_20260907_{timestamp}'
        scene = json.loads((archive / 'scene.json').read_text())
        board = cropper.register(cv2.imread(scene['image']))
        assert board.alignment_reason == 'OK'
        assert board.alignment_score >= float(cropper.config['global_alignment']['minimum_score'])
        slot = next(s for s in cropper.fixed_slots(board.image_bgr) if s.slot_id == 'vrm_05')
        # Known physical presence is diagnostic input, not an inferred production gate.
        result = provider.inspect(slot, board.image_bgr, non_empty_confidence=.99)
        rows.append(dict(scene=scene, result=asdict(result)))
    output = ROOT / 'runtime/inspection/vrm_seating_pairs/frozen_pair_check.json'
    output.write_text(json.dumps(dict(rows=rows, runtime_changed=False, training=False,
        diagnostic_only=True, presence_assumed=True, robot_command_sent=False,
        conveyor_command_sent=False), indent=2))
    for row in rows:
        print(row['scene']['seating_label'], row['result'])


if __name__ == '__main__':
    main()
