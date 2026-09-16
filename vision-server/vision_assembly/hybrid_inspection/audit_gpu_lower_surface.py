"""Offline lower-logo dark-line audit; never sets an inspection decision.

Uses green-logo orientation to compare archived surface crops. Image scores
are diagnostic, not physical crack labels or calibrated detector thresholds.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def measure(image):
    choices = []
    for k in range(4):
        a = np.ascontiguousarray(np.rot90(image, k))
        h, w = a.shape[:2]
        if h <= w:
            continue
        hsv = cv2.cvtColor(a, cv2.COLOR_BGR2HSV)
        green = cv2.inRange(hsv, (40, 65, 45), (95, 255, 255))
        green[:int(h*.2)] = 0
        green[int(h*.8):] = 0
        green[:, :int(w*.2)] = 0
        green[:, int(w*.8):] = 0
        ys, xs = np.where(green > 0)
        if len(ys) < 20:
            continue
        gray = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
        # White text should be immediately below the green logo, centrally.
        x0, x1 = int(w*.25), int(w*.75)
        y0, y1 = int(ys.max())+1, min(h, int(ys.max()+h*.16))
        if y1 <= y0:
            continue
        text = gray[y0:y1, x0:x1] > 135
        choices.append((int(text.sum()), a, int(ys.max())))
    if not choices:
        return {"available": False, "reason": "LOGO_NOT_LOCATED"}
    _, a, logo_bottom = max(choices, key=lambda c:c[0])
    h, w = a.shape[:2]
    y0, y1 = logo_bottom+int(h*.12), int(h*.84)
    x0, x1 = int(w*.3), int(w*.7)
    if y1-y0 < 15:
        return {"available": False, "reason": "LOWER_FACE_NOT_VISIBLE"}
    gray = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    region = gray[y0:y1, x0:x1]
    response = cv2.morphologyEx(region, cv2.MORPH_BLACKHAT,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (3, 17)))
    row = np.mean(response, axis=1)
    peak = int(np.argmax(row))
    return {"available": True, "roi_xyxy": [x0,y0,x1,y1],
            "dark_horizontal_response": float(row[peak]),
            "peak_row_fraction": float((y0+peak)/h),
            "region_gray_median": float(np.median(region)),
            "limitation": "Dark ridge can be a crack, print seam or shadow; no defect vote."}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--current', type=Path, required=True)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    paths = [('current_user_labelled_crack', args.current)]
    for split in ('train/good', 'test/good', 'test/crack'):
        paths.extend((split, f) for f in sorted((args.dataset/split).glob('*.png')))
    rows = []
    for split, path in paths:
        a = cv2.imread(str(path))
        if a is None:
            raise ValueError(f'Cannot decode {path}')
        rows.append(dict(split=split, path=str(path.resolve()),
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest(), **measure(a)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(rows=rows, runtime_changed=False,
        note='Different crop framing, printed instances and lighting are confounds. No training or threshold fitting.'), indent=2)+'\n')
    print(json.dumps([dict(split=s, scores=[r.get('dark_horizontal_response') for r in rows if r['split']==s])
                      for s in dict.fromkeys(r['split'] for r in rows)], indent=2))


if __name__ == '__main__':
    main()
