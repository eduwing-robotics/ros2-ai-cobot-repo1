"""Render manual annotations without approving them or training."""
import json
from pathlib import Path
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def main():
    root=ROOT/'vision_assembly/segmentation/vrm_boundary_adaptation_v1'
    draft=json.loads((root/'manual_polygon_drafts.json').read_text())
    panels=[]
    for stem,points in draft['polygons'].items():
        image=cv2.imread(str(root/'images'/f'{stem}.png'))
        poly=np.float32(points)
        if image is None or np.any(poly<0) or np.any(poly[:,0]>=image.shape[1]) or np.any(poly[:,1]>=image.shape[0]):
            raise ValueError('Invalid annotation coordinates')
        overlay=image.copy()
        cv2.polylines(overlay,[np.int32(poly)],True,(0,255,0),1)
        pair=np.hstack([cv2.resize(image,(378,482)),cv2.resize(overlay,(378,482))])
        pair=cv2.copyMakeBorder(pair,30,0,0,0,cv2.BORDER_CONSTANT)
        cv2.putText(pair,stem+' MANUAL DRAFT',(4,20),0,.44,(255,255,255),1)
        panels.append(pair)
    cv2.imwrite(str(root/'manual_preview.jpg'),np.vstack(panels))


if __name__=='__main__':
    main()
