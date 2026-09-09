"""Capture-independent diagnostic for a user-prepared empty SMD02 image."""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import cv2
import numpy as np
from preprocessor_and_cropper import FixedSlotCropper
from audit_smd02_empty_wall import edge_candidates

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('image',type=Path)
    parser.add_argument('--preparation',choices=('empty','restored'),default='empty')
    args=parser.parse_args()
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    registered=cropper.register(cv2.imread(str(args.image)))
    if registered.alignment_reason!='OK' or registered.alignment_score<cropper.config['global_alignment']['minimum_score']:
        raise ValueError(f'Invalid registration: {registered.alignment_reason}')
    slot=next(s for s in cropper.fixed_slots(registered.image_bgr) if s.slot_id=='smd_capacitor_02')
    cx,cy,_,_=slot.geometry
    x,y=int(cx)-65,int(cy)-85
    crop=registered.image_bgr[y:y+170,x:x+130].copy()
    if crop.shape!=(170,130,3):
        raise ValueError('Clipped crop')
    gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
    edges=edge_candidates(gray,[x,y])
    # Unmodified corrected CAD SMD02 polygon, previously extracted face1206.
    polygon=np.array([[1467.62085,790.75964],[1467.62085,880.27130],
                      [1522.89124,880.27130],[1522.89124,790.75964]])
    overlay=crop.copy()
    cv2.polylines(overlay,[np.rint(polygon-[x,y]).astype(np.int32)],True,(0,200,255),1)
    local=cv2.createCLAHE(clipLimit=2.,tileGridSize=(8,8)).apply(gray)
    comparison=cv2.resize(np.hstack([crop,overlay,cv2.cvtColor(local,cv2.COLOR_GRAY2BGR)]),None,
                          fx=4,fy=4,interpolation=cv2.INTER_NEAREST)
    out=Path(tempfile.mkdtemp(prefix=f'smd02_current_{args.preparation}_',dir=ROOT/'runtime/inspection'))
    for name,image in [('comparison.png',comparison),('crop.png',crop),('aligned_board.png',registered.image_bgr)]:
        if not cv2.imwrite(str(out/name),image):
            raise OSError(name)
    payload=dict(source=str(args.image),source_sha256=hashlib.sha256(args.image.read_bytes()).hexdigest(),
        preparation=f'User acknowledged SMD02 {args.preparation} preparation; not an automatic training label',
        alignment_score=registered.alignment_score,crop_origin=[x,y],edges=edges,
        status='DIAGNOSTIC_ONLY',runtime_changed=False,motion_command_sent=False,
        limitation='Strongest edges are not certified inner walls; no automatic calibration or training.')
    (out/'audit.json').write_text(json.dumps(payload,indent=2))
    print(out)
    print(json.dumps(payload))


if __name__=='__main__':
    main()
