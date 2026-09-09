"""Offline empty-socket dark-groove reference, not calibrated hole metrology."""
import json

import cv2
import numpy as np

from audit_vrm_texture_motion import ROOT, FixedSlotCropper, load_slots


def groove_bounds(crop):
    gray = cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray,(5,5),1).astype(float)
    h,w = gray.shape
    # Average central profiles to suppress print texture and avoid corners.
    xp = np.median(gray[round(h*.32):round(h*.68)],axis=0)
    yp = np.median(gray[:,round(w*.32):round(w*.68)],axis=1)
    def minimum(profile,a,b):
        lo,hi = round(len(profile)*a),round(len(profile)*b)
        return int(lo+np.argmin(profile[lo:hi]))
    return [minimum(xp,.04,.35),minimum(yp,.04,.35),
            minimum(xp,.65,.96),minimum(yp,.65,.96)]


def main():
    cropper = FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    output = ROOT/'runtime/inspection/vrm_socket_reference_audit_20260905'
    output.mkdir(parents=True,exist_ok=True)
    def source(stamp):
        return ROOT/f'runtime/inspection/s22_inspection_roi_20260905_{stamp}.png'
    empty = load_slots(cropper,source('134637'))
    bounds = {slot:groove_bounds(crop) for slot,(crop,_) in empty.items()}
    fitted=json.loads((ROOT/'runtime/inspection/vrm_outline_blur1_20260905/edges.json').read_text())['rows']
    fitted+=json.loads((ROOT/'runtime/inspection/vrm_outline_blur1_holdout_150807/edges.json').read_text())['rows']
    lookup={(r['stamp'],r['slot']):r for r in fitted}
    panels,rows = [],[]
    for stamp in ('134637','143632','145643','150807'):
        for slot,(crop,size) in load_slots(cropper,source(stamp)).items():
            left,top,right,bottom = bounds[slot]
            overlay=crop.copy()
            cv2.rectangle(overlay,(left,top),(right,bottom),(255,180,0),1)
            panel=cv2.resize(overlay,(240,300))
            panel=cv2.copyMakeBorder(panel,25,0,0,0,cv2.BORDER_CONSTANT)
            cv2.putText(panel,f'{stamp} {slot} GROOVE?',(3,17),0,.45,(255,255,255),1)
            panels.append(panel)
            row=dict(stamp=stamp,slot=slot,bounds=bounds[slot],status='UNKNOWN')
            entry=lookup.get((stamp,slot))
            if entry and entry['grabcut']:
                c,s,a=entry['grabcut']['rect']
                points=cv2.boxPoints((tuple(c),tuple(s),a))
                # Signed gap to the groove: negative means fitted outline crosses it.
                row['signed_groove_gaps_ltrb_px']=[float(points[:,0].min()-left),
                    float(points[:,1].min()-top),float(right-points[:,0].max()),
                    float(bottom-points[:,1].max())]
            rows.append(row)
    cv2.imwrite(str(output/'comparison.jpg'),np.vstack([np.hstack(panels[i:i+5]) for i in range(0,len(panels),5)]))
    (output/'reference.json').write_text(json.dumps(dict(authority='ADVISORY_ONLY',
        runtime_enabled=False,source=str(source('134637')),
        note='Groove intensity minimum, not proven inner hole boundary. No coordinate updates.',rows=rows),indent=2))
    print(output)


if __name__=='__main__':
    main()
