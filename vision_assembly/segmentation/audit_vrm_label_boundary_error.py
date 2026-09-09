"""Pixel error against existing approximate test polygons; not physical metrology."""
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from common import load_yolo_segments

ROOT=Path(__file__).resolve().parents[2]


def errors(truth,predicted,width,height):
    masks=[]
    bounds=[]
    for polygon in (truth,predicted):
        polygon=np.asarray(polygon,dtype=np.float32)
        if polygon.ndim!=2 or polygon.shape[1]!=2 or len(polygon)<3 or not np.isfinite(polygon).all():
            raise ValueError('Invalid polygon')
        mask=np.zeros((height,width),np.uint8)
        cv2.fillPoly(mask,[np.int32(polygon)],1)
        if not mask.any():
            raise ValueError('Empty mask')
        masks.append(mask)
        bounds.append(np.r_[polygon.min(axis=0),polygon.max(axis=0)])
    edges=[m-cv2.erode(m,np.ones((3,3),np.uint8)) for m in masks]
    distances=[cv2.distanceTransform(1-e,cv2.DIST_L2,cv2.DIST_MASK_PRECISE) for e in edges]
    samples=np.r_[distances[0][edges[1]>0],distances[1][edges[0]>0]]
    return dict(iou=float(np.logical_and(*masks).sum()/np.logical_or(*masks).sum()),
        boundary_p95_px=float(np.percentile(samples,95)),boundary_max_px=float(samples.max()),
        extent_max_error_px=float(np.max(np.abs(bounds[0]-bounds[1]))))


def main():
    torch.set_num_threads(2)
    dataset=ROOT/'vision_assembly/segmentation/vrm_fixed_boundary_dataset_v4'
    manifest=json.loads((dataset/'manifest.json').read_text())
    output=ROOT/'runtime/inspection/vrm_label_boundary_error.json'
    if output.exists():
        raise FileExistsError(output)
    models=[('original320','vrm_fixed_boundary_negative_v1','last',320),
            ('candidate640','vrm_boundary_640_candidate_20260907','best',640)]
    reports=[]
    for name,run,checkpoint,size in models:
        weights=ROOT/f'vision_assembly/segmentation/runs/{run}/weights/{checkpoint}.pt'
        model=YOLO(str(weights))
        rows=[]
        for row in manifest['rows']:
            if row['split']!='test':
                continue
            path=dataset/'images/test'/f"{row['stem']}.png"
            labels=dataset/'labels/test'/f"{row['stem']}.txt"
            image=cv2.imread(str(path)); h,w=image.shape[:2]
            truths=load_yolo_segments(labels,w,h)
            assert len(truths)==1, 'This audit requires one ground-truth object'
            result=model.predict(image,imgsz=size,device='cpu',conf=.25,retina_masks=True,verbose=False)[0]
            candidates=[] if result.masks is None else [errors(truths[0][1],poly,w,h) for poly in result.masks.xy]
            # Oracle matching is evaluation only, not a runtime selection policy.
            best=max(candidates,key=lambda x:x['iou']) if candidates else None
            rows.append(dict(stem=row['stem'],crop_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                label_sha256=hashlib.sha256(labels.read_bytes()).hexdigest(),candidates=len(candidates),matched=best))
        summary={field:dict(median=float(np.median([r['matched'][field] for r in rows if r['matched']])),
                            worst=float(max(r['matched'][field] for r in rows if r['matched'])))
                 for field in ['boundary_p95_px','boundary_max_px','extent_max_error_px']}
        reports.append(dict(model=name,weights_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(),rows=rows,summary=summary))
        print(name,json.dumps(summary))
    output.write_text(json.dumps(dict(reports=reports,runtime_changed=False,training_performed=False,
        robot_command_sent=False,conveyor_command_sent=False,
        limitation='10 reused normal-only test crops; approximate labels, best-IoU oracle matching, no claim of physical1mm or lip detection accuracy.'),indent=2))


if __name__=='__main__':
    main()
