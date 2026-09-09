#!/usr/bin/env python3
"""Minimal four-corner GPU OBB labeler for the local dataset."""
import argparse
from pathlib import Path

import cv2
import numpy as np


def clockwise(points):
    points=np.asarray(points,np.float32)
    center=points.mean(axis=0)
    angle=np.arctan2(points[:,1]-center[1],points[:,0]-center[0])
    ordered=points[np.argsort(angle)]
    start=int(np.argmin(ordered[:,0]+ordered[:,1]))
    return np.roll(ordered,-start,axis=0)


def load_boxes(label_path, width, height):
    """Load existing normalized Ultralytics OBB labels for relabel editing."""
    if not label_path.is_file():
        return []
    boxes=[]
    for line in label_path.read_text(encoding='utf-8').splitlines():
        fields=line.split()
        if len(fields)!=9:
            continue
        try:
            values=np.asarray([float(value) for value in fields[1:]],np.float32)
        except ValueError:
            continue
        points=values.reshape(4,2)*np.array([width,height],np.float32)
        boxes.append(clockwise(points))
    return boxes


def main():
    parser=argparse.ArgumentParser()
    root=Path(__file__).parent/'dataset'
    parser.add_argument('--images',type=Path,default=root/'images/unlabeled')
    parser.add_argument('--labels',type=Path,default=root/'labels/all')
    parser.add_argument('--relabel',action='store_true',
                        help='include images that already have a non-empty label file')
    args=parser.parse_args();args.labels.mkdir(parents=True,exist_ok=True)
    images=sorted([*args.images.glob('*.jpg'),*args.images.glob('*.png')])
    if not args.relabel:
        images=[path for path in images
                if not (args.labels/f'{path.stem}.txt').is_file()
                or not (args.labels/f'{path.stem}.txt').read_text(encoding='utf-8').strip()]
    if not images:raise RuntimeError(f'No images in {args.images}')
    print('Left click 4 corners per GPU | ENTER add box | U undo | S save+next | P save same boxes to all remaining | Q quit')
    index=0
    while index<len(images):
        path=images[index];image=cv2.imread(str(path))
        if image is None:index+=1;continue
        height,width=image.shape[:2];points=[]
        label_path=args.labels/f'{path.stem}.txt'
        boxes=load_boxes(label_path,width,height) if args.relabel else []
        canvas=image.copy()
        def mouse(event,x,y,flags,param):
            if event==cv2.EVENT_LBUTTONDOWN and len(points)<4:points.append((x,y))
        cv2.namedWindow('GPU OBB Labeler',cv2.WINDOW_NORMAL)
        cv2.setMouseCallback('GPU OBB Labeler',mouse)
        while True:
            canvas=image.copy()
            for box in boxes:cv2.polylines(canvas,[np.int32(box)],True,(0,255,0),3)
            for point in points:cv2.circle(canvas,point,6,(0,0,255),-1)
            if len(points)>1:cv2.polylines(canvas,[np.int32(points)],False,(0,0,255),2)
            cv2.putText(canvas,f'{index+1}/{len(images)} {path.name} boxes={len(boxes)}',
                        (20,35),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,255,255),2)
            cv2.imshow('GPU OBB Labeler',canvas);key=cv2.waitKey(30)&0xff
            if key in (10,13) and len(points)==4:
                boxes.append(clockwise(points));points=[]
            elif key in (ord('u'),ord('U')):
                if points:points.pop()
                elif boxes:boxes.pop()
            elif key in (ord('s'),ord('S'),ord('p'),ord('P')):
                lines=[]
                for box in boxes:
                    normalized=box/np.array([width,height],np.float32)
                    lines.append('0 '+' '.join(f'{value:.8f}' for value in normalized.reshape(-1)))
                label_path.write_text('\n'.join(lines)+('\n' if lines else ''),encoding='utf-8')
                print(f'Saved {len(boxes)} GPU boxes: {label_path.name}')
                if key in (ord('p'),ord('P')):
                    for remaining in images[index+1:]:
                        (args.labels/f'{remaining.stem}.txt').write_text(
                            '\n'.join(lines)+('\n' if lines else ''),encoding='utf-8')
                    print(f'Propagated the same boxes to {len(images)-index-1} remaining images')
                    cv2.destroyAllWindows();return
                index+=1;break
            elif key in (ord('q'),ord('Q'),27):
                cv2.destroyAllWindows();return
    cv2.destroyAllWindows()


if __name__=='__main__':main()
