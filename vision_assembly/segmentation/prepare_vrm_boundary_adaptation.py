"""Three explicitly selected development scenes, SAM drafts never training truth."""
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from ultralytics import SAM
from build_vrm_fixed_crop_dataset import ROOT,FixedSlotCropper
from label_s22_parts_seg import sam_box_polygon
from common import save_yolo_segments

SELECTED={
    '20260905_vrm04_small_rotation_defect_a':'vrm_04',
    '20260905_vrm01_rotation_lip_144513':'vrm_01',
    '20260905_vrm02_translation_160027':'vrm_02',
}


def main():
    output=ROOT/'vision_assembly/segmentation/vrm_boundary_adaptation_v1'
    if output.exists():
        raise ValueError('Refusing overwrite')
    manifest=json.loads((ROOT/'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())
    scenes={s['physical_scene_id']:s for s in manifest['scenes']}
    partition=dict(adaptation_scene_ids=list(SELECTED),
        retained_development_validation_scene_ids=sorted(set(scenes)-set(SELECTED)),
        note='Entire scene excluded from later candidate evaluation if any crop is adapted. All scenes already inspected; retained validation is not blind. Drafts cannot be used for training.',
        training_allowed=False,normal_patchcore_training_allowed=False)
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    crops=[]
    for scene_id,slot_id in SELECTED.items():
        scene=scenes[scene_id]
        path=ROOT/scene['image']
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if scene.get('image_sha256') and digest!=scene['image_sha256']:
            raise ValueError('Source mismatch')
        board=cropper.register(cv2.imread(str(path)))
        if board.alignment_reason!='OK' or board.alignment_score<float(cropper.config['global_alignment']['minimum_score']):
            raise ValueError('Uncertain registration')
        slot=next(s for s in cropper.fixed_slots(board.image_bgr) if s.slot_id==slot_id)
        cx,cy,w,h=slot.geometry
        cw,ch=round(w*1.5),round(h*1.5)
        x0,y0=round(cx-cw/2),round(cy-ch/2)
        crop=board.image_bgr[y0:y0+ch,x0:x0+cw].copy()
        box=(max(0,round(cw*.10)),max(0,round(ch*.10)),min(cw-1,round(cw*.90)),min(ch-1,round(ch*.90)))
        crops.append((scene_id,slot_id,crop,box,dict(source_image=str(path),source_sha256=digest,
            origin_px=[x0,y0],crop_size_px=[cw,ch],expected_pose=scene['expected_pose'][slot_id])))
    model_path=ROOT/'vision_assembly/segmentation/models/sam2.1_t.pt'
    sam=SAM(str(model_path))
    for directory in ('images','draft_labels','reviews','metadata'):
        (output/directory).mkdir(parents=True,exist_ok=False)
    rows,panels=[],[]
    for scene_id,slot_id,crop,box,meta in crops:
        stem=f'{scene_id}__{slot_id}'
        polygon=sam_box_polygon(sam,crop,box,'0')
        cv2.imwrite(str(output/'images'/f'{stem}.png'),crop)
        if polygon is not None:
            save_yolo_segments(output/'draft_labels'/f'{stem}.txt',[(3,polygon)],crop.shape[1],crop.shape[0])
        meta.update(scene_id=scene_id,slot_id=slot_id,annotation_status='DRAFT_NOT_REVIEWED',
            training_allowed=False,normal_patchcore_training_allowed=False,sam_prompt_box=list(box),
            sam_model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
            crop_sha256=hashlib.sha256((output/'images'/f'{stem}.png').read_bytes()).hexdigest())
        (output/'metadata'/f'{stem}.json').write_text(json.dumps(meta,indent=2))
        overlay=crop.copy()
        if polygon is not None:
            cv2.polylines(overlay,[np.int32(polygon)],True,(0,180,255),1)
        panel=np.hstack([cv2.resize(crop,(300,380)),cv2.resize(overlay,(300,380))])
        panel=cv2.copyMakeBorder(panel,35,0,0,0,cv2.BORDER_CONSTANT)
        cv2.putText(panel,f'{slot_id} {scene_id[-6:]} RAW / SAM DRAFT - NOT GT',(4,24),0,.5,(255,255,255),1)
        panels.append(panel)
        rows.append(dict(stem=stem,**meta))
    partition['rows']=rows
    (output/'partition.json').write_text(json.dumps(partition,indent=2))
    cv2.imwrite(str(output/'draft_preview.jpg'),np.vstack(panels))
    print('Prepared3 drafts; training disabled',output)


if __name__=='__main__':
    main()
