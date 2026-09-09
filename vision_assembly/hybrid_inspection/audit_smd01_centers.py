"""Compare advisory segmentation centres with thresholded bright-body centres.

Offline diagnostic only: neither centre is certified socket clearance.
"""
import json
from pathlib import Path

import cv2
import numpy as np
from audit_smd01_outline import bright_outline

ROOT = Path(__file__).resolve().parents[2]


def main():
    base = ROOT / 'runtime/inspection'
    rows = json.loads((base / 'pose_normal_defect_separation_20260907.json').read_text())['rows']
    rows += [dict(source='hybrid_fixed_slot/20260907_114134_401329', truth='user_restored_normal')]
    out = base / 'smd01_center_comparison_20260907'
    out.mkdir(exist_ok=False)
    results, panels = [], []
    for row in rows:
        directory = base / row['source']
        report = json.loads((directory / 'hybrid_report.json').read_text())
        slot = next(s for s in report['slots'] if s['slot_id'] == 'smd_capacitor_01')
        pose = slot['stages']['pose']
        measured = pose['measured']
        board = cv2.imread(str(directory / 'aligned_board.png'))
        if board is None or board.shape[:2] != (1266, 1600):
            raise ValueError(f'Invalid canonical board: {directory}')
        crop = board[1014:1154, 1181:1361].copy()
        display = crop.copy()
        center = np.array(measured['center_px']) - [1181, 1014]
        expected = np.array(measured['expected_center_px']) - [1181, 1014]
        cv2.drawMarker(display, tuple(np.rint(center).astype(int)), (255, 0, 255), cv2.MARKER_CROSS, 9, 1)
        cv2.drawMarker(display, tuple(np.rint(expected).astype(int)), (255, 180, 0), cv2.MARKER_CROSS, 9, 1)
        probes = []
        for threshold in [100, 130, 160]:
            contour = bright_outline(crop, threshold)
            if contour is None:
                probes.append(dict(threshold=threshold, found=False))
                continue
            moments = cv2.moments(contour)
            if moments['m00'] == 0:
                continue
            bright = np.array([moments['m10'], moments['m01']]) / moments['m00']
            probes.append(dict(threshold=threshold, found=True, center_native=bright.tolist(),
                               segmentation_distance_px=float(np.linalg.norm(bright-center))))
            if threshold == 130:
                cv2.drawContours(display, [contour], -1, (0, 255, 0), 1)
                cv2.drawMarker(display, tuple(np.rint(bright).astype(int)), (0, 255, 0), cv2.MARKER_CROSS, 9, 1)
        tile = cv2.resize(np.hstack([crop, display]), (1080, 420), interpolation=cv2.INTER_NEAREST)
        tile = cv2.copyMakeBorder(tile, 35, 0, 0, 0, cv2.BORDER_CONSTANT)
        cv2.putText(tile, f"{row['truth']} | MAGENTA segmentation / GREEN bright / BLUE nominal",
                    (8, 24), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
        panels.append(tile)
        results.append(dict(source=row['source'], truth=row['truth'],
                            confidence=pose['confidence'], measured=measured, probes=probes))
    cv2.imwrite(str(out / 'comparison.png'), np.vstack(panels))
    (out / 'audit.json').write_text(json.dumps(dict(rows=results,
        policy='Diagnostic only. Historical saved segmentation evidence; no retraining, '
               'local alignment, calibrated wall, runtime threshold or authority changes.'), indent=2))
    for row in results:
        print(row['truth'], 'confidence', round(row['confidence'], 3),
              'centroid distances', [round(p['segmentation_distance_px'], 2) for p in row['probes'] if p.get('found')])


if __name__ == '__main__':
    main()
