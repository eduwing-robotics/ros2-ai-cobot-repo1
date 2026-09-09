"""Nominal scale sanity audit, not image-to-world calibration."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main():
    config=ROOT/'vision_assembly/config'
    physical=json.loads((config/'physical_board.json').read_text())
    requirement=json.loads((config/'vrm_gripper_access_requirement.json').read_text())
    base=ROOT/'vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1'
    frames=[]
    for stamp in ['153918','155131']:
        report=json.loads((base/f'fresh_s22_inspection_roi_20260906_{stamp}_last/report.json').read_text())
        frames.append({r['slot']:r['primary'] for r in report['rows']})
    px_per_mm=1600/physical['size_mm']['x']
    measurement=requirement['user_reported_measurement']
    total=measurement['socket_width_height_mm'][0]-measurement['part_width_height_mm'][0]
    rows=[]
    for slot,a in frames[0].items():
        b=frames[1][slot]
        if not a or not b:
            raise ValueError('Missing contour')
        width=max(p[0] for p in a['polygon'])-min(p[0] for p in a['polygon'])
        travel=b['center_px'][0]-a['center_px'][0]
        rows.append(dict(slot=slot,predicted_width_px=width,nominal_width_mm=width/px_per_mm,
                         travel_px=travel,nominal_travel_mm=travel/px_per_mm))
    result=dict(status='UNKNOWN',runtime_enabled=False,nominal_px_per_mm=px_per_mm,
                opening_minus_body_width_mm=total,opening_based_nominal_travel_px=total*px_per_mm,rows=rows,
                socket_measurement_location=measurement.get('socket_measurement_location', 'Unspecified'),
                seated_contact_width_mm=measurement.get('seated_contact_width_mm'),
                limitation='Board-plane nominal scale only. Endpoint contact, actual socket height-dependent width, projection and contour error unverified. No rescaling or forced endpoint normalization; mismatch does not invalidate user dimensions.')
    path=base/'metric_consistency_top_opening_audit.json'
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
