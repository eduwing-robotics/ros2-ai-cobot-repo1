"""Empty-only wall candidates transferred unchanged to assembled crops.

Search windows are manually bounded from the empty-reference review, not fitted
to normal/defect outcomes. They do not distinguish inner from outer socket walls.
"""
import json
from pathlib import Path
import cv2
import numpy as np
from audit_smd01_outline import bright_outline

ROOT = Path(__file__).resolve().parents[2]


def wall_candidates(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    # Median across the long straight section suppresses isolated diagonal ridges.
    profiles = {
        'top': (np.median(np.abs(np.diff(gray[:, 75:125], axis=0)), axis=1), 30, 60),
        'bottom': (np.median(np.abs(np.diff(gray[:, 75:125], axis=0)), axis=1), 80, 115),
        'left': (np.median(np.abs(np.diff(gray[55:80, :], axis=1)), axis=0), 40, 75),
        'right': (np.median(np.abs(np.diff(gray[55:80, :], axis=1)), axis=0), 125, 155),
    }
    result = {}
    for side, (profile, low, high) in profiles.items():
        ranked = sorted(range(low, high), key=lambda i: float(profile[i]), reverse=True)
        selected = []
        for i in ranked:
            if profile[i] <= 0:
                break
            if all(abs(i-j) >= 4 for j in selected):
                selected.append(i)
            if len(selected) == 2:
                break
        result[side] = [dict(coordinate_px=i+.5, strength=float(profile[i])) for i in selected]
    return result


def main():
    base = ROOT/'runtime/inspection'
    references = base/'smd01_empty_reference_audit_20260907'
    out = base/'smd01_wall_consensus_20260907'
    out.mkdir(exist_ok=False)
    reference_rows = []
    for path in sorted(references.glob('*_crop.png')):
        im = cv2.imread(str(path))
        reference_rows.append(dict(source=str(path), candidates=wall_candidates(im)))
    consensus = {}
    if len(reference_rows) < 3:
        raise RuntimeError('At least three empty references required')
    for side in ['left','right','top','bottom']:
        coords = [r['candidates'][side][0]['coordinate_px'] for r in reference_rows if r['candidates'][side]]
        if len(coords) != len(reference_rows):
            raise RuntimeError(f'Unresolved {side} edge; no transferable rectangle')
        consensus[side] = dict(median_px=float(np.median(coords)), spread_px=float(np.ptp(coords)),
                               reference_count=len(coords), is_certified_wall=False)
    left,right,top,bottom = [int(round(consensus[s]['median_px'])) for s in ['left','right','top','bottom']]
    source_rows = json.loads((base/'smd01_outline_audit_20260907/audit.json').read_text())['rows']
    tiles, results = [], []
    for index,row in enumerate(source_rows):
        board = cv2.imread(row['source'])
        x,y = row['crop_origin']
        crop = board[y:y+140,x:x+180].copy()
        overlay = crop.copy()
        cv2.rectangle(overlay,(left,top),(right,bottom),(255,200,0),1)
        contour = bright_outline(crop,130)
        overrun = None
        if contour is not None:
            cv2.drawContours(overlay,[contour],-1,(0,255,255),1)
            bx,by,bw,bh = cv2.boundingRect(contour)
            overrun = dict(left_px=max(0,left-bx),right_px=max(0,bx+bw-1-right),
                           top_px=max(0,top-by),bottom_px=max(0,by+bh-1-bottom))
        panel=cv2.resize(np.hstack([crop,overlay]),None,fx=3,fy=3,interpolation=cv2.INTER_NEAREST)
        tile=cv2.copyMakeBorder(panel,35,0,0,0,cv2.BORDER_CONSTANT,value=(25,25,25))
        cv2.putText(tile,f"{index+1} {row['truth']} | ORIGINAL / EMPTY-ONLY CANDIDATE WALL + BODY",
                    (8,24),cv2.FONT_HERSHEY_SIMPLEX,.55,(230,230,230),1,cv2.LINE_AA)
        tiles.append(tile)
        results.append(dict(source=row['source'],truth=row['truth'],candidate_overrun_px=overrun))
    cv2.imwrite(str(out/'comparison.png'),np.vstack(tiles))
    payload=dict(reference_rows=reference_rows,consensus=consensus,rows=results,
                 status='UNKNOWN_DIAGNOSTIC_ONLY',
                 limitation='Fixed empty-only candidate rectangle, not measured inner wall. No local registration or outcome tuning. Pixel overrun is not physical clearance/height. No runtime change.')
    (out/'audit.json').write_text(json.dumps(payload,indent=2))
    print(json.dumps(dict(consensus=consensus,rows=results),indent=2))


if __name__ == '__main__':
    main()
