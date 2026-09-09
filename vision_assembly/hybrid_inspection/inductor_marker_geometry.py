"""Strict dark-mark measurement; does not infer direction from the black base."""
import math
import cv2
import numpy as np


def measure_dark_mark(crop, center, radius):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(gray)
    yy, xx = np.ogrid[:gray.shape[0], :gray.shape[1]]
    inner = (xx-center[0])**2+(yy-center[1])**2 <= (.78*radius)**2
    if np.count_nonzero(inner) < 20:
        return None
    ceiling = min(100.0, float(np.percentile(gray[inner], 85))*.45)
    enhanced_ceiling = float(np.percentile(enhanced[inner], 85))*.75
    mask = ((gray < ceiling) & (enhanced < enhanced_ceiling) & inner).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if n <= 1:
        return None
    idx = 1+int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    area = int(stats[idx, cv2.CC_STAT_AREA])
    if area < 20:
        return None
    y, x = np.nonzero(labels == idx)
    eigen, vectors = np.linalg.eigh(np.cov(np.stack([x, y])))
    if eigen[0] <= 0:
        return None
    v = vectors[:, 1]
    axis = math.degrees(math.atan2(v[1], v[0])) % 180
    direction = math.degrees(math.atan2(float(y.mean())-center[1], float(x.mean())-center[0])) % 360
    edge = np.asarray([[int(x[y==row].max()), int(row)] for row in np.unique(y)
                       if np.quantile(y,.2) <= row <= np.quantile(y,.8)],np.float32)
    edge_axis = None
    if len(edge) >= 8:
        vx, vy, _, _ = cv2.fitLine(edge, cv2.DIST_HUBER, 0, .01, .01).ravel()
        edge_axis = math.degrees(math.atan2(float(vy),float(vx))) % 180
    return dict(axis_deg=axis, axis_error_deg=abs((axis-90+90)%180-90),
                diagnostic_inner_edge_axis_deg=edge_axis,
                direction_deg=direction, direction_error_deg=abs((direction-180+180)%360-180),
                elongation=float(eigen[1]/eigen[0]), area_px=area, threshold=ceiling)
