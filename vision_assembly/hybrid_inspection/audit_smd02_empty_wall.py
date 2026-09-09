"""Diagnostic fixed-frame empty SMD02 crops; never changes inspection criteria."""
import hashlib
import json
import tempfile
from pathlib import Path

import cv2
import numpy as np
from preprocessor_and_cropper import FixedSlotCropper

ROOT = Path(__file__).resolve().parents[2]


def edge_candidates(gray, origin):
    """Rank raw-gradient edges near fixed CAD face, not near detected parts.

    +/-15px windows are exploratory. Multiple peaks deliberately preserved:
    neither the strongest peak nor repeated peaks certify an inner wall.
    """
    x,y=origin
    gray=gray.astype(np.float32)
    horizontal=np.median(np.abs(np.diff(gray[55:115,:],axis=1)),axis=0)
    vertical=np.median(np.abs(np.diff(gray[:,50:85],axis=0)),axis=1)
    profiles={'left':(horizontal,1467.62-x,x),'right':(horizontal,1522.89-x,x),
              'top':(vertical,790.76-y,y),'bottom':(vertical,880.27-y,y)}
    result={}
    for side,(profile,expected,offset) in profiles.items():
        low=max(0,int(expected)-15)
        high=min(len(profile),int(expected)+16)
        selected=[]
        for i in sorted(range(low,high),key=lambda i:float(profile[i]),reverse=True):
            if profile[i]>0 and all(abs(i-j)>=4 for j in selected):
                selected.append(i)
            if len(selected)==3:
                break
        result[side]=[dict(board_coordinate_px=i+.5+offset,strength=float(profile[i])) for i in selected]
    return result


def main():
    dataset = ROOT / 'vision_assembly/slot_classifier/datasets/component_presence_v1'
    records = [json.loads(line) for line in (dataset / 'manifest.jsonl').read_text().splitlines() if line.strip()]
    records = [r for r in records if r['slot_id'] == 'smd_capacitor_02' and r['label'] == 'empty']
    cropper = FixedSlotCropper(ROOT / 'vision_assembly/config/full_board_inspection.json')
    out = Path(tempfile.mkdtemp(prefix='smd02_wall_', dir=ROOT / 'runtime/inspection'))
    tiles, rows = [], []
    for record in records:
        source = dataset / record['source_image']
        if hashlib.sha256(source.read_bytes()).hexdigest() != record['source_sha256']:
            raise ValueError(f'Source hash mismatch: {source}')
        result = cropper.register(cv2.imread(str(source)))
        row = dict(source=str(source), score=result.alignment_score, reason=result.alignment_reason)
        rows.append(row)
        if result.alignment_reason != 'OK' or result.alignment_score < cropper.config['global_alignment']['minimum_score']:
            continue
        slot = next(s for s in cropper.fixed_slots(result.image_bgr) if s.slot_id == 'smd_capacitor_02')
        cx, cy, sx, sy = slot.geometry
        x, y = int(cx)-65, int(cy)-85
        crop = result.image_bgr[y:y+170, x:x+130].copy()
        if crop.shape != (170, 130, 3):
            raise ValueError('Clipped crop')
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        row['edge_candidates']=edge_candidates(gray,[x,y])
        local = cv2.createCLAHE(clipLimit=2., tileGridSize=(8,8)).apply(gray)
        annotated = crop.copy()
        cv2.rectangle(annotated, (round(cx-sx/2-x), round(cy-sy/2-y)),
                      (round(cx+sx/2-x), round(cy+sy/2-y)), (255,180,0), 1)
        panel = np.hstack([crop, annotated, cv2.cvtColor(local, cv2.COLOR_GRAY2BGR)])
        panel = cv2.resize(panel, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
        panel = cv2.copyMakeBorder(panel, 32, 0, 0, 0, cv2.BORDER_CONSTANT)
        cv2.putText(panel, source.stem+' EMPTY | RAW / NOMINAL ROI (NOT WALL) / CLAHE',
                    (5,22), cv2.FONT_HERSHEY_SIMPLEX, .48, (255,255,255), 1)
        tiles.append(panel)
        row.update(crop_origin=[x,y], nominal_geometry=list(slot.geometry))
    if tiles:
        if not cv2.imwrite(str(out/'comparison.png'), np.vstack(tiles)):
            raise OSError('Could not write comparison')
    consensus={}
    for side in ('left','right','top','bottom'):
        values=[r['edge_candidates'][side][0]['board_coordinate_px'] for r in rows
                if r.get('edge_candidates',{}).get(side)]
        consensus[side]=dict(count=len(values),median_px=float(np.median(values)) if values else None,
                            spread_px=float(np.ptp(values)) if values else None,certified_inner_wall=False)
    (out/'audit.json').write_text(json.dumps(dict(rows=rows,edge_consensus=consensus,
        limitation='Presence labels are not wall annotations. Board-only registration; no local normalization, wall certification, runtime vote or motion.'), indent=2))
    print(out)
    print(json.dumps(consensus))


if __name__ == '__main__':
    main()
