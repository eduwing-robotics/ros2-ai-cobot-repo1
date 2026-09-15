#!/usr/bin/env python3
"""Interactively replace one SMD OBB label across a fixed-pose close-view dataset."""
import argparse
from pathlib import Path
import cv2
import numpy as np

def ordered(points):
    pts=np.asarray(points,np.float32);center=pts.mean(0)
    pts=pts[np.argsort(np.arctan2(pts[:,1]-center[1],pts[:,0]-center[0]))]
    return np.roll(pts,-int(np.argmin(pts[:,0]+pts[:,1])),axis=0)

def parse_label(path,w,h):
    boxes=[]
    for row in path.read_text().splitlines():
        values=row.split();boxes.append(np.asarray(list(map(float,values[1:])),np.float32).reshape(4,2)*[w,h])
    return boxes

def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True);p.add_argument('--instance',type=int,default=9);p.add_argument('--all',action='store_true');a=p.parse_args()
    image_path=a.dataset/'median_reference.jpg';image=cv2.imread(str(image_path))
    if image is None:raise RuntimeError(f'cannot read {image_path}')
    labels=sorted((a.dataset/'labels/train').glob('*.txt'))
    if not labels:raise RuntimeError('no training labels')
    h,w=image.shape[:2];boxes=parse_label(labels[0],w,h)
    if not 1<=a.instance<=len(boxes):raise RuntimeError('instance out of range')
    clicks=[];window='Manual SMD OBB - click 4 corners, Enter next, R reset, Esc cancel'
    def mouse(event,x,y,flags,param):
        if event==cv2.EVENT_LBUTTONDOWN and len(clicks)<4:clicks.append((x,y))
    cv2.namedWindow(window,cv2.WINDOW_NORMAL);cv2.resizeWindow(window,min(w,1500),min(h,900));cv2.setMouseCallback(window,mouse)
    targets=list(range(1,len(boxes)+1)) if a.all else [a.instance]
    for current in targets:
     clicks.clear()
     while True:
        view=image.copy()
        for index,box in enumerate(boxes,1):
            color=(90,90,90) if index!=current else (0,0,255);cv2.polylines(view,[np.rint(box).astype(np.int32)],True,color,2,cv2.LINE_AA)
            center=np.rint(box.mean(0)).astype(int);cv2.putText(view,str(index),tuple(center),cv2.FONT_HERSHEY_SIMPLEX,.6,color,2,cv2.LINE_AA)
        for i,point in enumerate(clicks,1):
            cv2.circle(view,point,6,(0,255,255),-1);cv2.putText(view,str(i),(point[0]+8,point[1]-8),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,255),2)
        if len(clicks)>1:cv2.polylines(view,[np.asarray(clicks,np.int32)],len(clicks)==4,(0,255,255),2,cv2.LINE_AA)
        cv2.putText(view,f'Instance {current}/10: include both white ends',(20,35),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,255,255),2,cv2.LINE_AA)
        cv2.imshow(window,view);key=cv2.waitKey(30)&0xff
        if key in (27,ord('q')):cv2.destroyAllWindows();raise SystemExit('cancelled')
        if key in (ord('r'),ord('R')):clicks.clear()
        if key in (10,13) and len(clicks)==4:break
     boxes[current-1]=ordered(clicks)
    targets=sorted((a.dataset/'labels/train').glob('*.txt'))+sorted((a.dataset/'labels/val').glob('*.txt'))
    for path in targets:
        rows=path.read_text().splitlines()
        for current in (range(1,len(boxes)+1) if a.all else [a.instance]):
            normalized=boxes[current-1]/np.asarray([w,h],np.float32);rows[current-1]='0 '+' '.join(f'{v:.6f}' for v in normalized.reshape(-1))
        path.write_text('\n'.join(rows)+'\n')
    review=image.copy()
    for index,item in enumerate(boxes,1):
        color=(0,255,0) if (a.all or index==a.instance) else (120,120,120);cv2.polylines(review,[np.rint(item).astype(np.int32)],True,color,3 if (a.all or index==a.instance) else 1,cv2.LINE_AA)
        center=np.rint(item.mean(0)).astype(int);cv2.putText(review,str(index),tuple(center+[8,-8]),cv2.FONT_HERSHEY_SIMPLEX,.65,color,2)
    output=a.dataset/'manual_label_review.jpg';cv2.imwrite(str(output),review,[cv2.IMWRITE_JPEG_QUALITY,96]);cv2.destroyAllWindows();print(f'Updated {"all 10 instances" if a.all else f"instance {a.instance}"} in {len(targets)} labels');print(output)
if __name__=='__main__':main()
