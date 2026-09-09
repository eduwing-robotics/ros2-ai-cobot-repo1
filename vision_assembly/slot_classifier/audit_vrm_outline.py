"""Offline edge diagnostic; lines may belong to socket, never a pose verdict."""
import json
import math
import argparse
from pathlib import Path

import cv2
import numpy as np

from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stamps', nargs='+', default=['135111','141311','141603','142049','142337'])
    parser.add_argument('--output', type=Path, default=ROOT / 'runtime/inspection/vrm_outline_audit_20260905')
    parser.add_argument('--foreground-blur',type=float,default=0.0,
                        help='Offline smoothing sensitivity; never alters learned inputs')
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    cropper = FixedSlotCropper(ROOT / 'vision_assembly/config/full_board_inspection.json')
    panels, rows = [], []
    for stamp in args.stamps:
        path = ROOT / f'runtime/inspection/s22_inspection_roi_20260905_{stamp}.png'
        board = cropper.register(cv2.imread(str(path)))
        if board.alignment_reason != 'OK' or board.alignment_score < float(cropper.config['global_alignment']['minimum_score']):
            raise ValueError('Registration failed')
        for slot in cropper.fixed_slots(board.image_bgr):
            if slot.component_type != 'VRM':
                continue
            x, y, w, h = slot.geometry
            crop = cv2.getRectSubPix(board.image_bgr, (round(w*1.5), round(h*1.5)), (float(x), float(y)))
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            local = cv2.createCLAHE(2.0, (8, 8)).apply(gray)
            edges = cv2.Canny(cv2.GaussianBlur(local, (3, 3), 0), 30, 90)
            lines = cv2.HoughLinesP(edges, 1, np.pi/360, 25,
                                   minLineLength=round(min(w,h)*.4), maxLineGap=8)
            overlay, measurements = crop.copy(), []
            # Seed only the component interior; preserve all slot-relative pose.
            ch, cw = crop.shape[:2]
            mask = np.full((ch,cw), cv2.GC_PR_BGD, np.uint8)
            mask[:3] = mask[-3:] = cv2.GC_BGD
            mask[:,:3] = mask[:,-3:] = cv2.GC_BGD
            cv2.rectangle(mask, (round(cw*.3),round(ch*.3)),
                          (round(cw*.7),round(ch*.7)),cv2.GC_PR_FGD,-1)
            cv2.rectangle(mask, (round(cw*.42),round(ch*.42)),
                          (round(cw*.58),round(ch*.58)),cv2.GC_FGD,-1)
            cv2.setRNGSeed(0)
            foreground_input = cv2.GaussianBlur(crop,(0,0),args.foreground_blur) if args.foreground_blur>0 else crop
            cv2.grabCut(foreground_input, mask, None, np.zeros((1,65)),np.zeros((1,65)),5,cv2.GC_INIT_WITH_MASK)
            foreground = np.uint8((mask==cv2.GC_FGD)|(mask==cv2.GC_PR_FGD))*255
            contours,_ = cv2.findContours(foreground,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            fitted = None
            if contours:
                contour = max(contours,key=cv2.contourArea)
                rect = cv2.minAreaRect(contour)
                box = cv2.boxPoints(rect)
                cv2.polylines(overlay,[np.int32(box)],True,(0,255,0),1)
                fitted = dict(rect=[list(rect[0]),list(rect[1]),rect[2]],
                              fill=float(cv2.contourArea(contour)/max(1,rect[1][0]*rect[1][1])))
                # Compare boundary segments against the enclosing rectangle.
                # No image rotation/warping: pose evidence is retained.
                poly = cv2.approxPolyDP(contour, 2.0, True).reshape(-1,2)
                segments = []
                for start,end in zip(poly,np.roll(poly,-1,axis=0)):
                    delta = end-start
                    length = float(np.linalg.norm(delta))
                    if length < min(w,h)*.25:
                        continue
                    angle = math.degrees(math.atan2(float(delta[1]),float(delta[0])))
                    segments.append(dict(length=length,angle=(angle+45)%90-45))
                fitted['boundary_segments'] = segments
                if segments:
                    ordered = sorted(segments,key=lambda s:s['angle'])
                    halfway = sum(s['length'] for s in ordered)/2
                    total = 0
                    for segment in ordered:
                        total += segment['length']
                        if total >= halfway:
                            fitted['boundary_median_deg'] = segment['angle']
                            break
                cv2.imwrite(str(output/f'{stamp}_{slot.slot_id}_mask.png'),foreground)
            if lines is not None:
                for line in lines.reshape(-1, 4):
                    a,b,c,d = map(int, line)
                    angle = math.degrees(math.atan2(d-b,c-a))
                    residual = (angle+45) % 90-45
                    if abs(residual) > 25:
                        continue
                    measurements.append(dict(line=[a,b,c,d], axis_deviation_deg=residual))
                    cv2.line(overlay, (a,b), (c,d), (0,180,255), 1, cv2.LINE_AA)
            row = dict(stamp=stamp, slot=slot.slot_id, lines=measurements, grabcut=fitted,
                       status='UNKNOWN', note='Unassigned edges: socket/part ambiguity; not physical angle measurement')
            rows.append(row)
            pair = np.hstack([cv2.resize(crop,(240,300)),cv2.resize(overlay,(240,300))])
            panel = cv2.copyMakeBorder(pair,30,0,0,0,cv2.BORDER_CONSTANT)
            cv2.putText(panel, f'{stamp} {slot.slot_id} RAW / EDGES', (5,20),0,.5,(255,255,255),1)
            panels.append(panel)
    cv2.imwrite(str(output/'comparison.jpg'), np.vstack([np.hstack(panels[i:i+5]) for i in range(0,len(panels),5)]))
    (output/'edges.json').write_text(json.dumps(dict(authority='ADVISORY_ONLY', foreground_blur=args.foreground_blur, rows=rows),indent=2))
    print(output)


if __name__ == '__main__':
    main()
