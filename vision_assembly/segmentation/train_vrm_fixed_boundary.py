"""Isolated GPU boundary candidate; never changes active model links."""
import hashlib
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
import torch
from ultralytics import YOLO

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',type=Path,default=ROOT/'vision_assembly/segmentation/vrm_fixed_boundary_dataset_v2')
    parser.add_argument('--name',default='vrm_fixed_boundary_v1')
    parser.add_argument('--model',type=Path,default=ROOT/'yolo26n-seg.pt')
    parser.add_argument('--epochs',type=int,default=80)
    parser.add_argument('--patience',type=int,default=20)
    parser.add_argument('--imgsz',type=int,choices=(320,640),default=320)
    args=parser.parse_args()
    if Path(args.name).name!=args.name:
        raise ValueError('Run name must not contain paths')
    if not torch.cuda.is_available():
        raise RuntimeError('GPU required; no CPU fallback')
    torch.set_num_threads(2)
    data=args.data.resolve()
    manifest=json.loads((data/'manifest.json').read_text())
    run=ROOT/'vision_assembly/segmentation/runs'/args.name
    if run.exists():
        raise ValueError('Refusing to overwrite candidate run')
    pretrained=args.model.resolve()
    if not pretrained.is_file():
        raise FileNotFoundError('Local generic pretrained weights required')
    active=ROOT/'vision_assembly/segmentation/models/s22_parts_seg_candidate.pt'
    active_hash=hashlib.sha256(active.read_bytes()).hexdigest()
    provenance=dict(authority='ADVISORY_ONLY',runtime_enabled=False,
        status='TRAINING',dataset_manifest_sha256=hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest(),
        pretrained_sha256=hashlib.sha256(pretrained.read_bytes()).hexdigest(),
        active_model_sha256_before=active_hash,gpu=torch.cuda.get_device_name(0),
        robot_command_sent=False,conveyor_command_sent=False,
        limitations=manifest.get('limitation'),epochs_requested=args.epochs,patience=args.patience,
        imgsz=args.imgsz)
    # Let Ultralytics create its run directory; provenance saved separately first.
    provenance_path=run.parent/f'{args.name}_provenance.json'
    if provenance_path.exists():
        raise ValueError('Existing experiment provenance; inspect before retrying')
    provenance_path.write_text(json.dumps(provenance,indent=2))
    model=YOLO(str(pretrained))
    model.train(data=str(data/'vrm.yaml'),epochs=args.epochs,patience=args.patience,imgsz=args.imgsz,batch=8,
        device=0,workers=2,project=str(run.parent),name=run.name,exist_ok=False,
        seed=20260905,deterministic=True,cache=False,plots=True,
        mosaic=0.,mixup=0.,copy_paste=0.,close_mosaic=0,
        degrees=10.,translate=.05,scale=.1,perspective=0.,
        fliplr=0.,flipud=0.,hsv_h=0.,hsv_s=.1,hsv_v=.1,
        mask_ratio=1)
    best=run/'weights/best.pt'
    candidate=YOLO(str(best))
    metrics=candidate.val(data=str(data/'vrm.yaml'),split='test',imgsz=args.imgsz,batch=8,
        device=0,workers=2,project=str(run),name='heldout_test',plots=True)
    preview=run/'heldout_preview'
    preview.mkdir()
    panels=[]
    for row in manifest['rows']:
        if row['split']!='test':
            continue
        path=data/'images/test'/(row['stem']+'.png')
        image=cv2.imread(str(path))
        result=candidate.predict(image,imgsz=args.imgsz,device=0,conf=.25,retina_masks=True,verbose=False)[0]
        overlay=result.plot(boxes=False,labels=False,probs=False,line_width=1)
        cv2.imwrite(str(preview/(row['stem']+'.jpg')),overlay)
        panels.append(np.hstack([cv2.resize(image,(140,180)),cv2.resize(overlay,(140,180))]))
    cv2.imwrite(str(preview/'comparison.jpg'),np.vstack([np.hstack(panels[i:i+5]) for i in range(0,len(panels),5)]))
    final_hash=hashlib.sha256(active.read_bytes()).hexdigest()
    if final_hash!=active_hash:
        raise RuntimeError('Active model changed externally during experiment')
    provenance.update(status='TRAINED_NOT_DEPLOYED',best=str(best),
        best_sha256=hashlib.sha256(best.read_bytes()).hexdigest(),
        heldout_test_metrics={k:float(v) for k,v in metrics.results_dict.items()},
        active_model_unchanged=True)
    provenance_path.write_text(json.dumps(provenance,indent=2))
    print(json.dumps(provenance,indent=2))


if __name__=='__main__':
    main()
