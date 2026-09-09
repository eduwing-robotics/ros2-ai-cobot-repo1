"""Offline fixed RGB contact-window classifier; explicit train splits only."""
import hashlib
import argparse
import json
import cv2
import numpy as np
import torch
from PIL import Image
from sklearn.linear_model import LogisticRegression
from torchvision import models
from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper
from vrm_seating_common import crop_vrm_seating_slot


def windows(rgb):
    if rgb.shape != (256,256,3):
        raise ValueError('Expected shared 256x256 RGB crop')
    # Fixed windows retain their order and slot-relative location.
    centers=[(48,48),(128,48),(208,48),(208,128),(208,208),(128,208),(48,208),(48,128)]
    return np.stack([rgb[y-48:y+48,x-48:x+48] for x,y in centers])


class ContactTail(torch.nn.Module):
    def __init__(self, tail):
        super().__init__()
        self.tail=tail
        self.head=torch.nn.Linear(8*1280,2)

    def forward(self, x):
        n=x.shape[0]
        x=self.tail(x.flatten(0,1)).mean((2,3)).reshape(n,8*1280)
        return self.head(x)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--include-fresh',action='store_true')
    parser.add_argument('--contact-plan',help='Reviewed development / locked validation capture plan')
    parser.add_argument('--finetune-tail',action='store_true',help='Fixed20 epochs on training only; cached frozen early RGB features')
    parser.add_argument('--output',default='runtime/inspection/vrm_contact_candidate_20260907')
    args=parser.parse_args()
    torch.set_num_threads(2)
    torch.manual_seed(20260907)
    output=ROOT/args.output
    if output.exists():
        raise FileExistsError(output)
    root=ROOT/'vision_assembly/slot_classifier/datasets/vrm_seating_v3'
    records=[json.loads(l) for l in (root/'manifest.jsonl').read_text().splitlines() if l]
    images=[]
    for r in records:
        path=root/r['crop_image']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==r['crop_sha256']
        images.append(np.array(Image.open(path).convert('RGB')))
    if args.include_fresh:
        fresh=json.loads((ROOT/'runtime/inspection/vrm_seating_fresh_vrm5_20260907/fresh_manifest.json').read_text())
        sidecars={}
        for path in (ROOT/'runtime/inspection').glob('vrm*20260907_*.json'):
            sidecars[hashlib.sha256(path.read_bytes()).hexdigest()]=path
        for r in fresh:
            sidecar=json.loads(sidecars[r['sidecar_sha256']].read_text())
            assert sidecar['target_slot']=='vrm_05'
            assert r['scene_id'] in sidecar['images']
            assert r['label']==sidecar['seating_label'].lower()
            assert r['physical_scene_id']==sidecar['physical_scene_id']
            if r['split']=='train':
                assert sidecar['planned_split']=='development' and sidecar.get('training_allowed') is not False
            else:
                assert r['split']=='fresh_validation' and sidecar['planned_split']=='validation'
            assert hashlib.sha256((ROOT/r['scene_id']).read_bytes()).hexdigest()==r['source_sha256']
            path=ROOT/r['crop_image']
            records.append(dict(r,crop_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            images.append(np.array(Image.open(path).convert('RGB')))
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    if args.contact_plan:
        plan_path=ROOT/args.contact_plan
        plan=json.loads(plan_path.read_text())
        requested=[(p,'train') for p in plan['development_reviewed']]+[(p,'contact_validation') for p in plan['next_collection']['captured']]
        seen=set()
        for name,split in requested:
            metadata_path=plan_path.parent/name
            r=json.loads(metadata_path.read_text())
            assert r['target_slot']=='vrm_05'
            assert r['seating_label'] in ('FLAT','SEATING')
            if split=='train':
                assert r['planned_split']=='development_reviewed' and r['training_allowed'] is True
            else:
                assert r['planned_split']=='validation' and r['training_allowed'] is False
            path=ROOT/r['image']
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest==r['image_sha256'] and digest not in seen
            seen.add(digest)
            board=cropper.register(cv2.imread(str(path)))
            assert board.alignment_reason=='OK' and board.alignment_score>=float(cropper.config['global_alignment']['minimum_score'])
            slot=next(s for s in cropper.fixed_slots(board.image_bgr) if s.slot_id=='vrm_05')
            images.append(cv2.cvtColor(crop_vrm_seating_slot(board.image_bgr,slot.geometry),cv2.COLOR_BGR2RGB))
            records.append(dict(scene_id=r['physical_scene_id'],physical_scene_id=r['physical_scene_id'],
                split=split,slot_id='vrm_05',label=r['seating_label'].lower(),source_image=str(path),
                source_sha256=digest,review_sha256=hashlib.sha256(metadata_path.read_bytes()).hexdigest()))
    groups={r['physical_scene_id'] for r in records if r['split']=='train'}
    assert not groups.intersection(r['physical_scene_id'] for r in records if r['split']!='train')
    # Reserved failure/fresh scenes must never appear in the training records.
    forbidden=('194959','184100','183823','184132')
    assert not any(any(t in json.dumps(r) for t in forbidden) for r in records if r['split']=='train')
    selected=json.loads((ROOT/'runtime/inspection/vrm_seating_pairs/normal_envelope_audit.json').read_text())['rows']
    saved=json.loads((ROOT/'vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1/saved_scene_validation_last/report.json').read_text())
    lookup={r['scene']:r for r in saved['rows'] if r['slot']=='vrm_05'}
    for r in selected:
        if r['source']=='historical':
            source=lookup[r['scene']]; path=ROOT/source['source_image']; digest=source['image_sha256']
        else:
            source=json.loads((ROOT/'runtime/inspection/vrm_seating_pairs'/r['scene']/'scene.json').read_text())
            path=ROOT/source['image']; digest=source['image_sha256']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
        board=cropper.register(cv2.imread(str(path)))
        assert board.alignment_reason=='OK' and board.alignment_score>=float(cropper.config['global_alignment']['minimum_score'])
        slot=next(s for s in cropper.fixed_slots(board.image_bgr) if s.slot_id=='vrm_05')
        images.append(cv2.cvtColor(crop_vrm_seating_slot(board.image_bgr,slot.geometry),cv2.COLOR_BGR2RGB))
        records.append(dict(scene_id=r['scene'],physical_scene_id=r['scene'],slot_id='vrm_05',
            label='flat' if r['label'] in ('PASS','FLAT') else 'seating',split='retrospective_pose_control',
            label_basis=r['label_basis'],source_sha256=digest))
    model=models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1).features.eval()
    mean=torch.tensor([.485,.456,.406]).view(1,3,1,1)
    std=torch.tensor([.229,.224,.225]).view(1,3,1,1)
    features=[]
    with torch.inference_mode():
        for index,rgb in enumerate(images):
            batch=torch.from_numpy(windows(rgb).copy()).permute(0,3,1,2).float()/255
            normalized=(batch-mean)/std
            feature=(model[:6](normalized).numpy() if args.finetune_tail else
                     model(normalized).mean((2,3)).flatten().numpy())
            features.append(feature)
            if index%20==0:
                print('features',index+1,'/',len(images),flush=True)
    x=np.stack(features); y=np.array([r['label']=='seating' for r in records],dtype=int)
    train=np.array([r['split']=='train' for r in records])
    if args.finetune_tail:
        tail=ContactTail(model[6:])
        optimizer=torch.optim.AdamW(tail.parameters(),lr=1e-4,weight_decay=1e-4)
        counts=np.bincount(y[train],minlength=2)
        loss_fn=torch.nn.CrossEntropyLoss(weight=torch.tensor(len(y[train])/(2*counts),dtype=torch.float32))
        train_indices=np.flatnonzero(train)
        rng=np.random.default_rng(20260907)
        for epoch in range(20):
            # Keep pretrained BN statistics fixed; gradients still update convolution weights.
            tail.eval()
            order=rng.permutation(train_indices)
            losses=[]
            for start in range(0,len(order),8):
                idx=order[start:start+8]
                optimizer.zero_grad()
                loss=loss_fn(tail(torch.from_numpy(x[idx])),torch.from_numpy(y[idx]))
                loss.backward(); optimizer.step()
                losses.append(float(loss.detach()))
            print('fixed epoch',epoch+1,'train loss',float(np.mean(losses)),flush=True)
        tail.eval()
        with torch.inference_mode():
            probabilities=np.concatenate([torch.softmax(tail(torch.from_numpy(x[i:i+8])),1)[:,1].numpy()
                                          for i in range(0,len(x),8)])
    else:
        clf=LogisticRegression(C=1.,class_weight='balanced',max_iter=2000).fit(x[train],y[train])
        probabilities=clf.predict_proba(x)[:,1]
    rows=[dict(scene=r['scene_id'],slot=r['slot_id'],split=r['split'],label=r['label'],
               seating_score=float(p),status='UNKNOWN') for r,p in zip(records,probabilities)]
    output.mkdir()
    if args.finetune_tail:
        torch.save(tail.state_dict(),output/'candidate_tail_state.pt')
    else:
        np.savez(output/'candidate.npz',coef=clf.coef_,intercept=clf.intercept_,classes=clf.classes_)
    report=dict(rows=rows,train_count=int(train.sum()),method=('B0_eight_fixed96_RGB_finetune_tail_fixed20_epochs' if args.finetune_tail else 'frozen_B0_eight_fixed96_RGB_windows_logistic_C1'),
        training_config=dict(seed=20260907,epochs=20,lr=1e-4,weight_decay=1e-4,batch_size=8,checkpoint_selection='fixed_final_epoch') if args.finetune_tail else None,
        input_contract='shared256 crop, original RGB; no CLAHE, no part recenter/rotation',
        runtime_enabled=False,authority='ADVISORY_ONLY',validated=False,
        limitation='Uncalibrated probability; reused controls, not blind test. Some pose controls are rotation not seating.',
        robot_command_sent=False,conveyor_command_sent=False)
    (output/'evaluation.json').write_text(json.dumps(report,indent=2))
    (output/'manifest.json').write_text(json.dumps(records,indent=2))
    for split in sorted({r['split'] for r in rows}):
        subset=[r for r in rows if r['split']==split]
        print(split,len(subset),'diagnostic agreement',sum((r['seating_score']>=.5)==(r['label']=='seating') for r in subset))
    for r in rows:
        if any(t in r['scene'] for t in forbidden):
            print(r['scene'],r['slot'],r['label'],r['seating_score'])


if __name__=='__main__':
    main()
