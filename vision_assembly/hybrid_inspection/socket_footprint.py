"""Fixed convex socket versus measured outline, diagnostic only (not height).

Coordinates must share one board frame and unit. No fitted translation/rotation.
"""
import cv2
import numpy as np


def compare_footprint(socket, outline):
    result = dict(status='UNKNOWN', authority='ADVISORY_ONLY',
                  reason='INVALID_OR_MISSING_POLYGON')
    try:
        socket = np.asarray(socket, dtype=np.float32)
        outline = np.asarray(outline, dtype=np.float32)
        for p in (socket, outline):
            if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
                return result
            if abs(cv2.contourArea(p)) <= 1e-6:
                return result
        if not cv2.isContourConvex(socket):
            return dict(result, reason='NONCONVEX_SOCKET_UNSUPPORTED')
        # For convex socket, every point/segment is inside iff all vertices are.
        distances = np.array([cv2.pointPolygonTest(socket, tuple(map(float, p)), True)
                              for p in outline])
        result.update(reason='UNVALIDATED_CAD_FOOTPRINT_MEASUREMENT',
                      minimum_signed_clearance=float(distances.min()),
                      maximum_exit=max(0., -float(distances.min())),
                      outside_vertex_count=int((distances < -1e-5).sum()),
                      measured_outline_inside=bool((distances >= -1e-5).all()),
                      limitation='CAD floor is not calibrated socket wall; silhouette is not physical seating height. No PASS/FAIL authority.')
    except (ValueError, TypeError, cv2.error, OverflowError):
        pass
    return result
