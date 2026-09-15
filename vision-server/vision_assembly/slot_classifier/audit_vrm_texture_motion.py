"""Measure texture motion relative to a fixed normal slot; never rectify it away.

Diagnostic only. A template match is neither presence nor an authoritative pose
verdict. Returned displacement stays in registered-board pixels. No modified
crop is passed to an appearance model or inspection pipeline.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper


def texture_motion(reference, current, size):
    """Search a central texture patch, retaining the measured pose as evidence."""
    reference = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY).astype(np.float32)
    current = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY).astype(np.float32)
    # Local high-pass suppresses illumination gradients, not spatial pose.
    reference -= cv2.GaussianBlur(reference, (0, 0), 3)
    current -= cv2.GaussianBlur(current, (0, 0), 3)
    h, w = reference.shape
    center = ((w-1)/2, (h-1)/2)
    tw, th = max(12, round(size[0]*.55)), max(12, round(size[1]*.55))
    if min(reference.std(), current.std()) < .05:
        return {'status': 'UNKNOWN', 'reason': 'TEXTURE_TOO_WEAK'}
    candidates = []
    for angle in range(-20, 21):
        matrix = cv2.getRotationMatrix2D(center, angle, 1)
        rotated = cv2.warpAffine(reference, matrix, (w, h))
        patch = cv2.getRectSubPix(rotated, (tw, th), center)
        if patch.std() < .05:
            continue
        response = cv2.matchTemplate(current, patch, cv2.TM_CCOEFF_NORMED)
        _, score, _, loc = cv2.minMaxLoc(response)
        dx, dy = loc[0]+(tw-1)/2-center[0], loc[1]+(th-1)/2-center[1]
        candidates.append(dict(angle_deg=angle, dx_px=dx, dy_px=dy, score=score))
    if not candidates:
        return {'status': 'UNKNOWN', 'reason': 'NO_MATCH'}
    best = max(candidates, key=lambda c: c['score'])
    competitors = [c['score'] for c in candidates if abs(c['angle_deg']-best['angle_deg']) >= 5]
    return dict(status='UNKNOWN', authority='ADVISORY_ONLY', **best,
                distant_angle_gap=best['score']-max(competitors, default=best['score']),
                search_boundary=abs(best['angle_deg']) == 20,
                note='Template motion only; not calibrated part angle or presence.')


def load_slots(cropper, path):
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f'Unreadable image: {path}')
    board = cropper.register(image)
    if board.alignment_reason != 'OK' or board.alignment_score < float(cropper.config['global_alignment']['minimum_score']):
        raise ValueError(f'Uncertain board registration: {path}')
    result = {}
    for slot in cropper.fixed_slots(board.image_bgr):
        if slot.component_type != 'VRM':
            continue
        x,y,w,h = slot.geometry
        crop = cv2.getRectSubPix(board.image_bgr,(round(w*1.5),round(h*1.5)),(float(x),float(y)))
        result[slot.slot_id] = (crop, (w,h))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', default='143632')
    parser.add_argument('--stamps', nargs='+', default=['135111','141603','142049','142337','143632','144017','144513'])
    parser.add_argument('--output', type=Path, default=ROOT/'runtime/inspection/vrm_texture_motion_20260905')
    args = parser.parse_args()
    cropper = FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    def path(stamp):
        return ROOT/f'runtime/inspection/s22_inspection_roi_20260905_{stamp}.png'
    reference = load_slots(cropper,path(args.reference))
    rows, panels = [], []
    for stamp in args.stamps:
        current = load_slots(cropper,path(stamp))
        for slot,(crop,size) in current.items():
            row = dict(stamp=stamp,slot=slot,**texture_motion(reference[slot][0],crop,size))
            rows.append(row)
            print(json.dumps(row),flush=True)
            # Draw only the measured patch, not a fabricated whole-part mask.
            overlay = crop.copy()
            if 'angle_deg' in row:
                ch,cw = crop.shape[:2]
                center = ((cw-1)/2,(ch-1)/2)
                sw,sh = size[0]*.55,size[1]*.55
                corners = np.float32([[center[0]-sw/2,center[1]-sh/2],
                    [center[0]+sw/2,center[1]-sh/2],[center[0]+sw/2,center[1]+sh/2],
                    [center[0]-sw/2,center[1]+sh/2]])
                matrix = cv2.getRotationMatrix2D(center,row['angle_deg'],1)
                matrix[:,2] += (row['dx_px'],row['dy_px'])
                points = cv2.transform(corners[None],matrix)[0]
                cv2.polylines(overlay,[np.int32(points)],True,(0,220,255),1)
            pair = np.hstack([cv2.resize(reference[slot][0],(180,230)),cv2.resize(overlay,(180,230))])
            panel = cv2.copyMakeBorder(pair,45,0,0,0,cv2.BORDER_CONSTANT)
            cv2.putText(panel,f'{stamp} {slot} REF / MEASURED PATCH',(4,16),0,.38,(255,255,255),1)
            label = f"a={row.get('angle_deg')} dx={row.get('dx_px')} score={row.get('score',0):.3f}"
            cv2.putText(panel,label,(4,34),0,.38,(0,220,255),1)
            panels.append(panel)
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'motion.json').write_text(json.dumps(dict(reference=str(path(args.reference)),
        authority='ADVISORY_ONLY',runtime_enabled=False,robot_command_sent=False,
        conveyor_command_sent=False,rows=rows),indent=2))
    cv2.imwrite(str(args.output/'comparison.jpg'),np.vstack([
        np.hstack(panels[i:i+5]) for i in range(0,len(panels),5)]))


if __name__ == '__main__':
    main()
