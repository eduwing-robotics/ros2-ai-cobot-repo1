"""Offline pose evidence from four coherent edges; never a PASS/FAIL provider."""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def polygon_from_edges(edges):
    if len(edges) != 4 or any('candidate' not in e or e.get('ambiguous', True) for e in edges):
        return None
    lines = [e['candidate'] for e in edges]
    angles = [float(np.degrees(np.arctan(e['slope'])))*(-1 if i%2==0 else 1)
              for i,e in enumerate(lines)]
    # Fit-consistency check, NOT an allowed assembly angle threshold.
    if not np.isfinite(angles).all() or np.ptp(angles)>3:
        return None
    corners=[]
    for vi,hi in [(0,1),(2,1),(2,3),(0,3)]:
        v,h=lines[vi],lines[hi]
        matrix=np.array([[1,-v['slope']],[-h['slope'],1]],dtype=float)
        if abs(np.linalg.det(matrix))<.1:
            return None
        corners.append(np.linalg.solve(matrix,[v['intercept'],h['intercept']]))
    corners=np.array(corners)
    if not np.isfinite(corners).all():
        return None
    # Prevent reversed/crossing edge order from creating a fictitious polygon.
    if not (corners[1,0]>corners[0,0] and corners[2,0]>corners[3,0]
            and corners[3,1]>corners[0,1] and corners[2,1]>corners[1,1]):
        return None
    return dict(corners_px=corners.tolist(),center_px=corners.mean(axis=0).tolist(),
                angle_deg=float(np.median(angles)),edge_angles_deg=angles)


def pose_evidence(row):
    base=dict(status='UNKNOWN',authority='ADVISORY_ONLY',calibration_id=None,
              measurement_available=False)
    if row['reasons'] != ['UNVERIFIED_LINE']*4:
        return dict(**base,reason='AMBIGUOUS_OR_UNSUPPORTED_EDGE')
    raw,clahe=polygon_from_edges(row['raw']),polygon_from_edges(row['clahe'])
    if raw is None or clahe is None:
        return dict(**base,reason='INCONSISTENT_QUADRILATERAL')
    gap=float(np.max(np.linalg.norm(np.array(raw['corners_px'])-clahe['corners_px'],axis=1)))
    if gap>4:
        return dict(**base,reason='EXTRAPOLATED_CORNER_DISAGREEMENT',corner_gap_px=gap)
    base['measurement_available']=True
    return dict(**base,reason='UNVERIFIED_POSE',**raw,corner_gap_px=gap)


def main():
    paths=[ROOT/'runtime/inspection'/name/'report.json' for name in
           ('vrm_robust_edges_pose_regression','vrm_robust_edges_190202')]
    rows=[]
    for path in paths:
        for row in json.loads(path.read_text())['rows']:
            rows.append(dict(stamp=row['stamp'],slot=row['slot'],image_sha256=row['image_sha256'],
                             **pose_evidence(row)))
    # A fixed previously labelled normal frame, never chosen by fit to defects.
    references={r['slot']:r for r in rows if r['stamp']=='143632'}
    for r in rows:
        ref=references[r['slot']]
        if r['measurement_available'] and ref['measurement_available']:
            r['reference_stamp']='143632'
            r['delta_center_px']=(np.array(r['center_px'])-ref['center_px']).tolist()
            r['delta_angle_deg']=r['angle_deg']-ref['angle_deg']
        else:
            r['relative_pose_reason']='CURRENT_OR_REFERENCE_MEASUREMENT_UNAVAILABLE'
    output=ROOT/'runtime/inspection/vrm_line_pose_evidence_20260905.json'
    output.write_text(json.dumps(dict(authority='ADVISORY_ONLY',runtime_enabled=False,
        rows=rows,robot_command_sent=False,conveyor_command_sent=False,
        note='No defect tolerances selected. Image-space centers in fixed slot crop; no clearance, Z height or calibrated physical displacement. A coherent socket contour can still be wrong.'),indent=2))
    print('available',sum(r['measurement_available'] for r in rows),'/',len(rows))
    for r in rows:
        if r['measurement_available']:
            print(r['stamp'],r['slot'],r['angle_deg'],r.get('delta_center_px'))


if __name__=='__main__':
    main()
