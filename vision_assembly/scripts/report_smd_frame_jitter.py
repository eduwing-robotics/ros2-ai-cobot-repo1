#!/usr/bin/env python3
"""Render diagnostic paired crops; does not alter source frames or targets."""
import argparse,json
from pathlib import Path
import cv2
import numpy as np

p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
d=json.loads((a.directory/'analysis.json').read_text())
cfg=json.loads((Path(__file__).resolve().parents[1]/'config/smd_section_view.json').read_text())
rows={(r['index'],r['kind']):r for r in d['results'] if 'center' in r}
w,h=cfg['canonical_size'];cx,cy=np.rint(d['roi_center']).astype(int)
dst=np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
def rectified(index,kind):
    suffix='raw.png' if kind=='raw' else 'jpeg.jpg'
    im=cv2.imread(str(a.directory/f'{index:03d}_{suffix}'))
    scale=np.float32([im.shape[1],im.shape[0]])/cfg['source_image_size']
    H=cv2.getPerspectiveTransform(np.float32(cfg['section_polygon_pixel'])*scale.astype(np.float32),dst)
    return cv2.warpPerspective(im,H,(w,h),flags=cv2.INTER_CUBIC)
indices=[i for i in (0,5,6,36) if i < len(d['capture'])]
sheet=np.full((len(indices)*210,4*200,3),240,np.uint8)
for row,index in enumerate(indices):
    for k,kind in enumerate(('raw','jpeg')):
        image=rectified(index,kind);crop=image[cy-40:cy+40,cx-40:cx+40]
        for overlay in (False,True):
            panel=cv2.resize(crop,(160,160),interpolation=cv2.INTER_NEAREST)
            if overlay:
                box=(np.array(rows[index,kind]['box'])-[cx-40,cy-40])*2
                cv2.polylines(panel,[np.rint(box).astype(np.int32)],True,(0,0,255),1)
            x=(k*2+int(overlay))*200;y=row*210
            sheet[y+38:y+198,x+20:x+180]=panel
            label=f'{index:03d} {kind}'+(' OBB' if overlay else '')
            cv2.putText(sheet,label,(x+8,y+25),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,0),1)
cv2.imwrite(str(a.directory/'paired_crops.jpg'),sheet,[cv2.IMWRITE_JPEG_QUALITY,85])
# Track unchanged physical texture independently using normalized template matching.
ref=rectified(0,'raw');gray=cv2.cvtColor(ref,cv2.COLOR_BGR2GRAY)
template=gray[cy-32:cy+32,cx-32:cx+32]
metrics=[]
for index in range(len(d['capture'])):
    image=rectified(index,'raw');g=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    search=g[cy-40:cy+40,cx-40:cx+40]
    scores=cv2.matchTemplate(search,template,cv2.TM_CCOEFF_NORMED)
    _,score,_,loc=cv2.minMaxLoc(scores)
    metrics.append(dict(index=index,shift_px=[loc[0]-8,loc[1]-8],score=score))
summary=dict(template_tracking=metrics,
             shift_span_px=np.ptp([m['shift_px'] for m in metrics],axis=0).tolist(),
             min_correlation=min(m['score'] for m in metrics))
(a.directory/'texture_tracking.json').write_text(json.dumps(summary,indent=2))
print({k:v for k,v in summary.items() if k!='template_tracking'})
