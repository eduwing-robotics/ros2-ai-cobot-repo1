"""Read-only saved-image predictor for the isolated SMD01 seating experiment.

Always UNKNOWN/ADVISORY_ONLY. Not imported by the live inspection pipeline.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'vision_assembly/hybrid_inspection'))
from smd01_seating_candidate import CROP_PIPELINE, CROP_XYWH, LABELS, fixed_crop, sha256, registration_hashes


def infer(image_path, model_dir):
    import cv2
    import numpy as np
    import torch
    from torchvision.models import efficientnet_b0
    from preprocessor_and_cropper import FixedSlotCropper
    metadata=json.loads((model_dir/'evaluation.json').read_text())
    if (metadata['crop_pipeline']!=CROP_PIPELINE or tuple(metadata['crop_xywh'])!=CROP_XYWH
            or tuple(metadata['class_order'])!=LABELS or metadata['authority']!='ADVISORY_ONLY'):
        raise ValueError('Candidate contract mismatch')
    if metadata.get('registration_hashes') != registration_hashes(ROOT):
        raise ValueError('Registration reference/configuration changed; candidate requires re-evaluation')
    backbone_path=Path(metadata['backbone']);head_path=model_dir/'candidate_head.npz'
    if sha256(backbone_path)!=metadata['backbone_sha256'] or sha256(head_path)!=metadata['head_sha256']:
        raise ValueError('Candidate weight hash mismatch')
    torch.set_num_threads(2);cv2.setNumThreads(2)
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    registered=cropper.register(cv2.imread(str(image_path)))
    result=dict(source=str(image_path),source_sha256=sha256(image_path),slot_id='smd_capacitor_01',
                status='UNKNOWN',authority='ADVISORY_ONLY',confirmed_defect=False,
                model_path=str(model_dir),head_sha256=metadata['head_sha256'],
                runtime_enabled=False,alignment_score=registered.alignment_score)
    if registered.alignment_reason!='OK' or registered.alignment_score<.82:
        return dict(result,reason='REGISTRATION_INVALID',qualified_prediction='UNKNOWN')
    crop=fixed_crop(registered.image_bgr)
    rgb=cv2.cvtColor(cv2.resize(crop,(224,224),interpolation=cv2.INTER_AREA),cv2.COLOR_BGR2RGB)
    tensor=torch.from_numpy(rgb.copy()).permute(2,0,1).float()/255
    tensor=(tensor-torch.tensor([.485,.456,.406])[:,None,None])/torch.tensor([.229,.224,.225])[:,None,None]
    backbone=efficientnet_b0(weights=None)
    backbone.load_state_dict(torch.load(backbone_path,map_location='cpu',weights_only=True))
    backbone.classifier=torch.nn.Identity();backbone.eval()
    with torch.inference_mode():features=backbone(tensor[None]).numpy()
    with np.load(head_path,allow_pickle=False) as head:
        mean,scale,coef,intercept,classes=(head[k] for k in ('mean','scale','coef','intercept','classes'))
        if (mean.shape!=(1280,) or scale.shape!=(1280,) or coef.shape!=(1,1280)
                or intercept.shape!=(1,) or not np.array_equal(classes,[0,1])
                or not all(np.isfinite(a).all() for a in (features,mean,scale,coef,intercept))
                or (scale<=0).any()):
            raise ValueError('Invalid candidate head tensors')
        logit=float((((features-mean)/scale)@coef.T+intercept).item())
    probability=float(1/(1+np.exp(-np.clip(logit,-700,700))))
    prediction='LIP_SEATING' if probability>=.9 else 'NORMAL_SEATED' if probability<=.1 else 'UNKNOWN'
    return dict(result,seating_probability=probability,qualified_prediction=prediction,
                reason='EXPERIMENTAL_APPEARANCE_ONLY_NOT_HEIGHT_OR_POSITION_METROLOGY')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=Path,required=True)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=infer(args.image,args.model)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as handle:json.dump(result,handle,indent=2)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
