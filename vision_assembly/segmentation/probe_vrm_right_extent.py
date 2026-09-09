"""Relative rightmost contour evidence; never substitutes CAD ROI for socket wall."""
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def right_extent(polygon):
    p=np.asarray(polygon,dtype=float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<3 or not np.isfinite(p).all():
        raise ValueError('Invalid polygon')
    height=np.ptp(p[:,1])
    if height<=0:
        raise ValueError('Degenerate polygon')
    cut=p[:,1].min()+height*2/3
    # Include intersections with the lower-third cut, not only vertices.
    xs=[]
    for a,b in zip(p,np.roll(p,-1,axis=0)):
        if a[1]>=cut:
            xs.append(a[0])
        if (a[1]-cut)*(b[1]-cut)<0:
            xs.append(a[0]+(b[0]-a[0])*(cut-a[1])/(b[1]-a[1]))
    return dict(rightmost_px=float(p[:,0].max()),lower_third_rightmost_px=float(max(xs)))


def main():
    base=ROOT/'vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1'
    rows=[]
    for time in ['131407','132543','141441']:
        path=base/f'fresh_s22_inspection_roi_20260906_{time}_last/report.json'
        data=json.loads(path.read_text())
        row=next(r for r in data['rows'] if r['slot']=='vrm_04')
        if not row['primary']:
            raise ValueError('No contour')
        poly=np.asarray(row['primary']['polygon'])+np.asarray(row['crop_origin_px'])
        rows.append(dict(capture=time,**right_extent(poly),confidence=row['primary']['confidence']))
    reference=rows[1]
    for r in rows:
        r['rightward_delta_from_return_px']=r['rightmost_px']-reference['rightmost_px']
        r['lower_third_rightward_delta_from_return_px']=r['lower_third_rightmost_px']-reference['lower_third_rightmost_px']
    report=dict(status='UNKNOWN',authority='ADVISORY_ONLY',rows=rows,
        measured_socket_wall=None,minimum_required_gripper_clearance_mm=None,
        limitation='Relative predicted contour extents only, not wall clearance or collision prediction. CAD total socket clearance is not required gripper access clearance. No independent per-part realignment.',
        runtime_enabled=False)
    output=base/'vrm04_right_extent_20260906.json'
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
