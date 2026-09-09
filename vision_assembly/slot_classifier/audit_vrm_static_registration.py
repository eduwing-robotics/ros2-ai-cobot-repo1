"""Measure residual registration on static board pixels, without correcting parts."""
import json

import cv2
import numpy as np

from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper
from preprocessor_and_cropper import board_alignment_mask


def main():
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    def load(stamp):
        board=cropper.register(cv2.imread(str(ROOT/f'runtime/inspection/s22_inspection_roi_20260905_{stamp}.png')))
        if board.alignment_reason!='OK':
            raise ValueError('Registration failed')
        return board.image_bgr
    reference=load('134637')
    mask=board_alignment_mask(cropper.layout,reference.shape,cropper.board_size_mm,
        cropper.config['coordinate_mapping'],2.5)
    ref=cv2.cvtColor(reference,cv2.COLOR_BGR2GRAY)
    output=ROOT/'runtime/inspection/vrm_static_registration_20260905'
    output.mkdir(parents=True,exist_ok=True)
    rows=[]
    radius,search=15,10
    for stamp in ('143632','145643','150807'):
        current=load(stamp)
        gray=cv2.cvtColor(current,cv2.COLOR_BGR2GRAY)
        points=[]
        for y in range(35,ref.shape[0]-35,30):
            for x in range(35,ref.shape[1]-35,30):
                margin=radius+search
                if not np.all(mask[y-margin:y+margin+1,x-margin:x+margin+1]):
                    continue
                patch=ref[y-radius:y+radius+1,x-radius:x+radius+1]
                if patch.std()<3:
                    continue
                region=gray[y-margin:y+margin+1,x-margin:x+margin+1]
                response=cv2.matchTemplate(region,patch,cv2.TM_CCOEFF_NORMED)
                _,score,_,loc=cv2.minMaxLoc(response)
                alternate=response.copy()
                lx,ly=loc
                alternate[max(0,ly-3):ly+4,max(0,lx-3):lx+4]=-1
                gap=score-float(alternate.max())
                if score<.85 or gap<.03 or lx in (0,20) or ly in (0,20):
                    continue
                dx,dy=lx-search,ly-search
                points.append(dict(x=x,y=y,dx=dx,dy=dy,score=score,gap=gap))
                cv2.arrowedLine(current,(x,y),(x+dx*4,y+dy*4),(0,255,255),1)
        groups={}
        for name,selected in [('all',points),('left_board',[p for p in points if p['x']<400])]:
            displacement=np.array([[p['dx'],p['dy']] for p in selected])
            groups[name]=dict(count=len(selected),median_px=np.median(displacement,axis=0).tolist() if len(selected) else None)
        rows.append(dict(stamp=stamp,groups=groups,points=points))
        cv2.imwrite(str(output/f'{stamp}_static_arrows.jpg'),current)
        print(stamp,groups)
    (output/'residuals.json').write_text(json.dumps(dict(authority='ADVISORY_ONLY',
        note='Diagnostic static patch matches only; no image or slot coordinate corrections applied.',rows=rows),indent=2))


if __name__=='__main__':
    main()
