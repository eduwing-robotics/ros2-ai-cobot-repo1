"""Saved-scene score diagnostic, not a threshold calibration or runtime change."""
import hashlib
import json
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from build_vrm_fixed_crop_dataset import ROOT, FixedSlotCropper
from validate_vrm_boundary_scenes import summarize_mask


def main():
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required')
    torch.set_num_threads(2)
    run=ROOT/'vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1'
    output=run/'regression_diagnostic'
    if output.exists():
        raise FileExistsError(output)
    prior=json.loads((run/'saved_scene_validation/report.json').read_text())
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    boards={}
    for row in prior['rows']:
        path=row['source_image']
        if path not in boards:
            if hashlib.sha256(open(path,'rb').read()).hexdigest()!=row['image_sha256']:
                raise ValueError('Source changed')
            board=cropper.register(cv2.imread(path))
            if board.alignment_reason!='OK' or board.alignment_score<cropper.config['global_alignment']['minimum_score']:
                raise ValueError('Alignment failed')
            boards[path]=board.image_bgr
    output.mkdir()
    results=[]
    panels=[]
    for checkpoint in ['best','last']:
        weight=run/f'weights/{checkpoint}.pt'
        model=YOLO(str(weight))
        rows=[]
        for original in prior['rows']:
            x,y=original['crop_origin_px']
            crop=boards[original['source_image']][y:y+241,x:x+189].copy()
            pred=model.predict(crop,imgsz=320,device=0,conf=.001,retina_masks=True,verbose=False)[0]
            candidates=[]
            if pred.masks is not None:
                for poly,conf in zip(pred.masks.xy,pred.boxes.conf.cpu().tolist()):
                    candidate=summarize_mask(poly,conf,189,241)
                    if candidate and candidate['central_candidate']:
                        candidates.append(candidate)
            top=max(candidates,key=lambda c:c['confidence']) if candidates else None
            rows.append(dict(scene=original['scene'],slot=original['slot'],truth=original['expected_presence'],
                             top_confidence=top['confidence'] if top else 0.,top=top))
            if original['expected_presence']=='PRESENT' and original['primary'] is None:
                overlay=crop.copy()
                if top:
                    cv2.polylines(overlay,[np.int32(top['polygon'])],True,(0,170,255),1)
                panel=np.hstack([crop,overlay])
                panel=cv2.copyMakeBorder(panel,40,0,0,0,cv2.BORDER_CONSTANT)
                cv2.putText(panel,f'{checkpoint} {original["slot"]} conf {rows[-1]["top_confidence"]:.4f}',(3,16),0,.45,(255,255,255),1)
                cv2.putText(panel,original['scene'][-20:],(3,34),0,.4,(255,255,255),1)
                panels.append(panel)
        present=[r['top_confidence'] for r in rows if r['truth']=='PRESENT']
        empty=[r['top_confidence'] for r in rows if r['truth']=='EMPTY']
        summary=dict(present=len(present),present_at_025=sum(c>=.25 for c in present),
                     empty=len(empty),empty_at_025=sum(c>=.25 for c in empty),
                     min_present_score=min(present),max_empty_score=max(empty))
        results.append(dict(checkpoint=checkpoint,weights_sha256=hashlib.sha256(weight.read_bytes()).hexdigest(),summary=summary,rows=rows))
        print(checkpoint,summary,flush=True)
    cv2.imwrite(str(output/'missed_normal_comparison.jpg'),np.vstack(panels))
    (output/'report.json').write_text(json.dumps(dict(role='PREVIOUSLY_REVIEWED_DEVELOPMENT_DIAGNOSTIC',
        runtime_enabled=False,threshold_changed=False,results=results,
        limitation='No boundary ground truth. Top-confidence central mask for score diagnosis, not pose or presence authority; no threshold fitted.'),indent=2))


if __name__=='__main__':
    main()
