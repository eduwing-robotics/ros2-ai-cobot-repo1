"""Show archived and new fixed-slot RGB crops; never infer a physical label."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper
from vrm_seating_common import crop_vrm_seating_slot


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--previous-crop',type=Path,default=ROOT/'vision_assembly/slot_classifier/datasets/vrm_seating_v3/crops/seating/vrm05_lip_194959__vrm_05.png')
    parser.add_argument('--previous-label',default='PREVIOUS 09-04 19:49:59')
    args=parser.parse_args()
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    source=cv2.imread(str(args.image))
    if source is None:
        raise ValueError('Unreadable current image')
    board=cropper.register(source)
    if board.alignment_reason!='OK' or board.alignment_score<cropper.config['global_alignment']['minimum_score']:
        raise ValueError('Uncertain board registration; comparison not exported')
    slot=next(s for s in cropper.fixed_slots(board.image_bgr) if s.slot_id=='vrm_05')
    current=crop_vrm_seating_slot(board.image_bgr,slot.geometry)
    old_path=args.previous_crop.resolve()
    old=cv2.imread(str(old_path))
    if old is None or old.shape!=current.shape:
        raise ValueError('Incompatible historical crop')
    args.output.mkdir(parents=True,exist_ok=False)
    cv2.imwrite(str(args.output/'current_vrm05.png'),current)
    panels=[]
    for label,crop in [(args.previous_label,old),('CURRENT '+args.image.stem.rsplit('_',1)[-1],current)]:
        panel=cv2.resize(crop,None,fx=2,fy=2,interpolation=cv2.INTER_NEAREST)
        panel=cv2.copyMakeBorder(panel,40,0,0,0,cv2.BORDER_CONSTANT)
        cv2.putText(panel,label,(12,27),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),1,cv2.LINE_AA)
        panels.append(panel)
    cv2.imwrite(str(args.output/'comparison.png'),np.hstack(panels))
    report=dict(current_image=str(args.image.resolve()),previous_crop=str(old_path),
        current_sha256=hashlib.sha256(args.image.read_bytes()).hexdigest(),
        previous_sha256=hashlib.sha256(old_path.read_bytes()).hexdigest(),
        alignment_score=board.alignment_score,
        label='UNCONFIRMED_PHYSICAL_SEATING',training_allowed=False,
        note='Identical fixed-slot crop contract; nearest-neighbor display only. No per-part registration or enhancement.',
        robot_command_sent=False,conveyor_command_sent=False)
    (args.output/'comparison.json').write_text(json.dumps(report,indent=2))
    print(args.output/'comparison.png')


if __name__=='__main__':
    main()
