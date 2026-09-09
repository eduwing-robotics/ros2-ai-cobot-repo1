"""Diagnostic board-only registration using four fixed mounting holes."""
import json
import os
from pathlib import Path
import sys
import cv2
import numpy as np
from preprocessor_and_cropper import FixedSlotCropper

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'vision_assembly/inspection'))
from build_component_patchcore_dataset import _crop_slot, OUTPUT_SIZE
from predict_component_patchcore import _checkpoint, _predict_outputs


def main():
    os.environ.setdefault('HF_HUB_OFFLINE','1')
    out=ROOT/'runtime/inspection/patchcore/board_hole_registration_audit_20260906'
    crops=out/'crops'; crops.mkdir(parents=True,exist_ok=True)
    reference=cv2.imread(str(ROOT/'runtime/inspection/hybrid_fixed_slot/20260906_183337_961766/aligned_board.png'))
    h,w=reference.shape[:2]
    # Outer mounting holes, not removable components or yellow jig pins.
    points=[(.157,.046),(.843,.046),(.157,.955),(.843,.955)]
    gray_ref=cv2.cvtColor(reference,cv2.COLOR_BGR2GRAY)
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    slot=next(s for s in cropper.fixed_slots(reference) if s.slot_id=='inductor_01')
    report=[]
    runs=['hybrid_fixed_slot/20260906_184959_868834',
          'hybrid_inductor_candidate_validation/20260906_194334_346601',
          'hybrid_fixed_slot/20260906_195725_970872']
    for index,run in enumerate(runs):
        board=cv2.imread(str(ROOT/'runtime/inspection'/run/'aligned_board.png'))
        gray=cv2.cvtColor(board,cv2.COLOR_BGR2GRAY)
        source=[]; target=[]; checks=[]
        debug=board.copy()
        for fx,fy in points:
            x,y=round(fx*w),round(fy*h)
            template=gray_ref[y-25:y+26,x-25:x+26]
            search=gray[y-40:y+41,x-40:x+41]
            response=cv2.matchTemplate(search,template,cv2.TM_CCOEFF_NORMED)
            _,score,_,loc=cv2.minMaxLoc(response)
            dx,dy=loc[0]-15,loc[1]-15
            source.append([x+dx,y+dy]);target.append([x,y])
            checks.append(dict(reference=[x,y],displacement_px=[dx,dy],ncc=score))
            cv2.rectangle(debug,(x-25+dx,y-25+dy),(x+25+dx,y+25+dy),(0,255,0),2)
        if min(c['ncc'] for c in checks)<.85:
            raise RuntimeError(f'Unreliable hole match: {checks}')
        H=cv2.getPerspectiveTransform(np.float32(source),np.float32(target))
        corrected=cv2.warpPerspective(board,H,(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
        for label,im in [('original',board),('hole_corrected',corrected)]:
            crop,_,_=_crop_slot(im,slot.geometry,.22,OUTPUT_SIZE['Inductor'])
            cv2.imwrite(str(crops/f'{index}_{label}.png'),crop)
        cv2.imwrite(str(out/f'{index}_landmarks.jpg'),debug)
        report.append(dict(run=run,landmarks=checks,homography=H.tolist()))
    scores={}
    for label,models in [('active',ROOT/'runtime/inspection/patchcore/pcb_components_strict_v4'),
                         ('candidate',ROOT/'runtime/inspection/patchcore/inductor_appearance_candidate_20260906/models')]:
        pred=_predict_outputs('inductor',crops,_checkpoint(models,'inductor'),out/label)
        scores[label]={k:float(v['score']) for k,v in pred.items()}
    payload=dict(rows=report,scores=scores,policy='DIAGNOSTIC_ONLY_NOT_DEPLOYED',
                 limitation='Integer template matching with four preselected mounting holes; residual interpolation/view effects remain. No part-local normalization.')
    (out/'audit.json').write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps(payload,indent=2))


if __name__=='__main__': main()
