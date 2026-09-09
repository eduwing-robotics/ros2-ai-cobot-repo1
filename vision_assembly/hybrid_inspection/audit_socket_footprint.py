"""Replay saved masks against fixed CAD floor polygons; never edits decisions."""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from socket_footprint import compare_footprint


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report-dir',type=Path,required=True)
    p.add_argument('--trial',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    mapping=json.loads((args.trial/'trial.json').read_text())['mapping']
    masks=[f for f in (args.report_dir/'yolo_auxiliary').glob('*.json') if not f.name.endswith('_latest.json')]
    if len(masks)!=1: raise ValueError('Expected exactly one saved segmentation result')
    data=json.loads(masks[0].read_text())
    source=Path(data['input_image'])
    if hashlib.sha256(source.read_bytes()).hexdigest()!=data['input_sha256']:
        raise ValueError('Segmentation input hash mismatch')
    image=cv2.imread(str(source))
    if image is None or image.shape[:2]!=(1266,1600): raise ValueError('Wrong canonical frame')
    detections={d['slot_id']:d for d in data['detections']}
    rows=[]
    for slot in mapping:
        # Stored physical board axes point opposite image axes; no local fitting.
        mm=np.array(slot['polygon_board_mm'],dtype=float)
        px=(.5-mm/np.array([139.,110.]))*np.array([1600.,1266.])
        d=detections.get(slot['slot_id'],{})
        e=d.get('evidence',{})
        outline=e.get('polygon_px') if e.get('present') else None
        # Compare in mm to handle the anisotropic pixel scale correctly.
        observed=None if outline is None else np.array(outline)*[139/1600,110/1266]
        r=compare_footprint(px*[139/1600,110/1266],observed)
        rows.append(dict(slot_id=slot['slot_id'],unit='mm',confidence=d.get('confidence'),**r))
        cv2.polylines(image,[np.rint(px).astype(np.int32)],True,(0,210,255),1)
        if outline is not None:
            cv2.polylines(image,[np.rint(outline).astype(np.int32)],True,(255,200,0),1)
    args.output.mkdir(parents=True,exist_ok=False)
    result=dict(rows=rows,authority='ADVISORY_ONLY',
                source=str(source),source_sha256=data['input_sha256'],
                trial_sha256=hashlib.sha256((args.trial/'trial.json').read_bytes()).hexdigest(),
                segmentation_sha256=hashlib.sha256(masks[0].read_bytes()).hexdigest(),
                runtime_changed=False, note='Yellow CAD floor, cyan detected mask. Distance is diagnostic; no physical socket/height certification.')
    (args.output/'audit.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    if not cv2.imwrite(str(args.output/'outlines.png'),image): raise OSError('Image save failed')
    print([(r['slot_id'],round(r.get('maximum_exit',0),3)) for r in rows])


if __name__=='__main__': main()
