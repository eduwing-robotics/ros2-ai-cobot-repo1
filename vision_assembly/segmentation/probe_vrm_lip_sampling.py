"""CPU-only boundary sampling sensitivity; no fitting or production verdict."""
import hashlib
import argparse
import time
import json
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from build_vrm_fixed_crop_dataset import ROOT, FixedSlotCropper
from validate_vrm_boundary_scenes import summarize_mask
from vrm_duplicate_masks import deduplicate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--imgsz',type=int,choices=[320,640,960],default=320)
    parser.add_argument('--output',default='runtime/inspection/vrm_lip_sampling_sensitivity')
    parser.add_argument('--weights',default='vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1/weights/last.pt')
    parser.add_argument('--deduplicate',action='store_true',help='Diagnostic near-identical mask grouping, not runtime activation')
    parser.add_argument('--scenes', nargs='+', help='Explicit timestamp:flat or timestamp:seating diagnostic labels')
    args=parser.parse_args()
    torch.set_num_threads(2)
    weights=ROOT/args.weights
    model=YOLO(str(weights))
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    output=ROOT/args.output
    output.mkdir(exist_ok=False)
    rows=[]
    scenes=[('20260905_181938','flat'),('20260905_184100','seating'),('20260904_194959','seating')]
    if args.scenes:
        scenes=[item.split(':') for item in args.scenes]
        if any(len(item)!=2 or item[1] not in ('flat','seating') for item in scenes):
            raise ValueError('Expected timestamp:flat or timestamp:seating')
    for stamp,label in scenes:
        path=ROOT/f'runtime/inspection/s22_inspection_roi_{stamp}.png'
        board=cropper.register(cv2.imread(str(path)))
        assert board.alignment_reason=='OK'
        assert board.alignment_score>=float(cropper.config['global_alignment']['minimum_score'])
        slot=next(s for s in cropper.fixed_slots(board.image_bgr) if s.slot_id=='vrm_05')
        cx,cy,w,h=slot.geometry
        cw,ch=round(w*1.5),round(h*1.5)
        x,y=round(cx-cw/2),round(cy-ch/2)
        samples=[]
        for dx,dy in [(0,0),(-1,0),(1,0),(0,-1),(0,1)]:
            crop=board.image_bgr[y+dy:y+dy+ch,x+dx:x+dx+cw].copy()
            assert crop.shape[:2]==(ch,cw)
            started=time.perf_counter()
            result=model.predict(crop,imgsz=args.imgsz,device='cpu',conf=.25,retina_masks=True,verbose=False)[0]
            elapsed=time.perf_counter()-started
            central=[]
            if result.masks is not None:
                for poly,conf in zip(result.masks.xy,result.boxes.conf.tolist()):
                    summary=summarize_mask(poly,conf,cw,ch)
                    if summary and summary['central_candidate']:
                        points=np.asarray(poly)+[dx,dy]
                        summary['extent_in_fixed_crop']=[float(points[:,0].min()),float(points[:,1].min()),
                            float(points[:,0].max()),float(points[:,1].max())]
                        central.append(summary)
            unique,groups=deduplicate(central,cw,ch) if args.deduplicate else (central,[[i] for i in range(len(central))])
            # Different boundaries remain ambiguous. Original predictions preserved.
            samples.append(dict(offset=[dx,dy],elapsed_seconds=elapsed,central_count=len(central),
                unique_count=len(unique),duplicate_groups=groups,
                candidates=central,primary=unique[0] if len(unique)==1 else None))
        extents=[s['primary']['extent_in_fixed_crop'] for s in samples if s['primary']]
        rows.append(dict(image=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            label=label,samples=samples,extent_range_px=np.ptp(extents,axis=0).tolist() if len(extents)==5 else None,
            center_sampling_note='Offsets subtracted via mapping back to fixed crop; no part recentering or runtime image change'))
    (output/'report.json').write_text(json.dumps(dict(rows=rows,imgsz=args.imgsz,deduplicate=args.deduplicate,
        weights_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(), runtime_changed=False,
        authority='ADVISORY_ONLY',robot_command_sent=False,conveyor_command_sent=False,
        limitation='Artificial 1px input-window perturbation, not physical repeats or measured height/clearance. Selected retrospective examples.'),indent=2))
    for row in rows:
        print(row['image'], row['label'],row['extent_range_px'])


if __name__=='__main__':
    main()
