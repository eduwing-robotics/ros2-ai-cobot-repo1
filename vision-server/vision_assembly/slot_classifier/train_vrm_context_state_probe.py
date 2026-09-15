"""Isolated frozen RGB dual-view three-state experiment, never a runtime model."""
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import torch
from torchvision import models, transforms
from PIL import Image
from sklearn.linear_model import LogisticRegression

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'vision_assembly/hybrid_inspection'))
from preprocessor_and_cropper import FixedSlotCropper
from vrm_state_common import crop_vrm_state_slot


def views(rgb):
    if rgb.dtype!=np.uint8 or rgb.shape!=(256,256,3):
        raise ValueError('Expected RGB256 fixed-slot input')
    output=[]
    for fraction in (.37,.88):
        width=round(256*fraction)
        start=(256-width)//2
        output.append(rgb[start:start+width,start:start+width].copy())
    return output


def evaluate(clf,x,labels):
    probabilities=clf.predict_proba(x)
    pred=clf.classes_[probabilities.argmax(1)]
    confidence=probabilities.max(1)
    labels=np.array(labels)
    return dict(count=len(labels),raw_accuracy=float((pred==labels).mean()),
                correct_at_090=int(((pred==labels)&(confidence>=.90)).sum()),
                wrong_at_090=int(((pred!=labels)&(confidence>=.90)).sum()),
                abstained=int((confidence<.90).sum()),
                per_class={k:dict(count=int((labels==k).sum()),raw_correct=int(((labels==k)&(pred==labels)).sum())) for k in clf.classes_},
                predictions=[dict(truth=t,predicted=p,confidence=float(c),probabilities=dict(zip(clf.classes_,map(float,pr)))) for t,p,c,pr in zip(labels,pred,confidence,probabilities)])


def main():
    torch.set_num_threads(2)
    experiment=ROOT/'runtime/inspection/vrm_deadline_candidate_20260909'
    output=experiment/'frozen_context_state'
    output.mkdir(exist_ok=False)
    manifest=experiment/'dataset/manifest.jsonl'
    rows=[json.loads(line) for line in manifest.read_text().splitlines()]
    split=json.loads((experiment/'model/vrm_state.json').read_text())
    train=np.array([r['scene_id'] in split['train_scenes'] for r in rows])
    valid=np.array([r['scene_id'] in split['validation_scenes'] for r in rows])
    if np.any(train&valid) or not np.all(train|valid): raise ValueError('Invalid scene split')
    train_hashes={r['source_sha256'] for r,m in zip(rows,train) if m}
    valid_hashes={r['source_sha256'] for r,m in zip(rows,valid) if m}
    if train_hashes&valid_hashes: raise ValueError('Source leakage')
    weights=Path(torch.hub.get_dir())/'checkpoints/efficientnet_b0_rwightman-7f5810bc.pth'
    model=models.efficientnet_b0(weights=None)
    model.load_state_dict(torch.load(weights,map_location='cpu',weights_only=True))
    model.classifier=torch.nn.Identity()
    model.eval()
    transform=transforms.Compose([transforms.Resize((224,224)),transforms.ToTensor(),transforms.Normalize((.485,.456,.406),(.229,.224,.225))])
    def extract(images):
        vectors=[]
        with torch.inference_mode():
            for start in range(0,len(images),8):
                batch=torch.stack([transform(Image.fromarray(v)) for im in images[start:start+8] for v in views(im)])
                vectors.append(model(batch).numpy().reshape(-1,2560))
        return np.concatenate(vectors)
    images=[]
    for row in rows:
        bgr=cv2.imread(row['crop_image'])
        if bgr is None: raise ValueError('Missing training crop')
        images.append(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))
    features=extract(images)
    labels=[r['label'] for r in rows]
    clf=LogisticRegression(C=1.,class_weight='balanced',max_iter=3000,random_state=42)
    clf.fit(features[train],np.array(labels)[train])
    np.savez(output/'candidate.npz',coef=clf.coef_,intercept=clf.intercept_,classes=clf.classes_)
    validation=evaluate(clf,features[valid],np.array(labels)[valid])
    base=ROOT/'runtime/inspection/hbm_release_regression_20260909'
    runs=[base/'fresh_all_normal/20260909_154032_384501',base/'fresh_all_normal_repeat/20260909_154330_779617']
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    test_images=[];test_sources=[]
    for run in runs:
        report=json.loads((run/'hybrid_report.json').read_text())
        if report['input_sha256'] in train_hashes|valid_hashes: raise ValueError('Fresh test leaked')
        bgr=cv2.imread(str(run/'aligned_board.png'))
        for slot in cropper.fixed_slots(bgr):
            if slot.component_type=='VRM':
                test_images.append(cv2.cvtColor(crop_vrm_state_slot(bgr,slot.geometry),cv2.COLOR_BGR2RGB))
                test_sources.append(dict(report=str(run/'hybrid_report.json'),slot=slot.slot_id,sha256=report['input_sha256']))
    fresh=evaluate(clf,extract(test_images),['correct']*len(test_images))
    result=dict(authority='OFFLINE_ONLY',validated=False,threshold=.90,
                method='frozen EfficientNetB0 central37/context88 RGB logistic C1',
                manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                backbone_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(),
                validation=validation,fresh_normal=fresh,fresh_sources=test_sources,
                limitations='Previously consulted developmental scenes and same-position repeats; no independent physical-part acceptance')
    (output/'evaluation.json').write_text(json.dumps(result,indent=2))
    for name,metrics in [('validation',validation),('fresh_normal',fresh)]:
        print(name,{k:v for k,v in metrics.items() if k!='predictions'})


if __name__=='__main__': main()
