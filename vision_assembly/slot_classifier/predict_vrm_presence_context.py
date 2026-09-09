"""Run the frozen two-region VRM presence candidate without refitting it."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import torch
from torchvision import models, transforms

from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper, central_rgb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, default=ROOT/'runtime/inspection/vrm_presence_context_stress_20260905')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    metadata = json.loads((args.candidate/'evaluation.json').read_text())
    if metadata['method'] != 'central55_context130_RGB_frozen_EfficientNetB0_logistic_C1':
        raise ValueError('Candidate feature contract mismatch')
    artifact = args.candidate/'classifier_candidate.npz'
    with np.load(artifact,allow_pickle=False) as params:
        coef,intercept,classes = params['coef'],params['intercept'],params['classes']
    if classes.tolist()!=[0,1] or coef.shape!=(1,2560) or intercept.shape!=(1,):
        raise ValueError('Unexpected classifier shape/order')
    torch.set_num_threads(2)
    model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1)
    model.classifier = torch.nn.Identity()
    model.eval()
    transform = transforms.Compose([transforms.Resize((224,224)),transforms.ToTensor(),
        transforms.Normalize((.485,.456,.406),(.229,.224,.225))])
    cropper = FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    board = cropper.register(cv2.imread(str(args.image)))
    minimum = float(cropper.config['global_alignment']['minimum_score'])
    if board.alignment_reason!='OK' or board.alignment_score<minimum:
        raise ValueError('Uncertain registration')
    slots = [s for s in cropper.fixed_slots(board.image_bgr) if s.component_type=='VRM']
    batch = torch.stack([transform(central_rgb(board.image_bgr,s.geometry,scale))
                         for s in slots for scale in (.55,1.30)])
    with torch.inference_mode():
        features = model(batch).numpy().reshape(len(slots),-1)
    logits = features@coef.T+intercept
    probs = 1/(1+np.exp(-np.clip(logits[:,0],-50,50)))
    report = {'authority':'ADVISORY_ONLY','runtime_enabled':False,
        'input_image':str(args.image.resolve()),
        'input_sha256':hashlib.sha256(args.image.read_bytes()).hexdigest(),
        'candidate_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),
        'alignment_score':board.alignment_score,
        'note':'Uncalibrated binary candidate; does not imply correct placement or authoritative PASS/FAIL.',
        'slots':[{'slot_id':s.slot_id,'candidate':'PRESENT' if p>=.5 else 'EMPTY',
            'present_probability':float(p),'status':'UNKNOWN'} for s,p in zip(slots,probs)],
        'robot_command_sent':False,'conveyor_command_sent':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['slots']))


if __name__=='__main__':
    main()
