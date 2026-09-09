"""Rank competing empty-board edge peaks; never infer a certified inner wall."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np


def peaks(profile, expected, origin, radius=15):
    profile=np.asarray(profile,dtype=float)
    chosen=[]
    for i in sorted(range(max(0,int(expected)-radius),min(len(profile),int(expected)+radius+1)),
                    key=lambda i:float(profile[i]),reverse=True):
        if np.isfinite(profile[i]) and profile[i]>0 and all(abs(i-j)>=4 for j in chosen):
            chosen.append(i)
        if len(chosen)==3: break
    return [dict(coordinate_px=i+.5+origin,strength=float(profile[i]),
                 delta_from_CAD_px=float(i+.5-expected)) for i in chosen]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison',type=Path,required=True)
    parser.add_argument('--trial',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    provenance=json.loads((args.comparison/'provenance.json').read_text())
    mapping=json.loads((args.trial/'trial.json').read_text())['mapping']
    import hashlib
    if provenance['trial_sha256']!=hashlib.sha256((args.trial/'trial.json').read_bytes()).hexdigest():
        raise ValueError('Comparison geometry mismatch')
    rows=[]
    for s in mapping:
        if len(s['polygon_board_mm'])!=4:
            rows.append(dict(slot_id=s['slot_id'],reason='NONRECTANGULAR_SOCKET_SKIPPED'))
            continue
        polygon=(.5-np.array(s['polygon_board_mm'])/[139.,110.])*[1600,1266]
        lo=np.maximum(np.floor(polygon.min(axis=0)-20).astype(int),[0,0])
        hi=np.minimum(np.ceil(polygon.max(axis=0)+20).astype(int),[1600,1266])
        panel=cv2.imread(str(args.comparison/(s['slot_id']+'.png')))
        w,h=hi-lo
        if panel is None or panel.shape[:2]!=(h,w*4): raise ValueError('Invalid comparison dimensions')
        # ONLY the first (unannotated empty) panel; never occupied-board pixels.
        gray=cv2.cvtColor(panel[:,:w],cv2.COLOR_BGR2GRAY).astype(float)
        a,b=polygon.min(axis=0)-lo,polygon.max(axis=0)-lo
        x1,x2=int(a[0]+.3*(b[0]-a[0])),int(a[0]+.7*(b[0]-a[0]))
        y1,y2=int(a[1]+.3*(b[1]-a[1])),int(a[1]+.7*(b[1]-a[1]))
        xp=np.median(np.abs(np.diff(gray[y1:y2],axis=1)),axis=0)
        yp=np.median(np.abs(np.diff(gray[:,x1:x2],axis=0)),axis=1)
        sides={side:peaks(profile,float(expected),int(origin))
               for side,profile,expected,origin in [('left',xp,a[0],lo[0]),('right',xp,b[0],lo[0]),
                                                   ('top',yp,a[1],lo[1]),('bottom',yp,b[1],lo[1])]}
        rows.append(dict(slot_id=s['slot_id'],edges=sides))
    summary={}
    for side in ('left','right','top','bottom'):
        values=[r['edges'][side][0]['delta_from_CAD_px'] for r in rows if r.get('edges',{}).get(side)]
        summary[side]=dict(count=len(values),median_px=float(np.median(values)),
                           min_px=min(values),max_px=max(values)) if values else dict(count=0)
    data=dict(rows=rows,strongest_peak_deltas=summary,source_provenance=provenance,
              status='UNKNOWN',runtime_changed=False,
              limitation='Exploratory +/-15px search, competing peaks retained. Strongest gradient can be rim/shadow/print texture. Not wall calibration or constant-offset evidence.')
    with args.output.open('x') as stream: json.dump(data,stream,indent=2,allow_nan=False)
    print(json.dumps(summary))


if __name__=='__main__': main()
