"""Frozen-feature seating probe; only explicit training splits are fitted."""
import json
import argparse
import hashlib
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from torchvision import models, transforms

from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper
from vrm_seating_common import crop_vrm_seating_slot


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--include-session-training',action='store_true')
    parser.add_argument('--fresh-vrm5', action='store_true', help='Add explicit Sept7 development scenes; reserve both new validation scenes')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--pool-size',type=int,choices=(1,2,3,4,7),default=2)
    parser.add_argument('--multiscale',action='store_true',help='Concatenate earlier layer5 and final spatial features')
    parser.add_argument('--rbf',action='store_true',help='Offline SVC C1 gamma=scale; score is sigmoid margin, not probability')
    args=parser.parse_args()
    if args.fresh_vrm5 and args.output is None:
        parser.error('Fresh experiment requires separate output')
    if (args.multiscale or args.rbf) and args.output is None:
        parser.error('Experimental variants require a separate --output directory')
    if args.output is not None and any((args.output/name).exists() for name in ('candidate.npz','candidate.joblib')):
        parser.error('Refusing to overwrite an existing candidate')
    torch.set_num_threads(2)
    root=ROOT/'vision_assembly/slot_classifier/datasets/vrm_seating_v3'
    records=[json.loads(line) for line in (root/'manifest.jsonl').read_text().splitlines() if line]
    if args.include_session_training:
        extra_root=ROOT/'vision_assembly/slot_classifier/datasets/vrm_pose_session_20260905'
        extra=[json.loads(line) for line in (extra_root/'manifest.jsonl').read_text().splitlines() if line]
        reserved=json.loads((ROOT/'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())
        reserved_images={s['image'] for s in reserved['scenes']}
        for row in extra:
            if row['source_image'] in reserved_images or row['split']!='train':
                raise ValueError('Validation leakage')
            records.append(dict(scene_id=row['physical_scene_id'],physical_scene_id=row['physical_scene_id'],
                split='train',slot_id=row['slot_id'],label='seating' if row['label']=='PLACEMENT_DEFECT' else 'flat',
                crop_image=str(extra_root/row['crop_image'])))
    if args.fresh_vrm5:
        fresh_cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
        sidecars=('vrm_normal_left_20260907_143009.json',
            'vrm_left_lower_lip_20260907_143324.json',
            'vrm_normal_reseat_20260907_143855.json',
            'vrm_left_upper_lip_20260907_144137.json',
            'vrm_validation_normal_20260907_144354.json',
            'vrm_validation_lip_20260907_144819.json')
        seen=set()
        for name in sidecars:
            sidecar_path=ROOT/'runtime/inspection'/name
            scene=json.loads(sidecar_path.read_text())
            assert scene['target_slot']=='vrm_05'
            assert scene['planned_split'] in ('development','validation')
            assert scene['seating_label'] in ('FLAT','SEATING')
            split='train' if scene['planned_split']=='development' else 'fresh_validation'
            if split=='train' and scene.get('training_allowed') is False:
                raise ValueError('Training forbidden')
            for source in scene['images']:
                source_path=ROOT/source
                digest=hashlib.sha256(source_path.read_bytes()).hexdigest()
                if digest in seen:
                    raise ValueError('Duplicate fresh source')
                seen.add(digest)
                board=fresh_cropper.register(cv2.imread(str(source_path)))
                if board.alignment_reason!='OK' or board.alignment_score<float(fresh_cropper.config['global_alignment']['minimum_score']):
                    raise ValueError('Uncertain fresh registration')
                slot=next(s for s in fresh_cropper.fixed_slots(board.image_bgr) if s.slot_id=='vrm_05')
                crop=crop_vrm_seating_slot(board.image_bgr,slot.geometry)
                crop_path=args.output/'fresh_crops'/f'{source_path.stem}__vrm_05.png'
                crop_path.parent.mkdir(parents=True,exist_ok=True)
                if not cv2.imwrite(str(crop_path),crop):
                    raise IOError('Crop write failed')
                records.append(dict(scene_id=source,physical_scene_id=scene['physical_scene_id'],
                    split=split,slot_id='vrm_05',label=scene['seating_label'].lower(),
                    crop_image=str(crop_path.resolve()),source_sha256=digest,
                    sidecar_sha256=hashlib.sha256(sidecar_path.read_bytes()).hexdigest()))
        (args.output/'fresh_manifest.json').write_text(json.dumps(records[-12:],indent=2))
    model=models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1).features.eval()
    transform=transforms.Compose([transforms.Resize((224,224)),transforms.ToTensor(),
        transforms.Normalize((.485,.456,.406),(.229,.224,.225))])
    def features(images):
        with torch.inference_mode():
            result=[]
            for offset in range(0,len(images),16):
                batch=torch.stack([transform(im) for im in images[offset:offset+16]])
                if args.multiscale:
                    early=model[:6](batch)
                    final=model[6:](early)
                    pooled=[torch.nn.functional.adaptive_avg_pool2d(f,(args.pool_size,args.pool_size)).flatten(1) for f in (early,final)]
                    result.append(torch.cat(pooled,dim=1).numpy())
                else:
                    result.append(torch.nn.functional.adaptive_avg_pool2d(model(batch),(args.pool_size,args.pool_size)).flatten(1).numpy())
            return np.concatenate(result)
    images=[]
    for row in records:
        with Image.open(root/row['crop_image']) as im:
            images.append(im.convert('RGB'))
    x=features(images)
    y=np.array([int(r['label']=='seating') for r in records])
    train=np.array([r['split']=='train' for r in records])
    train_groups={r['physical_scene_id'] for r in records if r['split']=='train'}
    assert all(r['physical_scene_id'] not in train_groups for r in records if r['split']!='train')
    clf=(SVC(C=1.,kernel='rbf',gamma='scale',class_weight='balanced') if args.rbf else
         LogisticRegression(C=1.,class_weight='balanced',max_iter=2000)).fit(x[train],y[train])
    def scores(values):
        if args.rbf:
            return 1/(1+np.exp(-np.clip(clf.decision_function(values),-700,700)))
        return clf.predict_proba(values)[:,1]
    report=[]
    probabilities=scores(x)
    for r,p in zip(records,probabilities):
        report.append(dict(source=r['scene_id'],slot=r['slot_id'],split=r['split'],
            expected=r['label'],seating_score=float(p),status='UNKNOWN'))
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    manifest=json.loads((ROOT/'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())
    session_images,session_rows=[],[]
    for scene in manifest['scenes']:
        if not scene.get('expected_pose'):
            continue
        board=cropper.register(cv2.imread(str(ROOT/scene['image'])))
        if board.alignment_reason!='OK' or board.alignment_score<float(cropper.config['global_alignment']['minimum_score']):
            raise ValueError('Uncertain registration')
        for slot in cropper.fixed_slots(board.image_bgr):
            expected=scene['expected_pose'].get(slot.slot_id)
            if expected is None:
                continue
            crop=crop_vrm_seating_slot(board.image_bgr,slot.geometry)
            session_images.append(Image.fromarray(cv2.cvtColor(crop,cv2.COLOR_BGR2RGB)))
            session_rows.append(dict(source=scene['image'],slot=slot.slot_id,split='session_holdout',
                                     expected='seating' if expected=='FAIL' else 'flat',status='UNKNOWN'))
    probs=scores(features(session_images))
    for r,p in zip(session_rows,probs):
        r['seating_score']=float(p)
        report.append(r)
    output=ROOT/('runtime/inspection/vrm_spatial_seating_plus_session_20260905' if args.include_session_training else 'runtime/inspection/vrm_spatial_seating_probe_20260905')
    if args.output is not None:
        output=args.output
    output.mkdir(parents=True,exist_ok=True)
    if args.rbf:
        import joblib
        joblib.dump(clf,output/'candidate.joblib')
    else:
        np.savez(output/'candidate.npz',coef=clf.coef_,intercept=clf.intercept_,classes=clf.classes_)
    (output/'evaluation.json').write_text(json.dumps(dict(authority='ADVISORY_ONLY',runtime_enabled=False,
        method=f'frozen_B0_{"layer5_final_" if args.multiscale else ""}spatial{args.pool_size}x{args.pool_size}_{"rbf_C1_gamma_scale" if args.rbf else "logistic_C1"}',include_explicit_session_training=args.include_session_training,
        score_semantics='sigmoid_uncalibrated_svc_margin' if args.rbf else 'uncalibrated_logistic_probability',
        note='Historical seating labels versus current rotation/translation defects; distinct tasks, uncalibrated scores.',
        robot_command_sent=False,conveyor_command_sent=False,rows=report),indent=2))
    for split in sorted({r['split'] for r in report}):
        rows=[r for r in report if r['split']==split]
        print(split,len(rows),'binary agreement',sum((r['seating_score']>=.5)==(r['expected']=='seating') for r in rows))
    for r in session_rows:
        print(r['source'].rsplit('_',1)[-1],r['slot'],r['expected'],round(r['seating_score'],4))


if __name__=='__main__':
    main()
