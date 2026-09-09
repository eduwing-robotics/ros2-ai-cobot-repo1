"""Signed dark-band pairs from empty references; diagnostic, never runtime."""
import json
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def dark_pairs(profile, low, high):
    profile = np.asarray(profile, dtype=np.float32)
    gradient = np.diff(profile)
    pairs = []
    for a in range(low, high-3):
        for b in range(a+3, min(a+17, high)):
            falling, rising = -float(gradient[a]), float(gradient[b])
            if min(falling, rising) < 1:
                continue
            depth = min(float(profile[max(0,a-2):a+1].mean()),
                        float(profile[b+1:b+4].mean())) - float(profile[a+1:b+1].mean())
            if depth <= 1:
                continue
            pairs.append(dict(outer_low=a+.5, outer_high=b+.5,
                              strength=min(falling,rising),depth=depth,
                              score=min(falling,rising)*depth))
    pairs.sort(key=lambda p:p['score'],reverse=True)
    chosen=[]
    for pair in pairs:
        if all(abs(pair['outer_low']-q['outer_low'])+abs(pair['outer_high']-q['outer_high'])>=5 for q in chosen):
            chosen.append(pair)
        if len(chosen)==3:
            break
    return chosen


def main():
    base=ROOT/'runtime/inspection'
    out=base/'smd01_wall_pairs_20260907'
    out.mkdir(exist_ok=False)
    rows,tiles=[],[]
    for path in sorted((base/'smd01_empty_reference_audit_20260907').glob('*_crop.png')):
        im=cv2.imread(str(path)); gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
        profiles={'top':(np.median(gray[:,75:125],axis=1),30,65),
                  'bottom':(np.median(gray[:,75:125],axis=1),80,120),
                  'left':(np.median(gray[55:80,:],axis=0),40,80),
                  'right':(np.median(gray[55:80,:],axis=0),125,160)}
        candidates={s:dark_pairs(*args) for s,args in profiles.items()}
        overlay=im.copy()
        inner={}
        for side,pairs in candidates.items():
            if not pairs: continue
            p=pairs[0]
            # Geometric interior-facing edge of a dark band; not proof of wall.
            inner[side]=p['outer_high'] if side in ('left','top') else p['outer_low']
            for coord,color in [(p['outer_low'],(255,200,0)),(p['outer_high'],(0,255,255))]:
                c=round(coord)
                if side in ('left','right'): cv2.line(overlay,(c,50),(c,85),color,1)
                else: cv2.line(overlay,(70,c),(130,c),color,1)
        panel=cv2.resize(np.hstack([im,overlay]),None,fx=3,fy=3,interpolation=cv2.INTER_NEAREST)
        tile=cv2.copyMakeBorder(panel,35,0,0,0,cv2.BORDER_CONSTANT,value=(25,25,25))
        cv2.putText(tile,f'{path.stem} | DARK-BAND PAIRS: DIAGNOSTIC, NOT CERTIFIED WALL',
                    (8,24),cv2.FONT_HERSHEY_SIMPLEX,.5,(230,230,230),1,cv2.LINE_AA)
        tiles.append(tile);rows.append(dict(source=str(path),candidates=candidates,interior_facing_candidate=inner))
    spread={}
    for side in ('left','right','top','bottom'):
        values=[r['interior_facing_candidate'][side] for r in rows if side in r['interior_facing_candidate']]
        spread[side]=dict(count=len(values),values_px=values,spread_px=float(np.ptp(values)) if values else None)
    payload=dict(rows=rows,spread=spread,status='UNKNOWN_DIAGNOSTIC_ONLY',
                 limitation='Signed profiles pair dark-band edges but shadows/print grooves can also be dark bands. Search windows and widths are diagnostic assumptions. No physical clearance, local alignment, or runtime change.')
    (out/'audit.json').write_text(json.dumps(payload,indent=2))
    cv2.imwrite(str(out/'comparison.png'),np.vstack(tiles))
    print(json.dumps(spread,indent=2))


if __name__=='__main__':main()
