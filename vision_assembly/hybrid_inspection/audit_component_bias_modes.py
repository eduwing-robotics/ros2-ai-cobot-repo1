"""Counterfactual pose audit of saved reports, never a new inspection or label."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from main import build_advisory_candidates
from opencv_inspectors import check_auxiliary_pose


def without_bias(slots):
    result = deepcopy(slots)
    for slot in result:
        old = slot.get('stages', {}).get('pose', {})
        m = old.get('measured') or {}
        limits = old.get('limits') or {}
        if 'raw_offset_mm' not in m or 'expected_axis_angle_deg' not in limits:
            continue
        # Identity pixels/mm lets the same pose checker evaluate archived mm
        # offsets, not pretend that this is a new detector measurement.
        item = dict(confidence=old['confidence'], evidence=dict(present=True,
            center_px=m['raw_offset_mm'], expected_center_px=[0.,0.],
            long_axis_angle_deg_undirected=m.get('axis_angle_deg',0.),
            mask_area_px=m.get('mask_area_px'),
            normalized_slot_distance=m.get('normalized_slot_distance')))
        check = check_auxiliary_pose(item, limits['expected_axis_angle_deg'],
            (100,100,3), (100.,100.),
            position_tolerance_mm=limits['position_tolerance_mm'],
            angle_tolerance_deg=limits['angle_tolerance_deg'],
            slot_reference_offset_mm=m.get('slot_reference_correction_mm',[0.,0.]),
            slot_reference_calibration_id=m.get('slot_reference_calibration_id'),
            check_axis_angle=m.get('axis_angle_checked',True)).to_dict()
        # Retain true archived pixel geometry for downstream display gates.
        check['measured']['center_px']=m['center_px']
        check['measured']['expected_center_px']=m['expected_center_px']
        slot['stages']['pose']=check
    return result


def flags(slots):
    return {r['slot_id']:r['codes'] for r in build_advisory_candidates(slots)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    rows=[]; skipped=0
    for path in sorted(args.root.rglob('hybrid_report.json')):
        try:
            report=json.loads(path.read_text())
            source=Path(report['input_image'])
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=report['input_sha256']:
                skipped+=1;continue
            before=flags(report['slots']);after=flags(without_bias(report['slots']))
            rows.append(dict(report=str(path),source=str(source),sha256=report['input_sha256'],
                baseline=before,no_component_bias=after,changed=before!=after,
                ground_truth='UNASSIGNED', final_decision_changed=False))
        except (KeyError,ValueError,TypeError):
            skipped+=1
    payload=dict(purpose='COUNTERFACTUAL_NOT_NEW_INFERENCE',rows=rows,skipped=skipped,
        report_count=len(rows),changed_count=sum(r['changed'] for r in rows),
        limitation='No automatic truth labels, no accuracy claim, no runtime promotion.')
    with args.output.open('x') as stream: json.dump(payload,stream,indent=2)
    print(json.dumps({k:v for k,v in payload.items() if k!='rows'},indent=2))


if __name__=='__main__': main()
