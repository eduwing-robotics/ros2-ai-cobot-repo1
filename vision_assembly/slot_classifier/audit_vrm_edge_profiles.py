"""Independent local edge profiles: diagnostic only, no image pose correction."""
import json
import argparse
from pathlib import Path

import cv2
import numpy as np

from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper


def boundaries(crop, mode):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if mode == 'clahe':
        gray = cv2.createCLAHE(2., (8, 8)).apply(gray)
    gray = cv2.GaussianBlur(gray, (5, 5), 1.).astype(np.float32)
    h, w = gray.shape
    xp = np.median(gray[round(h*.3):round(h*.7)], axis=0)
    yp = np.median(gray[:, round(w*.3):round(w*.7)], axis=1)
    result = []
    # Signed edge from dark gap to brighter component. Can still select a socket edge.
    for profile, lo, hi, sign in [(xp,.08,.38,1),(yp,.08,.38,1),
                                   (xp,.62,.92,-1),(yp,.62,.92,-1)]:
        derivative = np.gradient(profile)*sign
        a, b = round(len(profile)*lo), round(len(profile)*hi)
        peak = a+int(np.argmax(derivative[a:b]))
        result.append(dict(position=peak, strength=float(derivative[peak])))
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--stamps',nargs='+',default=['154927','155509','155745','160027'])
    parser.add_argument('--output',type=Path,default=ROOT/'runtime/inspection/vrm_edge_profiles_160027')
    args=parser.parse_args()
    if args.stamps[0]!='154927':
        raise ValueError('Frozen baseline154927 must be first')
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    cropper = FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    manifest = json.loads((ROOT/'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())
    expected = {s['image'].rsplit('_',1)[-1][:6]: s.get('expected_pose', {}) for s in manifest['scenes']}
    rows, panels, baseline = [], [], {}
    for stamp in args.stamps:
        board = cropper.register(cv2.imread(str(ROOT/f'runtime/inspection/s22_inspection_roi_20260905_{stamp}.png')))
        if board.alignment_reason != 'OK' or board.alignment_score < float(cropper.config['global_alignment']['minimum_score']):
            raise ValueError('Uncertain alignment')
        for slot in cropper.fixed_slots(board.image_bgr):
            if slot.component_type != 'VRM':
                continue
            x,y,w,h = slot.geometry
            crop = cv2.getRectSubPix(board.image_bgr,(round(w*1.5),round(h*1.5)),(float(x),float(y)))
            raw, enhanced = boundaries(crop,'raw'), boundaries(crop,'clahe')
            positions = np.array([r['position'] for r in raw])
            cpositions = np.array([r['position'] for r in enhanced])
            if stamp == '154927':
                baseline[slot.slot_id] = positions
            row = dict(stamp=stamp,slot=slot.slot_id,expected=expected.get(stamp,{}).get(slot.slot_id,'UNSPECIFIED'),
                raw=raw,clahe=enhanced,raw_clahe_disagreement_px=np.abs(positions-cpositions).tolist(),
                raw_delta_from_normal_px=(positions-baseline[slot.slot_id]).tolist(),status='UNKNOWN')
            rows.append(row)
            overlay=crop.copy()
            for bounds,color in ((positions,(0,255,0)),(cpositions,(0,180,255))):
                left,top,right,bottom=map(int,bounds)
                cv2.rectangle(overlay,(left,top),(right,bottom),color,1)
            pair=np.hstack([cv2.resize(crop,(200,250)),cv2.resize(overlay,(200,250))])
            pair=cv2.copyMakeBorder(pair,25,0,0,0,cv2.BORDER_CONSTANT)
            cv2.putText(pair,f'{stamp} {slot.slot_id} raw/CLAHE edges',(3,17),0,.4,(255,255,255),1)
            panels.append(pair)
    cv2.imwrite(str(output/'comparison.jpg'),np.vstack([np.hstack(panels[i:i+5]) for i in range(0,len(panels),5)]))
    (output/'report.json').write_text(json.dumps(dict(authority='ADVISORY_ONLY',runtime_enabled=False,
        note='Profile edge candidates, not verified inner socket boundaries. No transforms or verdicts applied.',
        robot_command_sent=False,conveyor_command_sent=False,rows=rows),indent=2))
    for row in rows:
        print(row['stamp'],row['slot'],row['expected'],row['raw_delta_from_normal_px'],row['raw_clahe_disagreement_px'])


if __name__=='__main__':
    main()
