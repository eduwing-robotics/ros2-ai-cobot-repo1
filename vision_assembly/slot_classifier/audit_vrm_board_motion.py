"""Compare invariant-board feature motion before/after registration.

Diagnostic only: tracked component motion is never used to warp an input.
"""
import json
import argparse
from pathlib import Path
import cv2
import numpy as np
from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper
from preprocessor_and_cropper import board_alignment_mask


def tracks(ref, cur, mask):
    a=cv2.cvtColor(ref,cv2.COLOR_BGR2GRAY)
    b=cv2.cvtColor(cur,cv2.COLOR_BGR2GRAY)
    p=cv2.goodFeaturesToTrack(a,250,.01,12,mask=mask,blockSize=7)
    if p is None:
        return np.empty((0,2)),np.empty((0,2))
    q,s,_=cv2.calcOpticalFlowPyrLK(a,b,p,None,winSize=(25,25),maxLevel=3)
    if q is None:
        return np.empty((0,2)),np.empty((0,2))
    back,t,_=cv2.calcOpticalFlowPyrLK(b,a,q,None,winSize=(25,25),maxLevel=3)
    if back is None:
        return np.empty((0,2)),np.empty((0,2))
    p,q,back=p.reshape(-1,2),q.reshape(-1,2),back.reshape(-1,2)
    valid=(s.ravel()>0)&(t.ravel()>0)&(np.linalg.norm(p-back,axis=1)<1.)
    valid &= np.linalg.norm(q-p,axis=1)<40
    x,y=np.rint(q[:,0]).astype(int),np.rint(q[:,1]).astype(int)
    inside=(x>=0)&(x<mask.shape[1])&(y>=0)&(y<mask.shape[0])
    safe=np.zeros(len(p),bool)
    safe[inside]=mask[y[inside],x[inside]]>0
    valid &= safe
    return p[valid],q[valid]


def summary(p,q):
    if len(p)<3:
        return dict(count=len(p),status='INSUFFICIENT_FIXED_FEATURES')
    delta=q-p
    return dict(count=len(p),median_px=np.median(delta,axis=0).tolist(),
                p90_magnitude_px=float(np.percentile(np.linalg.norm(delta,axis=1),90)))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'runtime/inspection/vrm_board_motion_181938')
    args=parser.parse_args()
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    out=args.output
    out.mkdir(exist_ok=False)
    images={}
    registered={}
    for stamp in ('181938','183451','184100'):
        image=cv2.imread(str(ROOT/f'runtime/inspection/s22_inspection_roi_20260905_{stamp}.png'))
        if image is None:
            raise ValueError(stamp)
        images[stamp]=image
        registered[stamp]=cropper.register(image)
        if registered[stamp].alignment_reason!='OK':
            raise ValueError('Registration uncertain')
    mask=board_alignment_mask(cropper.layout,cropper.reference.shape,cropper.board_size_mm,
                              cropper.config['coordinate_mapping'],2.5)
    mask=cv2.erode(mask,np.ones((7,7),np.uint8))
    slots=[s for s in cropper.fixed_slots(registered['181938'].image_bgr) if s.component_type=='VRM']
    rows=[]
    for stamp in ('183451','184100'):
        for stage in ('roi_before_alignment','registered'):
            ref=images['181938'] if stage=='roi_before_alignment' else registered['181938'].image_bgr
            cur=images[stamp] if stage=='roi_before_alignment' else registered[stamp].image_bgr
            p,q=tracks(ref,cur,mask)
            local={}
            for slot in slots:
                center=np.array(slot.geometry[:2])
                near=np.linalg.norm(p-center,axis=1)<250
                local_mask=np.zeros(mask.shape,np.uint8)
                cv2.circle(local_mask,tuple(np.rint(center).astype(int)),250,255,-1)
                local_mask=cv2.bitwise_and(local_mask,mask)
                lp,lq=tracks(ref,cur,local_mask)
                local[slot.slot_id]=dict(summary(lp,lq),
                    global_sample_subset=summary(p[near],q[near]),
                    allowed_mask_pixels=int(np.count_nonzero(local_mask)))
            component={}
            if stage=='registered':
                for slot in slots:
                    x,y,w,h=slot.geometry
                    interior=np.zeros(mask.shape,np.uint8)
                    cv2.rectangle(interior,(round(x-w*.3),round(y-h*.3)),
                                  (round(x+w*.3),round(y+h*.3)),255,-1)
                    ip,iq=tracks(ref,cur,interior)
                    component[slot.slot_id]=summary(ip,iq)
            rows.append(dict(stamp=stamp,stage=stage,global_fixed=summary(p,q),local_fixed=local,
                             component_surface_diagnostic=component))
            panel=cur.copy()
            for start,end in zip(p,q):
                cv2.circle(panel,tuple(np.rint(start).astype(int)),3,(0,255,255),1)
                cv2.arrowedLine(panel,tuple(np.rint(start).astype(int)),tuple(np.rint(end).astype(int)),(0,255,0),1)
            cv2.imwrite(str(out/f'{stamp}_{stage}.png'),panel)
    report=dict(rows=rows,alignment={k:dict(score=v.alignment_score,warp=v.alignment_warp.tolist())
                for k,v in registered.items()},runtime_enabled=False,authority='ADVISORY_ONLY',
                note='LK diagnostics: fixed feature mask excludes all component areas. '
                     'Local tracking does not prove camera pose or physical component movement. '
                     'No correction is applied to inspection inputs.',
                robot_command_sent=False,conveyor_command_sent=False)
    (out/'audit.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
