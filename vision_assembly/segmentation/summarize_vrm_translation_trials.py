"""Descriptive frozen-candidate trial ranges; no learned acceptance threshold."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main():
    base=ROOT/'vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1'
    output=base/'translation_trial_summary.json'
    if output.exists():
        raise FileExistsError(output)
    left=['152933','153345','153918','154722','155607','160026']
    right={'155131':[1,2,3,4,5],'153632':[4],'154508':[2]}
    frames={}
    expected='98572682b1df4aef452d7d5727c3cf6acf6abc7e6d954fdce7a214046d6f10cc'
    for stamp in sorted(set(left)|set(right)):
        path=base/f'fresh_s22_inspection_roi_20260906_{stamp}_last/report.json'
        report=json.loads(path.read_text())
        if report['weights_sha256']!=expected:
            raise ValueError('Checkpoint mismatch')
        for row in report['rows']:
            if hashlib.sha256(Path(row['source_image']).read_bytes()).hexdigest()!=row['image_sha256']:
                raise ValueError('Source changed')
        frames[stamp]={row['slot']:row for row in report['rows']}
    slots=[]
    for number in range(1,6):
        slot=f'vrm_{number:02d}'
        def sample(stamp):
            row=frames[stamp][slot]
            if row['primary'] is None:
                raise ValueError(f'Missing candidate {stamp}/{slot}; cannot summarize as zero')
            return dict(capture=stamp,x=row['primary']['center_px'][0]+row['crop_origin_px'][0],
                        alignment=row['alignment_score'])
        a=[sample(t) for t in left]
        b=[sample(t) for t,indices in right.items() if number in indices]
        low,high=min(r['x'] for r in a),max(r['x'] for r in a)
        rmin=min(r['x'] for r in b)
        slots.append(dict(slot=slot,left_samples=a,right_samples=b,left_range_px=[low,high],
                          left_span_px=high-low,right_min_px=rmin,observed_range_separation_px=rmin-high))
    result=dict(status='UNKNOWN',authority='ADVISORY_ONLY',runtime_enabled=False,weights_sha256=expected,
        left_scene_intent='Requested left seating; user confirmed VRM5 left in155607. No pixel-based exclusion of outliers.',
        rows=slots,threshold_fitted=False,
        limitation='Selected development sequences with repeated physical parts and few right examples. Observed ranges are not confidence intervals, calibrated1mm clearance, or independent accuracy. No common-motion subtraction.')
    output.write_text(json.dumps(result,indent=2))
    for r in slots:
        print(r['slot'],'left_span',round(r['left_span_px'],3),'separation',round(r['observed_range_separation_px'],3))


if __name__=='__main__':
    main()
