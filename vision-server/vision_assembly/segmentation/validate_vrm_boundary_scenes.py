"""Saved-scene boundary stress test. Not a production inspection or pose verdict."""
import hashlib
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from build_vrm_fixed_crop_dataset import FixedSlotCropper, ROOT
from vrm_duplicate_masks import deduplicate


def summarize_mask(poly,confidence,width,height):
    area=abs(float(cv2.contourArea(poly.astype(np.float32))))
    moments=cv2.moments(poly.astype(np.float32))
    if moments['m00']==0:
        return None
    center=[moments['m10']/moments['m00'],moments['m01']/moments['m00']]
    (_, _),(w,h),angle=cv2.minAreaRect(poly.astype(np.float32))
    if w<h:
        angle+=90
    angle=(angle+90)%180-90
    return dict(confidence=float(confidence),area_px=area,center_px=center,
        long_axis_deg=float(angle),polygon=poly.tolist(),
        central_candidate=bool(.2*width<center[0]<.8*width and .2*height<center[1]<.8*height))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',type=Path,default=ROOT/'vision_assembly/segmentation/runs/vrm_fixed_boundary_v1')
    parser.add_argument('--dataset',type=Path,default=ROOT/'vision_assembly/segmentation/vrm_fixed_boundary_dataset_v2')
    parser.add_argument('--checkpoint',choices=['best','last'],default='best')
    parser.add_argument('--fresh-image',type=Path)
    parser.add_argument('--imgsz',type=int,choices=(320,640),default=320)
    parser.add_argument('--device',choices=('cpu','0'),default='0')
    parser.add_argument('--deduplicate',action='store_true')
    args=parser.parse_args()
    if args.device!='cpu' and not torch.cuda.is_available():
        raise RuntimeError('GPU required')
    torch.set_num_threads(2)
    dataset=args.dataset.resolve()
    source_manifest=json.loads((dataset/'manifest.json').read_text())
    used_hashes={r['source_sha256'] for r in source_manifest['rows']}
    scenes=json.loads((ROOT/'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())['scenes']
    excluded=set(source_manifest.get('adaptation_scene_ids',[]))
    scenes=[s for s in scenes if s['physical_scene_id'] not in excluded]
    if args.fresh_image:
        fresh=args.fresh_image.resolve()
        fresh_hash=hashlib.sha256(fresh.read_bytes()).hexdigest()
        historical=json.loads((ROOT/'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())['scenes']
        if fresh_hash in used_hashes or any(hashlib.sha256((ROOT/s['image']).read_bytes()).hexdigest()==fresh_hash for s in historical):
            raise ValueError('Fresh image duplicates training or development source')
        scenes=[dict(physical_scene_id=fresh.stem,image=str(fresh),image_sha256=fresh_hash,labels={})]
    run=args.run.resolve()
    output=run/('saved_scene_validation' if args.checkpoint=='best' else 'saved_scene_validation_last')
    if args.fresh_image:
        output=run/('fresh_'+fresh.stem+'_'+args.checkpoint)
    if output.exists():
        raise ValueError('Refusing to overwrite validation')
    weights=run/f'weights/{args.checkpoint}.pt'
    digest=hashlib.sha256(weights.read_bytes()).hexdigest()
    model=YOLO(str(weights))
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    output.mkdir()
    rows=[]
    for scene in scenes:
        path=ROOT/scene['image']
        image_hash=hashlib.sha256(path.read_bytes()).hexdigest()
        if scene.get('image_sha256') and image_hash!=scene['image_sha256']:
            raise ValueError('Scene image changed')
        if image_hash in used_hashes:
            raise ValueError('Scene overlaps boundary training/validation/test source')
        board=cropper.register(cv2.imread(str(path)))
        if board.alignment_reason!='OK' or board.alignment_score<float(cropper.config['global_alignment']['minimum_score']):
            raise ValueError(f'Uncertain registration: {path}')
        panels=[]
        for slot in cropper.fixed_slots(board.image_bgr):
            if slot.component_type!='VRM':
                continue
            cx,cy,w,h=slot.geometry
            cw,ch=round(w*1.5),round(h*1.5)
            x0,y0=round(cx-cw/2),round(cy-ch/2)
            if x0<0 or y0<0 or x0+cw>board.image_bgr.shape[1] or y0+ch>board.image_bgr.shape[0]:
                raise ValueError('Crop outside board')
            crop=board.image_bgr[y0:y0+ch,x0:x0+cw].copy()
            prediction=model.predict(crop,imgsz=args.imgsz,device=args.device,conf=.25,retina_masks=True,verbose=False)[0]
            candidates=[]
            if prediction.masks is not None:
                for poly,confidence in zip(prediction.masks.xy,prediction.boxes.conf.cpu().tolist()):
                    summary=summarize_mask(poly,confidence,cw,ch)
                    if summary:
                        summary['extent_in_fixed_crop']=[float(poly[:,0].min()),float(poly[:,1].min()),float(poly[:,0].max()),float(poly[:,1].max())]
                        candidates.append(summary)
            central=[c for c in candidates if c['central_candidate']]
            unique,groups=deduplicate(central,cw,ch) if args.deduplicate else (central,[])
            primary=(unique[0] if len(unique)==1 else None) if args.deduplicate else (max(central,key=lambda c:c['area_px']) if central else None)
            row=dict(scene=scene['physical_scene_id'],slot=slot.slot_id,source_image=str(path),
                image_sha256=image_hash,expected_presence=scene.get('labels',{}).get(slot.slot_id,'UNKNOWN'),
                expected_pose=scene.get('expected_pose',{}).get(slot.slot_id,'UNKNOWN'),
                process_position_review=scene.get('process_position_review'),
                status='UNKNOWN',alignment_score=board.alignment_score,crop_origin_px=[x0,y0],
                candidates=candidates,primary=primary,central_candidate_count=len(central),
                unique_central_count=len(unique),duplicate_groups=groups)
            rows.append(row)
            overlay=crop.copy()
            for c in candidates:
                cv2.polylines(overlay,[np.int32(c['polygon'])],True,(0,170,255),1)
            panel=np.hstack([cv2.resize(crop,(150,190)),cv2.resize(overlay,(150,190))])
            panel=cv2.copyMakeBorder(panel,40,0,0,0,cv2.BORDER_CONSTANT)
            cv2.putText(panel,f'{slot.slot_id} GT {row["expected_presence"]} / {row["expected_pose"]}',(3,15),0,.35,(255,255,255),1)
            cv2.putText(panel,f'candidates {len(candidates)} - ADVISORY',(3,32),0,.35,(255,255,255),1)
            panels.append(panel)
        cv2.imwrite(str(output/(scene['physical_scene_id']+'.jpg')),np.hstack(panels))
        print(scene['physical_scene_id'],'done',flush=True)
    references={r['slot']:r['primary'] for r in rows if r['scene']=='20260905_all_vrm_flat_143632'}
    for row in rows:
        ref=references.get(row['slot'])
        if ref and row['primary']:
            row['relative_center_px']=(np.array(row['primary']['center_px'])-ref['center_px']).tolist()
            row['relative_angle_deg']=(row['primary']['long_axis_deg']-ref['long_axis_deg']+90)%180-90
    labelled_present=[r for r in rows if r['expected_presence']=='PRESENT']
    labelled_empty=[r for r in rows if r['expected_presence']=='EMPTY']
    summary=dict(present_slots=len(labelled_present),present_with_central_candidate=sum(r['primary'] is not None for r in labelled_present),
                 empty_slots=len(labelled_empty),empty_with_central_candidate=sum(r['primary'] is not None for r in labelled_empty),
                 physical_scenes=len(scenes),total_slots=len(rows),
                 present_without_any_candidate=sum(r['central_candidate_count']==0 for r in labelled_present),
                 present_ambiguous=sum(r['unique_central_count']>1 for r in labelled_present),
                 empty_with_any_candidate=sum(r['central_candidate_count']>0 for r in labelled_empty))
    (output/'report.json').write_text(json.dumps(dict(summary=summary,rows=rows,weights_sha256=digest,
        imgsz=args.imgsz,device=args.device,deduplicate=args.deduplicate,
        excluded_adaptation_scene_ids=sorted(excluded),authority='ADVISORY_ONLY',runtime_enabled=False,robot_command_sent=False,conveyor_command_sent=False,
        limitation=('New source hash; physical truth not inferred, all labels UNKNOWN. ' if args.fresh_image else 'Previously reviewed development scenes, not blind production trials. ')+ 'No mask ground truth: no quantitative contour/angle accuracy claim. Candidate presence is not fused presence. Fixed conf.25; central region20-80% used only to separate neighboring fragments. No threshold fitting.'),indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
