"""Multi-band edge agreement probe; no authoritative contour or clearance."""
import argparse
import json
import cv2
import numpy as np
from audit_vrm_texture_motion import load_slots
from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper


def measure(crop, enhanced=False):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if enhanced:
        gray = cv2.createCLAHE(2., (8, 8)).apply(gray)
    gray = cv2.GaussianBlur(gray, (5, 5), 1.).astype(np.float32)
    h, w = gray.shape
    edges = []
    for axis, low, high, sign in [(0,.08,.38,1),(1,.08,.38,1),
                                  (0,.62,.92,-1),(1,.62,.92,-1)]:
        peaks, strengths = [], []
        for f in np.linspace(.25,.75,7):
            center = round((h if axis == 0 else w)*f)
            band = gray[center-2:center+3,:] if axis == 0 else gray[:,center-2:center+3]
            profile = np.median(band, axis=axis)
            gradient = np.gradient(profile)*sign
            a,b = round(len(profile)*low), round(len(profile)*high)
            peak = a+int(np.argmax(gradient[a:b]))
            peaks.append(peak)
            strengths.append(float(gradient[peak]))
        median = float(np.median(peaks))
        edges.append(dict(median_px=median, band_peaks_px=peaks,
                          spread_px=float(np.ptp(peaks)), strengths=strengths))
    return edges


def main():
    parser=argparse.ArgumentParser()
    sources=parser.add_mutually_exclusive_group(required=True)
    sources.add_argument('--stamps', nargs='+')
    sources.add_argument('--images', nargs='+', help='Explicit source paths, including other capture dates')
    parser.add_argument('--slots', nargs='+', help='Only inspect named slots')
    parser.add_argument('--output', required=True)
    args=parser.parse_args()
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    rows, panels=[],[]
    sources=([(stamp,ROOT/f'runtime/inspection/s22_inspection_roi_20260905_{stamp}.png') for stamp in args.stamps]
        if args.stamps else [(str(path).split('/')[-1].removesuffix('.png'),ROOT/path) for path in args.images])
    for stamp,path in sources:
        slots=load_slots(cropper,path)
        for slot,(crop,_) in slots.items():
            if args.slots and slot not in args.slots:
                continue
            raw,enhanced=measure(crop),measure(crop,True)
            delta=[abs(a['median_px']-b['median_px']) for a,b in zip(raw,enhanced)]
            row=dict(stamp=stamp,source=str(path),slot=slot,raw=raw,clahe=enhanced,
                     disagreement_px=delta,status='UNKNOWN',
                     max_band_spread_px=max(e['spread_px'] for e in raw))
            rows.append(row)
            overlay=crop.copy()
            for edges,color in [(raw,(0,255,0)),(enhanced,(0,170,255))]:
                l,t,r,b=[round(e['median_px']) for e in edges]
                cv2.rectangle(overlay,(l,t),(r,b),color,1)
            panel=np.hstack([cv2.resize(crop,(160,210)),cv2.resize(overlay,(160,210))])
            panel=cv2.copyMakeBorder(panel,40,0,0,0,cv2.BORDER_CONSTANT)
            cv2.putText(panel,f'{stamp[-15:]} {slot} RAW / EDGE PROBE',(3,15),0,.36,(255,255,255),1)
            cv2.putText(panel,f'spread {row["max_band_spread_px"]:.0f} CLAHE gap {max(delta):.0f}px',
                        (3,32),0,.36,(255,255,255),1)
            panels.append(panel)
            print(stamp,slot,'spread',row['max_band_spread_px'],'gap',max(delta))
    output=ROOT/args.output
    if not panels:
        raise ValueError('No matching slots')
    output.mkdir(parents=True,exist_ok=False)
    (output/'report.json').write_text(json.dumps(dict(rows=rows,authority='ADVISORY_ONLY',
        runtime_enabled=False,robot_command_sent=False,conveyor_command_sent=False,
        note='Agreement is not proof of component boundary; socket edges may also agree. No thresholds or physical tolerances selected.'),indent=2))
    columns=min(5,len(panels))
    panels.extend([np.zeros_like(panels[0]) for _ in range((-len(panels))%columns)])
    if not cv2.imwrite(str(output/'comparison.jpg'),np.vstack(
        [np.hstack(panels[i:i+columns]) for i in range(0,len(panels),columns)])):
        raise IOError('Failed to save boundary comparison')


if __name__=='__main__':
    main()
