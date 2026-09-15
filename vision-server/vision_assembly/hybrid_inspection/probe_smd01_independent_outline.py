"""Guarded bright-body measurement and offline replay CLI; no height judgement."""
import json
from pathlib import Path
import cv2
import numpy as np
from audit_smd01_outline import bright_outline

ROOT = Path(__file__).resolve().parents[2]


def measure(crop):
    if crop is None or crop.shape != (140, 180, 3) or crop.dtype != np.uint8:
        return dict(valid=False, reason='INVALID_WINDOW')
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    local = cv2.createCLAHE(clipLimit=2., tileGridSize=(8,8)).apply(gray)
    edges = cv2.Canny(local, 50, 120)
    nearby_edges = cv2.dilate(edges, np.ones((5,5), np.uint8))
    centers = []
    supports = []
    for threshold in (100, 130, 160):
        count, _, stats, _ = cv2.connectedComponentsWithStats(np.uint8(gray >= threshold)*255)
        # Do not choose the nearest of two plausible bodies. Large separate
        # highlights or foreign objects invalidate this narrow fixed window.
        if sum(stats[i, cv2.CC_STAT_AREA] >= 500 for i in range(1,count)) > 1:
            return dict(valid=False, reason='MULTIPLE_BRIGHT_BODIES')
        contour = bright_outline(crop, threshold)
        if contour is None or cv2.contourArea(contour) < 500:
            return dict(valid=False, reason='BODY_NOT_RESOLVED')
        x,y,w,h = cv2.boundingRect(contour)
        if x <= 0 or y <= 0 or x+w >= crop.shape[1] or y+h >= crop.shape[0]:
            return dict(valid=False, reason='BODY_TOUCHES_WINDOW')
        area = cv2.contourArea(contour)
        if area > crop.shape[0]*crop.shape[1]*.45:
            return dict(valid=False, reason='BODY_TOO_LARGE')
        border = np.zeros(gray.shape, np.uint8)
        cv2.drawContours(border,[contour],-1,255,1)
        support = float(np.count_nonzero((border>0)&(nearby_edges>0))/np.count_nonzero(border))
        supports.append(support)
        if support < .60:
            return dict(valid=False, reason='CLAHE_EDGE_NOT_CORROBORATED', edge_support=support)
        moments = cv2.moments(contour)
        centers.append([moments['m10']/moments['m00'], moments['m01']/moments['m00']])
    centers = np.asarray(centers)
    spread = float(np.linalg.norm(centers[:,None]-centers[None,:], axis=2).max())
    return dict(valid=spread <= 3., reason='CONSENSUS' if spread <= 3 else 'THRESHOLD_UNSTABLE',
                center=np.median(centers,axis=0).tolist(), spread_px=spread,
                minimum_clahe_edge_support=min(supports))


def main():
    base = ROOT/'runtime/inspection'
    cases = json.loads((base/'smd01_small_lip_integration_20260907.json').read_text())['rows']
    cases += [dict(report=str(base/'hybrid_fixed_slot/20260907_132818_028086/hybrid_report.json'),truth='defect')]
    result = []
    for case in cases:
        path = Path(case['report'])
        image = cv2.imread(str(path.parent/'aligned_board.png'))
        if image is None or image.shape[:2] != (1266,1600):
            raise ValueError(str(path))
        measurement = measure(image[1014:1154,1181:1361])
        result.append(dict(**case,measurement=measurement))
    (base/'smd01_independent_outline_guarded_20260907.json').write_text(json.dumps(dict(rows=result,
        limitation='Offline bright component measurement only. No physical seating claim, no calibrated confidence, no runtime or model changes.'),indent=2))
    print(json.dumps([dict(truth=r['truth'],report=Path(r['report']).parent.name,**r['measurement']) for r in result],indent=2))


if __name__=='__main__':
    main()
