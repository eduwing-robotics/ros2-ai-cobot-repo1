"""Training-example fit check only, not independent validation."""
import json
import argparse
import cv2
import numpy as np
from ultralytics import YOLO
from build_vrm_fixed_crop_dataset import ROOT
from common import load_yolo_segments


def main():
    base=ROOT/'vision_assembly/segmentation/runs'
    parser=argparse.ArgumentParser()
    parser.add_argument('--candidate',default='vrm_fixed_boundary_adapted_v1')
    parser.add_argument('--checkpoint',choices=['best','last'],default='best')
    args=parser.parse_args()
    if '/' in args.candidate or args.candidate in {'.','..'}:
        raise ValueError('Candidate must be a run name')
    run=base/args.candidate
    output=run/('adaptation_fit_only' if args.checkpoint=='best' else 'adaptation_fit_only_last')
    if output.exists():
        raise ValueError('Refusing overwrite')
    source=ROOT/'vision_assembly/segmentation/vrm_boundary_adaptation_v1'
    models=[YOLO(str(base/'vrm_fixed_boundary_v1/weights/best.pt')),
            YOLO(str(run/f'weights/{args.checkpoint}.pt'))]
    rows,panels=[],[]
    for row in json.loads((source/'partition.json').read_text())['rows']:
        stem=row['stem']
        image=cv2.imread(str(source/'images'/f'{stem}.png'))
        h,w=image.shape[:2]
        poly=load_yolo_segments(source/'reviewed_labels'/f'{stem}.txt',w,h)[0][1]
        truth=np.zeros((h,w),np.uint8)
        cv2.fillPoly(truth,[np.int32(poly)],1)
        views=[cv2.resize(image,(240,300))]
        scores=[]
        for model in models:
            result=model.predict(image,imgsz=320,device=0,conf=.25,retina_masks=True,verbose=False)[0]
            best=0.
            overlay=image.copy()
            cv2.polylines(overlay,[np.int32(poly)],True,(0,255,0),1)
            if result.masks is not None:
                for p in result.masks.xy:
                    mask=np.zeros_like(truth)
                    cv2.fillPoly(mask,[np.int32(p)],1)
                    iou=float(np.logical_and(mask,truth).sum()/max(np.logical_or(mask,truth).sum(),1))
                    best=max(best,iou)
                    cv2.polylines(overlay,[np.int32(p)],True,(0,170,255),1)
            scores.append(best)
            views.append(cv2.resize(overlay,(240,300)))
        panel=np.hstack(views)
        panel=cv2.copyMakeBorder(panel,30,0,0,0,cv2.BORDER_CONSTANT)
        cv2.putText(panel,f'{row["slot_id"]} TRAIN FIT ONLY: original / old {scores[0]:.3f} / adapted {scores[1]:.3f}',(4,21),0,.46,(255,255,255),1)
        panels.append(panel)
        rows.append(dict(stem=stem,old_iou=scores[0],adapted_iou=scores[1]))
    output.mkdir()
    (output/'report.json').write_text(json.dumps(dict(rows=rows,role='TRAINING_FIT_ONLY',runtime_enabled=False),indent=2))
    cv2.imwrite(str(output/'comparison.jpg'),np.vstack(panels))
    negative_source=ROOT/'vision_assembly/segmentation/vrm_negative_review_v1'
    if negative_source.exists():
        negatives=[]
        for row in json.loads((negative_source/'manifest.json').read_text())['rows']:
            image=cv2.imread(str(negative_source/(row['stem']+'.png')))
            result=models[-1].predict(image,imgsz=320,device=0,conf=.25,retina_masks=True,verbose=False)[0]
            negatives.append(dict(stem=row['stem'],candidate_count=len(result.boxes),
                                  confidences=result.boxes.conf.cpu().tolist()))
        (output/'negative_fit.json').write_text(json.dumps(dict(role='REUSED_DEVELOPMENT_OR_TRAINING_NOT_INDEPENDENT',rows=negatives),indent=2))
        print(json.dumps(negatives,indent=2))
    print(json.dumps(rows,indent=2))


if __name__=='__main__':
    main()
