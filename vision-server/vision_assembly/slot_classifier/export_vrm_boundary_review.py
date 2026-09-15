"""Coordinate-labelled raw crops for boundary review, not inferred ground truth."""
import json
import argparse
from pathlib import Path
import cv2
import numpy as np
from audit_vrm_texture_motion import ROOT, FixedSlotCropper, load_slots


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cases',nargs='+',help='STAMP:slot pairs, in groups of three')
    parser.add_argument('--output',type=Path,default=ROOT/'runtime/inspection/vrm_boundary_review_160027')
    args=parser.parse_args()
    out=args.output
    out.mkdir(parents=True,exist_ok=True)
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    cases=[('134637','vrm_05'),('143632','vrm_05'),('154927','vrm_05'),
           ('134637','vrm_02'),('154927','vrm_02'),('160027','vrm_02')]
    if args.cases:
        cases=[tuple(c.split(':')) for c in args.cases]
    if len(cases)%3 or any(len(c)!=2 for c in cases):
        raise ValueError('Expected groups of three STAMP:slot pairs')
    panels=[]
    for stamp,slot in cases:
        crop,_=load_slots(cropper,ROOT/f'runtime/inspection/s22_inspection_roi_20260905_{stamp}.png')[slot]
        cv2.imwrite(str(out/f'{stamp}_{slot}_raw.png'),crop)
        # Exact nearest-neighbor magnification, no invented high-frequency detail.
        panel=cv2.resize(crop,None,fx=2,fy=2,interpolation=cv2.INTER_NEAREST)
        panel=cv2.copyMakeBorder(panel,35,0,35,0,cv2.BORDER_CONSTANT)
        cv2.putText(panel,f'{stamp} {slot}',(40,16),0,.5,(255,255,255),1)
        for x in range(0,crop.shape[1],20):
            cv2.putText(panel,str(x),(35+x*2,32),0,.3,(255,255,255),1)
        for y in range(0,crop.shape[0],20):
            cv2.putText(panel,str(y),(1,35+y*2),0,.3,(255,255,255),1)
        panels.append(panel)
    cv2.imwrite(str(out/'review.png'),np.vstack([np.hstack(panels[i:i+3]) for i in range(0,len(panels),3)]))
    (out/'review.json').write_text(json.dumps(dict(authority='ADVISORY_ONLY',
        note='Raw fixed-slot crops. No automatic polygon is ground truth. Hidden inner socket wall must remain unlabelled.',
        cases=cases,training_allowed=False,robot_command_sent=False,conveyor_command_sent=False),indent=2))
    print(out)


if __name__=='__main__':
    main()
