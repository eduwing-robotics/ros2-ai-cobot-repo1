"""Train an isolated frozen-feature SMD01 seating appearance candidate.

Dates before Sept7 fit the head, Sept7 is developmental validation, Sept8-10 is
later replay. All are reused physical hardware/data, not independent deployment
qualification. No source labels derived from anomaly scores, no per-part align,
CLAHE, geometry augmentation, live capture, or runtime model replacement.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'vision_assembly/hybrid_inspection'))
from smd01_seating_candidate import (LABELS, CROP_PIPELINE, CROP_XYWH,
                                    assign_split, unique_cases, fixed_crop, sha256, registration_hashes)


def collect_cases():
    base = ROOT/'runtime/inspection'
    registry = base/'smd01_small_lip_integration_20260907.json'
    observations = [(Path(r['report']), {'defect':'LIP_SEATING','normal':'NORMAL_SEATED'}[r['truth']],
                     str(registry), False)
                    for r in json.loads(registry.read_text())['rows']]
    for folder, label in [
        ('smd01_lip_validation_20260908_132035/20260908_132108_768224','LIP_SEATING'),
        ('smd01_recovery_20260908_132402/20260908_132425_543863','NORMAL_SEATED'),
        ('smd01_fresh_validation_20260908_131643/20260908_131741_747610','NORMAL_SEATED')]:
        observations.append((base/folder/'hybrid_report.json',label,
                             'docs/logs/vision.md: Sept8 SMD01 normal/lip/recovery records',
                             '131643' in folder))
    event = base/'api/d24beed9-4df3-422c-8707-2f67f6918df8/event.json'
    observations.extend((Path(a['report']),'NORMAL_SEATED',
        'vision_assembly/hybrid_inspection/audit_smd01_surface_corroboration.py',False)
        for a in json.loads(event.read_text())['attempts'])
    for folder in ('normal_replay','fresh_normal'):
        observations.append((next((base/'model_completion_20260910'/folder).glob('*/hybrid_report.json')),
                             'NORMAL_SEATED','docs/logs/vision.md: verified normal source replay',False))
    correction_path=base/'model_completion_20260910/smd01_displaced_truth.json'
    correction=json.loads(correction_path.read_text())
    if correction['label']!='MICRO_LIP_SEATING' or correction.get('position_defect_confirmed') is not False:
        raise ValueError('Require explicit user seating correction; not a position-defect control')
    corrected_report=next((base/'model_completion_20260910/smd01_displaced').glob('*/hybrid_report.json'))
    if json.loads(corrected_report.read_text())['input_image'] != correction['source']:
        raise ValueError('Correction source mismatch')
    observations.append((corrected_report,'LIP_SEATING',str(correction_path),False))
    rows=[]
    for path,label,provenance,inherited in observations:
        report=json.loads(path.read_text()); source=Path(report['input_image'])
        digest=sha256(source)
        if digest != report['input_sha256']:
            raise ValueError(f'Source hash mismatch: {source}')
        rows.append(dict(source=str(source),source_sha256=digest,source_report=str(path),
                         source_report_sha256=sha256(path),label=label,label_provenance=provenance,
                         inherited_unchanged_state=inherited,split=assign_split(source),
                         independent_validation=False,slot_id='smd_capacitor_01'))
    return unique_cases(rows)


def metric(rows, probabilities):
    import numpy as np
    targets=np.asarray([LABELS.index(r['label']) for r in rows]); probabilities=np.asarray(probabilities,dtype=float)
    if probabilities.shape != targets.shape or not np.isfinite(probabilities).all() or ((probabilities<0)|(probabilities>1)).any():
        raise ValueError('Invalid seating probabilities or row count')
    predictions=(probabilities>=.5).astype(int)
    return dict(count=len(rows),raw_correct=int((predictions==targets).sum()),
        false_normal=int(((targets==1)&(predictions==0)).sum()),
        false_seating=int(((targets==0)&(predictions==1)).sum()),
        at_fixed_090_gate=dict(correct=int((((probabilities>=.9)&(targets==1))|
            ((probabilities<=.1)&(targets==0))).sum()),
            incorrect=int((((probabilities>=.9)&(targets==0))|
            ((probabilities<=.1)&(targets==1))).sum()),
            abstain=int(((probabilities>.1)&(probabilities<.9)).sum())))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--checkpoint',type=Path,default=Path.home()/'.cache/torch/hub/checkpoints/efficientnet_b0_rwightman-7f5810bc.pth')
    args=parser.parse_args()
    import cv2
    import numpy as np
    import torch
    from torchvision.models import efficientnet_b0
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from preprocessor_and_cropper import FixedSlotCropper

    torch.set_num_threads(2);cv2.setNumThreads(2);torch.manual_seed(47)
    args.output.mkdir(parents=True,exist_ok=False)
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    rows=collect_cases(); tensors=[]
    for i,row in enumerate(rows):
        registered=cropper.register(cv2.imread(row['source']))
        if registered.alignment_reason!='OK' or registered.alignment_score<.82:
            raise ValueError(f'Registration invalid: {row["source"]}')
        crop=fixed_crop(registered.image_bgr)
        path=args.output/f'{i:03d}_{row["split"]}_{row["label"]}.png'
        cv2.imwrite(str(path),crop)
        row.update(crop=str(path),crop_sha256=sha256(path),registration_score=registered.alignment_score,
                   crop_pipeline=CROP_PIPELINE)
        rgb=cv2.cvtColor(cv2.resize(crop,(224,224),interpolation=cv2.INTER_AREA),cv2.COLOR_BGR2RGB)
        tensor=torch.from_numpy(rgb.copy()).permute(2,0,1).float()/255
        tensors.append((tensor-torch.tensor([.485,.456,.406])[:,None,None])/
                        torch.tensor([.229,.224,.225])[:,None,None])
    backbone=efficientnet_b0(weights=None)
    backbone.load_state_dict(torch.load(args.checkpoint,map_location='cpu',weights_only=True))
    backbone.classifier=torch.nn.Identity();backbone.eval()
    with torch.inference_mode():
        features=torch.cat([backbone(torch.stack(tensors[i:i+8])) for i in range(0,len(tensors),8)]).numpy()
    train=np.asarray([r['split']=='train' for r in rows]); labels=np.asarray([LABELS.index(r['label']) for r in rows])
    if set(labels[train])!={0,1}: raise ValueError('Both physical states required in training')
    scaler=StandardScaler().fit(features[train])
    # Fixed before viewing later replay results; no held-out tuning/refitting.
    head=LogisticRegression(C=.1,class_weight='balanced',max_iter=2000,random_state=47)
    head.fit(scaler.transform(features[train]),labels[train])
    probabilities=head.predict_proba(scaler.transform(features))[:,1]
    np.savez(args.output/'candidate_head.npz',mean=scaler.mean_,scale=scaler.scale_,
             coef=head.coef_,intercept=head.intercept_,classes=head.classes_)
    np.savez(args.output/'features.npz',features=features,labels=labels)
    for row,prob in zip(rows,probabilities):
        row.update(seating_probability=float(prob),raw_prediction=LABELS[int(prob>=.5)],
                   qualified_prediction='LIP_SEATING' if prob>=.9 else 'NORMAL_SEATED' if prob<=.1 else 'UNKNOWN')
    summary={s:metric([r for r in rows if r['split']==s],
                     [r['seating_probability'] for r in rows if r['split']==s])
             for s in ('train','validation','later_replay')}
    result=dict(schema_version=1,task='SMD01_SEATING_APPEARANCE_CANDIDATE',authority='ADVISORY_ONLY',
        production_status='UNKNOWN',runtime_enabled=False,validated=False,crop_pipeline=CROP_PIPELINE,
        registration_hashes=registration_hashes(ROOT),crop_xywh=CROP_XYWH,backbone=str(args.checkpoint),backbone_sha256=sha256(args.checkpoint),
        head_sha256=sha256(args.output/'candidate_head.npz'),class_order=LABELS,regularization_C=.1,
        probability_gate=.9,summary=summary,rows=rows,
        limitations=['Reused same hardware/development images; later dates are not independent production qualification.',
            'Labels specify appearance associated with seating; no measured height or general position labels.',
            'No defect-only threshold changes, no test-set refit, no learned authority promotion.',
            'Current fusion contract still defers SMD01 micro seating.'])
    (args.output/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__': main()
