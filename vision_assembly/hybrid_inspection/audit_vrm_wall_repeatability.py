"""Offline dark-groove repeatability. Groove is not a verified inner socket wall."""
import hashlib
import argparse
import json
from pathlib import Path
import sys
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'vision_assembly/slot_classifier'))
from audit_vrm_socket_reference import groove_bounds
from preprocessor_and_cropper import FixedSlotCropper


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'runtime/inspection/vrm_wall_repeatability_20260908')
    output = parser.parse_args().output
    output.mkdir(exist_ok=False)
    cropper = FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    controls = [('134637', range(1,6)), ('141311',[2,4]), ('141603',[1,3,5])]
    rows, panels = [], {}
    for stamp, ids in controls:
        path = ROOT/f'runtime/inspection/s22_inspection_roi_20260905_{stamp}.png'
        board = cropper.register(cv2.imread(str(path)))
        if board.alignment_reason != 'OK' or board.alignment_score < cropper.config['global_alignment']['minimum_score']:
            raise ValueError('Uncertain registration')
        for slot in cropper.fixed_slots(board.image_bgr):
            if slot.slot_id not in [f'vrm_{i:02}' for i in ids]:
                continue
            x,y,w,h = slot.geometry
            cw,ch = round(w*1.5),round(h*1.5)
            crop = cv2.getRectSubPix(board.image_bgr,(cw,ch),(float(x),float(y)))
            left,top,right,bottom = groove_bounds(crop)
            origin_x = x-(cw-1)/2
            rows.append(dict(stamp=stamp, slot=slot.slot_id, image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             right_groove_board_x_px=origin_x+right, groove_width_px=right-left,
                             source=str(path), alignment_score=board.alignment_score))
            cv2.rectangle(crop,(left,top),(right,bottom),(255,180,0),1)
            panel=cv2.resize(crop,(240,300))
            panel=cv2.copyMakeBorder(panel,30,0,0,0,cv2.BORDER_CONSTANT)
            cv2.putText(panel,f'{stamp} {slot.slot_id} GROOVE?',(3,20),0,.45,(255,255,255),1)
            panels[(stamp,slot.slot_id)] = panel
    summary=[]
    for sid in sorted({r['slot'] for r in rows}):
        values=[r['right_groove_board_x_px'] for r in rows if r['slot']==sid]
        summary.append(dict(slot=sid, observations=len(values), right_groove_range_px=float(np.ptp(values)),
                            minimum_x_px=min(values), maximum_x_px=max(values),
                            physical_wall_validated=False))
    ordered = [panels[('134637',f'vrm_{i:02}')] for i in range(1,6)]
    ordered += [panels[('141311' if i in (2,4) else '141603',f'vrm_{i:02}')] for i in range(1,6)]
    cv2.imwrite(str(output/'empty_groove_comparison.jpg'),np.vstack([np.hstack(ordered[i:i+5]) for i in (0,5)]))
    gap_rows = []
    for stamp in ('170142','185803'):
        paths = list((ROOT/'runtime/inspection/vrm_controls_20260908').glob(f'extended_normal_{stamp}/*/hybrid_report.json'))
        if len(paths) != 1:
            raise ValueError('Expected unique current report')
        report = json.loads(paths[0].read_text())
        for slot in report['slots']:
            if slot['slot_id'] not in ('vrm_02','vrm_03'):
                continue
            boundary = slot['stages'].get('vrm_boundary',{}).get('measured')
            if not boundary:
                continue
            ref = next(s for s in summary if s['slot']==slot['slot_id'])
            body_right = boundary['position'][2]
            gap_rows.append(dict(stamp=stamp,slot=slot['slot_id'],report=str(paths[0]),
                body_right_x_px=body_right,
                signed_groove_gap_interval_px=[ref['minimum_x_px']-body_right,ref['maximum_x_px']-body_right],
                measured_clearance_mm=None,status='UNKNOWN',
                limitation='Reference repeat spread only, not complete uncertainty; mask edge and groove are not calibrated physical surfaces.'))
    data=dict(rows=rows, summary=summary, gap_comparison=gap_rows, runtime_enabled=False,
              authority='ADVISORY_ONLY', measured_clearance_mm=None,
              limitation='Two observations per slot; darkest groove may be shadow or outer rim. No physical inner-wall identification or millimetre certification.',
              robot_command_sent=False, conveyor_command_sent=False)
    (output/'audit.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
