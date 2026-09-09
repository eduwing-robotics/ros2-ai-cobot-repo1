"""Validate frozen candidate against pre-existing explicit historical labels."""
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import torch
from torchvision import models,transforms
from PIL import Image
from train_vrm_context_state_probe import ROOT,views
from preprocessor_and_cropper import FixedSlotCropper
from vrm_state_common import crop_vrm_state_slot


def main():
    torch.set_num_threads(2)
    experiment=ROOT/'runtime/inspection/vrm_deadline_candidate_20260909'
    output=experiment/'frozen_context_state'
    excluded={json.loads(l)['source_sha256'] for l in (experiment/'dataset/manifest.jsonl').read_text().splitlines()}
    label_file=ROOT/'vision_assembly/config/vrm_presence_context_holdout_20260905.json'
    config=json.loads(label_file.read_text())
    stamps=('141603','142337','143632','144017','144513','150517')
    model=models.efficientnet_b0(weights=None)
    weights=Path(torch.hub.get_dir())/'checkpoints/efficientnet_b0_rwightman-7f5810bc.pth'
    model.load_state_dict(torch.load(weights,map_location='cpu',weights_only=True))
    model.classifier=torch.nn.Identity();model.eval()
    transform=transforms.Compose([transforms.Resize((224,224)),transforms.ToTensor(),transforms.Normalize((.485,.456,.406),(.229,.224,.225))])
    with np.load(output/'candidate.npz',allow_pickle=False) as params:
        coef,intercept,classes=params['coef'],params['intercept'],params['classes']
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    rows=[]
    for stamp in stamps:
        scene=next(s for s in config['scenes'] if s['image'].endswith('_'+stamp+'.png'))
        path=ROOT/scene['image'];digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in excluded: raise ValueError('Historical evaluation source leaked')
        if scene.get('image_sha256') and scene['image_sha256']!=digest: raise ValueError('Historical source changed')
        board=cropper.register(cv2.imread(str(path)))
        if board.alignment_reason!='OK' or board.alignment_score<.82: raise ValueError('Invalid registration')
        for slot in cropper.fixed_slots(board.image_bgr):
            sid=slot.slot_id
            label=scene.get('labels',{}).get(sid)
            pose=(scene.get('expected_pose') or {}).get(sid)
            reason=(scene.get('defect_reason') or {}).get(sid)
            truth=('empty' if label=='EMPTY' else 'correct' if label=='PRESENT' and pose=='PASS'
                   else 'rotated' if reason=='ROTATION_POSITION_ERROR' else None)
            if truth is None: continue
            rgb=cv2.cvtColor(crop_vrm_state_slot(board.image_bgr,slot.geometry),cv2.COLOR_BGR2RGB)
            batch=torch.stack([transform(Image.fromarray(v)) for v in views(rgb)])
            with torch.inference_mode(): f=model(batch).numpy().reshape(1,-1)
            logits=f@coef.T+intercept;prob=np.exp(logits-logits.max());prob/=prob.sum()
            index=int(prob.argmax());prediction=str(classes[index]);confidence=float(prob[0,index])
            rows.append(dict(scene=stamp,slot=sid,truth=truth,prediction=prediction,confidence=confidence,
                             state_at_090=prediction if confidence>=.9 else 'unknown',source_sha256=digest,
                             historical_hash_available=bool(scene.get('image_sha256')),label_source=scene['label_source']))
    summary={label:dict(count=sum(r['truth']==label for r in rows),
                       correct_at_090=sum(r['truth']==label and r['state_at_090']==label for r in rows),
                       wrong_at_090=sum(r['truth']==label and r['state_at_090'] not in (label,'unknown') for r in rows))
             for label in classes}
    with (output/'historical_evaluation.json').open('x') as stream:
        json.dump(dict(rows=rows,summary=summary,authority='OFFLINE_ONLY',
                       label_file_sha256=hashlib.sha256(label_file.read_bytes()).hexdigest(),
                       limitation='Historical development controls; not newly blinded independent physical units'),stream,indent=2)
    print(summary)
    for r in rows:
        if r['truth']!=r['state_at_090']: print(r['scene'],r['slot'],r['truth'],'->',r['state_at_090'],round(r['confidence'],3))


if __name__=='__main__': main()
