"""Explicit operator wall annotation on an archived EMPTY slot; never deploys.

LMB: polygon corners in order; RMB/U: undo; R: reset; Enter: archive;
Esc: cancel. Original source, crop origin and geometry hashes are retained.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
import cv2
import numpy as np


def board_points(points, origin, scale):
    p=np.asarray(points,dtype=float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<3 or not np.isfinite(p).all():
        raise ValueError('At least three finite corners required')
    if not np.isfinite(scale) or scale<=0: raise ValueError('Invalid scale')
    board=p/scale+np.asarray(origin,dtype=float)
    contour=board.astype(np.float32)
    if not cv2.isContourConvex(contour) or cv2.contourArea(contour)<=1:
        raise ValueError('Polygon must be convex and corners ordered')
    return board.tolist()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--comparison',type=Path,required=True)
    ap.add_argument('--trial',type=Path,required=True)
    ap.add_argument('--slot',required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--check-only',action='store_true')
    args=ap.parse_args()
    prov=json.loads((args.comparison/'provenance.json').read_text())
    trial_bytes=(args.trial/'trial.json').read_bytes()
    if hashlib.sha256(trial_bytes).hexdigest()!=prov['trial_sha256']: raise ValueError('Geometry hash mismatch')
    for source in prov['sources']:
        if hashlib.sha256(Path(source['path']).read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('Source hash mismatch')
    slot=next(s for s in json.loads(trial_bytes)['mapping'] if s['slot_id']==args.slot)
    polygon=(.5-np.array(slot['polygon_board_mm'])/[139,110])*[1600,1266]
    origin=np.maximum(np.floor(polygon.min(axis=0)-20).astype(int),[0,0])
    end=np.minimum(np.ceil(polygon.max(axis=0)+20).astype(int),[1600,1266])
    w,h=end-origin
    panel=cv2.imread(str(args.comparison/(args.slot+'.png')))
    if panel is None or panel.shape[:2]!=(h,w*4): raise ValueError('Invalid comparison')
    empty=panel[:,:w].copy()
    if args.check_only:
        print(json.dumps(dict(slot=args.slot,origin=origin.tolist(),size=[int(w),int(h)],source=prov['sources'][0])))
        return
    scale=min(5.,1000/h,1300/w)
    view=cv2.resize(empty,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
    points=[]
    title='EMPTY SOCKET WALL - '+args.slot
    message='Select inner-wall corners clockwise. ESC cancels without saving.'
    def mouse(event,x,y,flags,param):
        if event==cv2.EVENT_LBUTTONDOWN and y>=100 and y<100+view.shape[0] and 0<=x<view.shape[1]:
            points.append((x,y-100))
        elif event==cv2.EVENT_RBUTTONDOWN and points: points.pop()
    cv2.namedWindow(title,cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(title,mouse)
    try:
        while True:
            canvas=cv2.copyMakeBorder(view,100,0,0,max(0,800-view.shape[1]),cv2.BORDER_CONSTANT)
            for i,line in enumerate([args.slot+' | ARCHIVED EMPTY | NO RUNTIME CHANGE',
                'LMB corners | RMB/U undo | R reset | ENTER save | ESC cancel',message]):
                cv2.putText(canvas,line,(8,22+27*i),0,.48,(240,240,240),1)
            for p in points: cv2.circle(canvas,(p[0],p[1]+100),3,(0,255,255),1)
            if len(points)>1:
                cv2.polylines(canvas,[np.array(points,dtype=np.int32)+[0,100]],len(points)>=3,(0,255,255),1)
            cv2.imshow(title,canvas)
            key=cv2.waitKey(30)&255
            if key==27 or cv2.getWindowProperty(title,cv2.WND_PROP_VISIBLE)<1: break
            if key in (ord('u'),8) and points: points.pop()
            if key==ord('r'): points.clear()
            if key in (10,13):
                try: selected=board_points(points,origin,scale)
                except ValueError as e:
                    message=str(e); continue
                args.output.mkdir(parents=True,exist_ok=True)
                destination=args.output/(args.slot+'_'+str(time.time_ns())+'.json')
                record=dict(slot_id=args.slot,polygon_registered_board_px=selected,
                    crop_origin_px=origin.tolist(),display_scale=scale,provenance=prov,
                    annotation_method='OPERATOR_CLICKED_EMPTY_INNER_WALL',
                    status='UNVALIDATED_WALL_ANNOTATION',runtime_enabled=False,
                    limitation='Human image-edge identification only; transfer, metric/height accuracy and normal/defect controls still required.')
                with destination.open('x') as f: json.dump(record,f,indent=2,allow_nan=False)
                print(destination,flush=True)
                break
    finally: cv2.destroyAllWindows()


if __name__=='__main__': main()
