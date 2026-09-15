"""Replay frozen spatial seating candidates; never fit or promote a model."""
import argparse
import hashlib
import json
import re
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision import models, transforms

from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper
from vrm_seating_common import crop_vrm_seating_slot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--candidates', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(2)
    cropper = FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    source = cv2.imread(str(args.image))
    if source is None:
        raise ValueError('Unreadable image')
    board = cropper.register(source)
    if board.alignment_reason != 'OK' or board.alignment_score < float(cropper.config['global_alignment']['minimum_score']):
        raise ValueError('Uncertain registration; no pose decision')
    slots = [s for s in cropper.fixed_slots(board.image_bgr) if s.component_type == 'VRM']
    if len(slots) != 5:
        raise ValueError('Expected five VRM slots')
    transform = transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(),
        transforms.Normalize((.485, .456, .406), (.229, .224, .225))])
    batch = torch.stack([transform(Image.fromarray(cv2.cvtColor(
        crop_vrm_seating_slot(board.image_bgr, s.geometry), cv2.COLOR_BGR2RGB))) for s in slots])
    model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1).features.eval()
    with torch.inference_mode():
        early_features = model[:6](batch)
        features = model[6:](early_features)
    reports = []
    for directory in args.candidates:
        metadata = json.loads((directory/'evaluation.json').read_text())
        method=metadata['method']
        multiscale=method.startswith('frozen_B0_layer5_final_')
        match = re.fullmatch(r'frozen_B0_spatial([1-47])x\1_logistic_C1', method.replace('layer5_final_', ''))
        if not match:
            raise ValueError('Unsupported feature extraction contract')
        size = int(match.group(1))
        x = torch.nn.functional.adaptive_avg_pool2d(features, (size, size)).flatten(1).numpy()
        if multiscale:
            early=torch.nn.functional.adaptive_avg_pool2d(early_features,(size,size)).flatten(1).numpy()
            x=np.concatenate([early,x],axis=1)
        artifact = directory/'candidate.npz'
        with np.load(artifact, allow_pickle=False) as head:
            if not np.array_equal(head['classes'], [0, 1]) or head['coef'].shape != (1, x.shape[1]):
                raise ValueError('Incompatible classifier')
            z = (x @ head['coef'].T + head['intercept']).ravel()
        scores = 1/(1+np.exp(-np.clip(z, -700, 700)))
        reports.append(dict(candidate=str(directory), sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
            rows=[dict(slot=s.slot_id, seating_score=float(p), diagnostic_warning=bool(p >= .5),
                       status='UNKNOWN') for s, p in zip(slots, scores)]))
    report = dict(image=str(args.image), image_sha256=hashlib.sha256(args.image.read_bytes()).hexdigest(),
        alignment_score=board.alignment_score, authority='ADVISORY_ONLY', runtime_enabled=False,
        training_performed=False, note='Uncalibrated diagnostic threshold 0.5; no warning is not PASS. Presence is not evaluated.',
        robot_command_sent=False, conveyor_command_sent=False, candidates=reports)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
