"""Reuse reviewed S22 polygons in fixed board-slot crops; no per-part alignment."""
import argparse
import hashlib
import itertools
import json
import random
import sys
from collections import Counter
from pathlib import Path
import cv2
import numpy as np
from common import load_yolo_segments, save_yolo_segments

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'vision_assembly/hybrid_inspection'))
from preprocessor_and_cropper import FixedSlotCropper


def polygon_transform(points,source_h,alignment_warp):
    """ECC is an inverse sampling warp: annotations need its inverse."""
    affine=np.eye(3)
    affine[:2]=alignment_warp
    transform=np.linalg.inv(affine)@source_h
    return cv2.perspectiveTransform(np.asarray(points,np.float32)[None],transform)[0]


def split_scenes(names):
    names=sorted(set(names))
    if len(names)<3:
        raise ValueError('At least3 scene groups required')
    random.Random(20260905).shuffle(names)
    return {name:('test' if i==0 else 'val' if i==1 else 'train') for i,name in enumerate(names)}


def clip_polygon(points,width,height):
    points=[np.asarray(p,dtype=float) for p in points]
    for axis,bound,lower in [(0,0,True),(1,0,True),(0,width-1,False),(1,height-1,False)]:
        if not points:
            break
        result=[]
        previous=points[-1]
        inside=lambda p: p[axis]>=bound if lower else p[axis]<=bound
        for current in points:
            if inside(current)!=inside(previous):
                ratio=(bound-previous[axis])/(current[axis]-previous[axis])
                result.append(previous+ratio*(current-previous))
            if inside(current):
                result.append(current)
            previous=current
        points=result
    return np.asarray(points,np.float32).reshape(-1,2)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    out=args.output.resolve()
    if out.exists():
        raise ValueError('Refusing to replace existing dataset')
    source=ROOT/'vision_assembly/segmentation/s22_source'
    samples=[]
    for r in sorted((source/'reviews').glob('*.json')):
        if json.loads(r.read_text()).get('status')!='COMPLETE':
            continue
        meta=json.loads((source/'metadata'/r.name).read_text())
        if meta.get('board_state')!='normal':
            raise ValueError('This experiment requires reviewed normal boards')
        samples.append((r.stem,meta))
    splits=split_scenes([m['scene'] for _,m in samples])
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    prepared=[]
    hashes={}
    for stem,meta in samples:
        images=list((source/'images').glob(stem+'.*'))
        if len(images)!=1:
            raise ValueError('Nonunique source')
        path=images[0]
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=meta['sha256']:
            raise ValueError('Source changed since archive')
        split=splits[meta['scene']]
        if digest in hashes:
            raise ValueError('Duplicate image; review grouping before splitting')
        hashes[digest]=split
        image=cv2.imread(str(path))
        if image is None:
            raise ValueError('Unreadable image')
        ih,iw=image.shape[:2]
        polys=[poly for cls,poly in load_yolo_segments(source/'labels'/f'{stem}.txt',iw,ih) if cls==3]
        if len(polys)!=5:
            raise ValueError('Expected exactly5 reviewed VRM polygons')
        board=cropper.register(image)
        if board.alignment_reason!='OK' or board.alignment_score<float(cropper.config['global_alignment']['minimum_score']):
            raise ValueError(f'Uncertain registration: {stem}')
        mapped=[polygon_transform(p,board.source_homography,board.alignment_warp) for p in polys]
        slots=[s for s in cropper.fixed_slots(board.image_bgr) if s.component_type=='VRM']
        if len(slots)!=5:
            raise ValueError('Expected5 fixed VRM slots')
        centers=[p.mean(axis=0) for p in mapped]
        match=min(itertools.permutations(range(5)),key=lambda perm:sum(
            np.linalg.norm(centers[j]-np.array(s.geometry[:2]))**2 for s,j in zip(slots,perm)))
        for slot,j in zip(slots,match):
            cx,cy,w,h=slot.geometry
            if abs(centers[j][0]-cx)>w*.6 or abs(centers[j][1]-cy)>h*.6:
                raise ValueError('Implausible polygon-slot assignment')
            cw,ch=round(w*1.5),round(h*1.5)
            x0,y0=round(cx-cw/2),round(cy-ch/2)
            if x0<0 or y0<0 or x0+cw>board.image_bgr.shape[1] or y0+ch>board.image_bgr.shape[0]:
                raise ValueError('Fixed crop outside board')
            crop=board.image_bgr[y0:y0+ch,x0:x0+cw].copy()
            poly=mapped[j]-[x0,y0]
            if np.any(poly<0) or np.any(poly[:,0]>=cw) or np.any(poly[:,1]>=ch):
                raise ValueError('Polygon clipped by fixed crop')
            visible=[poly]
            for k,other in enumerate(mapped):
                if k==j:
                    continue
                clipped=clip_polygon(other-[x0,y0],cw,ch)
                if len(clipped)>=3 and abs(cv2.contourArea(clipped))>=1:
                    visible.append(clipped)
            prepared.append((crop,visible,dict(stem=f'{stem}__{slot.slot_id}',scene=meta['scene'],
                split=split,source_image=str(path),source_sha256=digest,slot=slot.slot_id,
                visible_instances=len(visible),primary_instance_index=0,
                source_label_sha256=hashlib.sha256((source/'labels'/f'{stem}.txt').read_bytes()).hexdigest(),
                alignment_score=board.alignment_score,source_homography=board.source_homography.tolist(),
                alignment_warp=board.alignment_warp.tolist(),crop_origin_px=[x0,y0],crop_size_px=[cw,ch])))
    # All sources/mappings checked before any dataset is written.
    out.mkdir(parents=True)
    panels=[]
    for crop,polys,row in prepared:
        for kind in ('images','labels'):
            (out/kind/row['split']).mkdir(parents=True,exist_ok=True)
        if not cv2.imwrite(str(out/'images'/row['split']/(row['stem']+'.png')),crop):
            raise IOError('Image write failed')
        save_yolo_segments(out/'labels'/row['split']/(row['stem']+'.txt'),[(0,poly) for poly in polys],crop.shape[1],crop.shape[0])
        if len(panels)<10:
            overlay=crop.copy()
            cv2.polylines(overlay,[np.int32(poly) for poly in polys],True,(0,255,0),1)
            panel=np.hstack([cv2.resize(crop,(140,180)),cv2.resize(overlay,(140,180))])
            panels.append(panel)
    manifest=dict(authority='ADVISORY_ONLY',runtime_enabled=False,training_performed=False,
        scene_splits=splits,counts=dict(Counter(r['split'] for _,_,r in prepared)),
        total_visible_instances=sum(r['visible_instances'] for _,_,r in prepared),
        rows=[r for _,_,r in prepared],crop_policy='fixed geometry1.5x integer crop after board-only registration; original color; no per-part recenter/rotation',
        limitation='Normal-only masks. Scene IDs are existing metadata; physical part identities may recur. No evidence of empty/defect performance. Test split must not select epochs or thresholds.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (out/'vrm.yaml').write_text(f'path: {json.dumps(str(out))}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: vrm\n')
    cv2.imwrite(str(out/'mapping_preview.jpg'),np.vstack([np.hstack(panels[i:i+5]) for i in (0,5)]))
    print(json.dumps(dict(scene_splits=splits,counts=manifest['counts']),indent=2))


if __name__=='__main__':
    main()
