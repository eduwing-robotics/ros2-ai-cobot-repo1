"""Offline counterfactuals only; never used by the inspection runtime."""
import json
import os
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'vision_assembly/inspection'))
from predict_component_patchcore import _checkpoint, _predict_outputs


def metrics(im):
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    mask = (gray > 160).astype(np.uint8)
    n, labels, stats, centers = cv2.connectedComponentsWithStats(mask)
    idx = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    selected = labels == idx
    return dict(white_center=centers[idx].tolist(), white_area=int(selected.sum()),
                white_bgr=np.median(im[selected], axis=0).tolist(),
                laplacian_variance=float(cv2.Laplacian(gray,cv2.CV_64F).var()),
                mean_bgr=im.mean(axis=(0,1)).tolist())


def main():
    os.environ.setdefault('HF_HUB_OFFLINE','1')
    out = ROOT/'runtime/inspection/patchcore/inductor_capture_drift_20260906'
    crops = out/'counterfactuals'
    crops.mkdir(parents=True,exist_ok=True)
    sources = {
      'normal': 'hybrid_fixed_slot/20260906_183337_961766',
      'earlier': 'hybrid_fixed_slot/20260906_184959_868834',
      'current': 'hybrid_inductor_candidate_validation/20260906_194334_346601'}
    images = {k:cv2.imread(str(ROOT/'runtime/inspection'/v/'patchcore_crops/inductor/inductor_01.png')) for k,v in sources.items()}
    measured = {k:metrics(im) for k,im in images.items()}
    old, new = images['normal'], images['current']
    gain = np.asarray(measured['normal']['white_bgr'])/np.maximum(measured['current']['white_bgr'],1)
    shift = np.asarray(measured['normal']['white_center'])-measured['current']['white_center']
    color = np.clip(new.astype(np.float32)*gain,0,255).astype(np.uint8)
    matrix = np.asarray([[1,0,shift[0]],[0,1,shift[1]]],np.float32)
    variants = dict(images)
    variants['diagnostic_color_only'] = color
    variants['diagnostic_shift_only'] = cv2.warpAffine(new,matrix,(new.shape[1],new.shape[0]),borderMode=cv2.BORDER_REFLECT)
    variants['diagnostic_color_and_shift'] = cv2.warpAffine(color,matrix,(new.shape[1],new.shape[0]),borderMode=cv2.BORDER_REFLECT)
    tiles=[]
    for name,im in variants.items():
        cv2.imwrite(str(crops/(name+'.png')),im)
        tile=cv2.copyMakeBorder(cv2.resize(im,(336,336)),32,0,0,0,cv2.BORDER_CONSTANT,value=(25,25,25))
        cv2.putText(tile,name,(6,22),cv2.FONT_HERSHEY_SIMPLEX,.45,(255,255,255),1,cv2.LINE_AA)
        tiles.append(tile)
    cv2.imwrite(str(out/'diagnostic_comparison.jpg'),np.vstack([np.hstack(tiles[:3]),np.hstack(tiles[3:])]))
    rows={}
    for label,root in [('active',ROOT/'runtime/inspection/patchcore/pcb_components_strict_v4'),
                       ('candidate',ROOT/'runtime/inspection/patchcore/inductor_appearance_candidate_20260906/models')]:
        pred=_predict_outputs('inductor',crops,_checkpoint(root,'inductor'),out/label)
        rows[label]={k:float(v['score']) for k,v in pred.items()}
    payload=dict(sources=sources,metrics=measured,diagnostic_gain_bgr=gain.tolist(),
                 diagnostic_shift_px=shift.tolist(),scores=rows,
                 limitation='Counterfactual crop manipulation is diagnostic only, forbidden for runtime pose compensation. White-region centroid depends on segmentation/appearance, not calibrated physical motion. Same-scene normal claim from user; no new labels or training.')
    (out/'diagnosis.json').write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps(payload,indent=2))


if __name__=='__main__':
    main()
