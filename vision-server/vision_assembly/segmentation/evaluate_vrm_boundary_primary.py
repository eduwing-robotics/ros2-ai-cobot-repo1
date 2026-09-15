"""One fixed test evaluation; primary-mask IoU and image-space center error."""
import json
from pathlib import Path
import cv2
import numpy as np
from ultralytics import YOLO
from common import load_yolo_segments

ROOT=Path(__file__).resolve().parents[2]


def centroid(mask):
    m=cv2.moments(mask)
    return np.array([m['m10']/m['m00'],m['m01']/m['m00']]) if m['m00'] else None


def main():
    run=ROOT/'vision_assembly/segmentation/runs/vrm_fixed_boundary_v1'
    data=ROOT/'vision_assembly/segmentation/vrm_fixed_boundary_dataset_v2'
    output=run/'primary_test'
    if output.exists():
        raise ValueError('Existing test evaluation; do not overwrite')
    model=YOLO(str(run/'weights/best.pt'))
    rows,panels=[],[]
    for row in json.loads((data/'manifest.json').read_text())['rows']:
        if row['split']!='test':
            continue
        image=cv2.imread(str(data/'images/test'/(row['stem']+'.png')))
        h,w=image.shape[:2]
        truth=load_yolo_segments(data/'labels/test'/(row['stem']+'.txt'),w,h)[0][1]
        mask=np.zeros((h,w),np.uint8)
        cv2.fillPoly(mask,[np.int32(truth)],1)
        result=model.predict(image,imgsz=320,device=0,conf=.25,retina_masks=True,verbose=False)[0]
        candidates=[]
        if result.masks is not None:
            for poly in result.masks.xy:
                predicted=np.zeros_like(mask)
                cv2.fillPoly(predicted,[np.int32(poly)],1)
                intersection=np.logical_and(mask,predicted).sum()
                union=np.logical_or(mask,predicted).sum()
                candidates.append((float(intersection/max(union,1)),predicted,poly))
        best=max(candidates,key=lambda item:item[0]) if candidates else None
        iou=best[0] if best else 0.
        error=float(np.linalg.norm(centroid(mask)-centroid(best[1]))) if best and best[0]>0 and centroid(best[1]) is not None else None
        rows.append(dict(stem=row['stem'],slot=row['slot'],primary_mask_iou=iou,
                         center_error_px=error,predicted_instances=len(candidates)))
        overlay=image.copy()
        cv2.polylines(overlay,[np.int32(truth)],True,(0,255,0),1)
        if best:
            cv2.polylines(overlay,[np.int32(best[2])],True,(0,160,255),1)
        panel=np.hstack([cv2.resize(image,(140,180)),cv2.resize(overlay,(140,180))])
        panel=cv2.copyMakeBorder(panel,25,0,0,0,cv2.BORDER_CONSTANT)
        cv2.putText(panel,f'{row["slot"]} IoU {iou:.3f} green=GT orange=pred',(2,17),0,.32,(255,255,255),1)
        panels.append(panel)
    errors=[r['center_error_px'] for r in rows if r['center_error_px'] is not None]
    report=dict(authority='ADVISORY_ONLY',runtime_enabled=False,rows=rows,
        primary_iou_mean=float(np.mean([r['primary_mask_iou'] for r in rows])),
        primary_iou_min=min(r['primary_mask_iou'] for r in rows),
        center_error_mean_px=float(np.mean(errors)) if errors else None,
        center_error_max_px=max(errors) if errors else None,
        limitation='Test normal crops only; GT-best-IoU association is evaluation matching, not deployment selection. No empty or rotation-defect accuracy claim.')
    output.mkdir()
    (output/'report.json').write_text(json.dumps(report,indent=2))
    cv2.imwrite(str(output/'comparison.jpg'),np.vstack([np.hstack(panels[i:i+5]) for i in range(0,len(panels),5)]))
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))


if __name__=='__main__':
    main()
