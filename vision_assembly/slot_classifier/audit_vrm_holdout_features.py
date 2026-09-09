"""Frozen-feature explanation of a missed holdout, not defect localization."""
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision import models, transforms

ROOT=Path(__file__).resolve().parents[2]


def main():
    torch.set_num_threads(2)
    records=[]
    for name in ('vrm_seating_v3','vrm_pose_session_20260905'):
        root=ROOT/'vision_assembly/slot_classifier/datasets'/name
        for line in (root/'manifest.jsonl').read_text().splitlines():
            r=json.loads(line)
            if r['split']!='train' and not (r.get('scene_id')=='vrm05_lip_194959' and r['slot_id']=='vrm_05'):
                continue
            path=root/r['crop_image']
            assert hashlib.sha256(path.read_bytes()).hexdigest()==r['crop_sha256']
            records.append(dict(path=str(path),split=r['split'],slot=r['slot_id'],
                label='seating' if r['label'] in ('seating','PLACEMENT_DEFECT') else 'flat'))
    model=models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1).features.eval()
    transform=transforms.Compose([transforms.Resize((224,224)),transforms.ToTensor(),
        transforms.Normalize((.485,.456,.406),(.229,.224,.225))])
    chunks=[]
    for start in range(0,len(records),16):
        tensors=[]
        for r in records[start:start+16]:
            with Image.open(r['path']) as im:
                tensors.append(transform(im.convert('RGB')))
        with torch.inference_mode():
            early=model[:6](torch.stack(tensors))
            final=model[6:](early)
            chunks.append(torch.cat([torch.nn.functional.adaptive_avg_pool2d(f,(4,4)).flatten(1)
                                     for f in (early,final)],dim=1).numpy())
    x=np.concatenate(chunks)
    target=next(i for i,r in enumerate(records) if r['split']=='holdout')
    candidate=ROOT/'runtime/inspection/vrm_multiscale_seating_plus_165057/candidate.npz'
    with np.load(candidate,allow_pickle=False) as head:
        contribution=x[target]*head['coef'][0]
        spatial=contribution.reshape(-1,4,4).sum(axis=0)
        intercept=float(head['intercept'][0])
        logit=float(x[target]@head['coef'][0]+intercept)
    assert np.isclose(spatial.sum()+intercept,logit)
    normalized=x/np.maximum(np.linalg.norm(x,axis=1,keepdims=True),1e-12)
    similarities=normalized@normalized[target]
    neighbors={}
    for label in ('flat','seating'):
        order=sorted((i for i,r in enumerate(records) if r['split']=='train' and r['label']==label),
                     key=lambda i:float(similarities[i]),reverse=True)[:5]
        neighbors[label]=[{**records[i],'cosine':float(similarities[i])} for i in order]
    out=ROOT/'runtime/inspection/vrm05_holdout_feature_audit'
    out.mkdir(exist_ok=False)
    report=dict(target=records[target],training_count=sum(r['split']=='train' for r in records),
                candidate_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
                logit=logit,score=float(1/(1+np.exp(-logit))),intercept=intercept,
                spatial_logit_contributions=spatial.tolist(),neighbors=neighbors,
                note='Feature-cell contributions have large overlapping receptive fields: '
                     'not pixel defect localization. Cosine similarity is diagnostic, not a classifier.',
                training_performed=False,runtime_enabled=False,authority='ADVISORY_ONLY',
                robot_command_sent=False,conveyor_command_sent=False)
    (out/'audit.json').write_text(json.dumps(report,indent=2))
    panels=[]
    for label,path in [('MISSED HOLDOUT',records[target]['path']),
                       ('NEAREST TRAIN NORMAL',neighbors['flat'][0]['path']),
                       ('NEAREST TRAIN DEFECT',neighbors['seating'][0]['path'])]:
        crop=cv2.imread(path)
        assert crop is not None
        panel=cv2.copyMakeBorder(crop,32,0,0,0,cv2.BORDER_CONSTANT)
        cv2.putText(panel,label,(5,20),cv2.FONT_HERSHEY_SIMPLEX,.43,(255,255,255),1)
        panels.append(panel)
    cv2.imwrite(str(out/'neighbors.png'),np.hstack(panels))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
