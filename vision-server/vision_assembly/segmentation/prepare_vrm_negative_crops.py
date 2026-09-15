"""Prepare saved empty-slot crops for visual review, never auto-label neighbors."""
import hashlib
import json
import cv2
import numpy as np
from build_vrm_fixed_crop_dataset import ROOT, FixedSlotCropper


def main():
    output=ROOT/'vision_assembly/segmentation/vrm_negative_review_v1'
    if output.exists():
        raise FileExistsError(output)
    selected={'20260905_vrm02_04_empty_a','20260905_vrm04_small_rotation_defect_a'}
    scenes=json.loads((ROOT/'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())['scenes']
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    output.mkdir()
    rows,panels=[],[]
    for scene in scenes:
        if scene['physical_scene_id'] not in selected:
            continue
        path=ROOT/scene['image']
        board=cropper.register(cv2.imread(str(path)))
        if board.alignment_reason!='OK' or board.alignment_score<cropper.config['global_alignment']['minimum_score']:
            raise ValueError('Registration failed')
        for slot in cropper.fixed_slots(board.image_bgr):
            if scene['labels'].get(slot.slot_id)!='EMPTY':
                continue
            cx,cy,w,h=slot.geometry
            cw,ch=round(w*1.5),round(h*1.5)
            x,y=round(cx-cw/2),round(cy-ch/2)
            crop=board.image_bgr[y:y+ch,x:x+cw].copy()
            if crop.shape[:2]!=(ch,cw):
                raise ValueError('Crop bounds')
            stem=scene['physical_scene_id']+'__'+slot.slot_id
            target=output/(stem+'.png')
            cv2.imwrite(str(target),crop)
            rows.append(dict(stem=stem,scene=scene['physical_scene_id'],slot=slot.slot_id,
                source_image=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                crop_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),origin_px=[x,y],
                expected_presence='EMPTY',review_status='NEEDS_VISIBLE_NEIGHBOR_REVIEW'))
            panel=cv2.copyMakeBorder(crop,30,0,0,0,cv2.BORDER_CONSTANT)
            cv2.putText(panel,scene['image'][-10:-4]+' '+slot.slot_id,(3,20),0,.45,(255,255,255),1)
            panels.append(panel)
    (output/'manifest.json').write_text(json.dumps(dict(rows=rows,training_allowed=False),indent=2))
    cv2.imwrite(str(output/'preview.jpg'),np.hstack(panels))


if __name__=='__main__':
    main()
