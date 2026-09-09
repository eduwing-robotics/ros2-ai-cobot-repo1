"""Multiple-row empty-slot evidence, no fitted production wall or thresholds."""
import json
from pathlib import Path
import cv2
import numpy as np
from audit_smd01_wall_pairs import dark_pairs

ROOT = Path(__file__).resolve().parents[2]


def scan_left(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    scans = []
    for y in range(53, 87, 3):
        pairs = dark_pairs(np.median(gray[y-1:y+2], axis=0), 40, 80)
        scans.append(dict(y=y, candidates=pairs))
    scored = []
    for x in np.arange(43.5, 79, 1):
        hits = sum(any(abs(p['outer_high']-x) <= 2 for p in row['candidates']) for row in scans)
        scored.append(dict(x=float(x), rows_supported=hits))
    ranked = sorted(scored, key=lambda p: p['rows_supported'], reverse=True)
    peaks = []
    for p in ranked:
        if p['rows_supported'] and all(abs(p['x']-q['x']) >= 6 for q in peaks):
            peaks.append(p)
        if len(peaks) == 3:
            break
    return dict(scans=scans, peaks=peaks, total_rows=len(scans))


def main():
    base = ROOT/'runtime/inspection'
    out = base/'smd01_left_continuity_20260907'
    out.mkdir(exist_ok=False)
    tiles, rows = [], []
    for path in sorted((base/'smd01_empty_reference_audit_20260907').glob('*_crop.png')):
        im=cv2.imread(str(path)); result=scan_left(im); overlay=im.copy()
        for row in result['scans']:
            for p in row['candidates']:
                cv2.circle(overlay,(round(p['outer_high']),row['y']),1,(180,180,180),-1)
        for peak,color in zip(result['peaks'],[(0,255,255),(255,150,0),(255,0,255)]):
            x=round(peak['x']);cv2.line(overlay,(x,50),(x,88),color,1)
        panel=cv2.resize(np.hstack([im,overlay]),None,fx=3,fy=3,interpolation=cv2.INTER_NEAREST)
        tile=cv2.copyMakeBorder(panel,35,0,0,0,cv2.BORDER_CONSTANT,value=(25,25,25))
        cv2.putText(tile,f'{path.stem} | LEFT WALL CANDIDATES ONLY', (8,24),cv2.FONT_HERSHEY_SIMPLEX,.55,(230,230,230),1,cv2.LINE_AA)
        tiles.append(tile);rows.append(dict(source=str(path),**result))
    cv2.imwrite(str(out/'comparison.png'),np.vstack(tiles))
    (out/'audit.json').write_text(json.dumps(dict(rows=rows,status='UNKNOWN_DIAGNOSTIC_ONLY',
        limitation='Votes include competing edges in overlapping row strips, not independent observations. Fixed near-vertical candidates only. No physical clearance or runtime change.'),indent=2))
    print(json.dumps([dict(source=r['source'],peaks=r['peaks'],total_rows=r['total_rows']) for r in rows],indent=2))


if __name__=='__main__':main()
