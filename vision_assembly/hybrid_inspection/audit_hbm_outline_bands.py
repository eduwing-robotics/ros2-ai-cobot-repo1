"""Offline original-frame side-band probe. Never alters pose or live decisions."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def outline_bands(shape, polygon, radius=6):
    p = np.asarray(polygon, dtype=float)
    h, w = shape[:2]
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
        raise ValueError("Invalid polygon")
    if (p < 0).any() or (p[:,0] >= w).any() or (p[:,1] >= h).any():
        raise ValueError("Clipped outline")
    if radius <= 0 or radius > 16:
        raise ValueError("Invalid probe radius")
    mask = np.zeros((h,w), np.uint8)
    cv2.fillPoly(mask, [np.rint(p).astype(np.int32)], 1)
    ys = np.flatnonzero(mask.any(axis=1))
    if len(ys) < 20:
        raise ValueError("Too little outline support")
    # Avoid rounded tips and lower-left polarity dot; diagnostic coverage only.
    y0,y1=int(ys[0]+.08*len(ys)),int(ys[0]+.80*len(ys))
    bands = {s:np.zeros_like(mask) for s in ("left","right")}
    for y in range(y0,y1):
        xs=np.flatnonzero(mask[y])
        if len(xs) < 2: continue
        for side,x in (("left",int(xs[0])),("right",int(xs[-1]))):
            if x-radius < 0 or x+radius >= w: raise ValueError("Clipped band")
            bands[side][y,x-radius:x+radius+1]=1
    return bands


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",action="append",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    results=[]
    for run in args.run:
        paths=[p for p in (run/"yolo_auxiliary").glob("*.json") if not p.name.endswith("_latest.json")]
        if len(paths)!=1: raise ValueError("Ambiguous segmentation")
        data=json.loads(paths[0].read_text())
        source=Path(data["input_image"])
        if hashlib.sha256(source.read_bytes()).hexdigest()!=data["input_sha256"]:
            raise ValueError("Input hash mismatch")
        image=cv2.imread(str(source))
        if image is None: raise ValueError("Unreadable image")
        lab=cv2.cvtColor(image,cv2.COLOR_BGR2LAB)[:,:,0]
        sat=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)[:,:,1]
        white=(lab>=130)&(sat<=105)
        for d in data["detections"]:
            if not d["slot_id"].startswith("hbm_"):continue
            e=d["evidence"]
            row={"run":str(run),"slot_id":d["slot_id"],"source_sha256":data["input_sha256"],
                 "confidence":d["confidence"],"status":"UNVERIFIED"}
            try:
                if not e.get("present"):raise ValueError("No outline")
                bands=outline_bands(image.shape,e["polygon_px"])
                row["bands"]={s:{"white_pixels":int((white & m.astype(bool)).sum()),
                    "rows_with_two_white_pixels":int(((white & m.astype(bool)).sum(axis=1)>=2).sum()),
                    "sampled_rows":int(m.any(axis=1).sum())} for s,m in bands.items()}
            except (ValueError,KeyError) as exc:row.update(status="UNAVAILABLE",reason=str(exc))
            results.append(row)
    with args.output.open("x") as f:
        json.dump({"authority":"OFFLINE_ONLY","runtime_changed":False,
                   "limitation":"Unverified segmentation boundary; brighter band is not proof of intact pins. No pose/direction normalization or PASS/FAIL.",
                   "rows":results},f,indent=2)
    print(args.output)


if __name__=="__main__":main()
