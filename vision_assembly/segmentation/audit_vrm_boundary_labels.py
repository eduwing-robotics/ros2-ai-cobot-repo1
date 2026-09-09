"""Read-only source label inventory and preview. Does not build/train a dataset."""
import json
from collections import Counter
from pathlib import Path
import cv2
import numpy as np
from common import load_yolo_segments

ROOT=Path(__file__).resolve().parents[2]


def main():
    source=ROOT/'vision_assembly/segmentation/s22_source'
    rows,panels,seen=[],[],set()
    for review_path in sorted((source/'reviews').glob('*.json')):
        if json.loads(review_path.read_text()).get('status')!='COMPLETE':
            continue
        stem=review_path.stem
        meta=json.loads((source/'metadata'/review_path.name).read_text())
        images=list((source/'images').glob(stem+'.*'))
        if len(images)!=1:
            raise ValueError('Nonunique source image')
        image=cv2.imread(str(images[0]))
        if image is None:
            raise ValueError('Unreadable image')
        h,w=image.shape[:2]
        polys=[p for c,p in load_yolo_segments(source/'labels'/f'{stem}.txt',w,h) if c==3]
        scene=meta.get('scene',stem)
        rows.append(dict(stem=stem,scene=scene,board_state=meta.get('board_state'),vrm_polygons=len(polys)))
        if scene in seen or len(seen)>=3:
            continue
        seen.add(scene)
        for i,poly in enumerate(polys):
            x,y,bw,bh=cv2.boundingRect(poly)
            margin=round(max(bw,bh)*.15)
            x0,y0=max(0,x-margin),max(0,y-margin)
            crop=image[y0:min(h,y+bh+margin),x0:min(w,x+bw+margin)].copy()
            overlay=crop.copy()
            cv2.polylines(overlay,[np.int32(poly-[x0,y0])],True,(0,255,0),1)
            panel=np.hstack([cv2.resize(crop,(140,180)),cv2.resize(overlay,(140,180))])
            panel=cv2.copyMakeBorder(panel,25,0,0,0,cv2.BORDER_CONSTANT)
            cv2.putText(panel,f'scene sample{len(seen)} polygon{i+1}',(3,17),0,.4,(255,255,255),1)
            panels.append(panel)
    output=ROOT/'runtime/inspection/vrm_boundary_label_inventory'
    output.mkdir(exist_ok=False)
    report=dict(rows=rows,reviewed_images=len(rows),scene_count=len({r['scene'] for r in rows}),
        states=dict(Counter(r['board_state'] for r in rows)),vrm_polygons=sum(r['vrm_polygons'] for r in rows),
        training_performed=False,source_labels_changed=False,
        note='COMPLETE is existing review metadata, not a new contour accuracy certification. All current sources are normal boards; no reviewed empty/rotated VRM masks in this source collection.')
    (output/'inventory.json').write_text(json.dumps(report,indent=2))
    cv2.imwrite(str(output/'preview.jpg'),np.vstack([np.hstack(panels[i:i+5]) for i in range(0,len(panels),5)]))
    print(report['reviewed_images'],report['scene_count'],report['vrm_polygons'],report['states'])


if __name__=='__main__':
    main()
