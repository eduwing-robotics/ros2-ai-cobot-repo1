#!/usr/bin/env python3
"""Offline SMD-02 edge experiment. Never produces an executable robot target.

Assumes approximately horizontal terminal bands in this fixed close view.
Finds the outer top/bottom brightness edges and left/right colour-body edges.
Parameters are fixed across all saved frames; no temporal smoothing is used.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from smd_terminal_axis import canonical_axis_angle_deg, terminal_axis_from_bgr, unwrap_axis_angles_deg


def peak(profile, lo, hi):
    k = lo + int(np.argmax(profile[lo:hi]))
    if k == lo or k == hi-1:
        raise ValueError('edge peak touches search bound')
    a,b,c = map(float,profile[k-1:k+2])
    denom = a-2*b+c
    delta = .5*(a-c)/denom if denom < -1e-6 else 0.
    return k + float(np.clip(delta,-.5,.5)), b


def fit_line(points):
    points = np.asarray(points)
    if len(points) < 15:
        raise ValueError('insufficient edge support')
    keep = np.ones(len(points),bool)
    for _ in range(3):
        slope,offset = np.polyfit(points[keep,0],points[keep,1],1)
        error = abs(points[:,1]-(slope*points[:,0]+offset))
        keep = error < max(1.,3*float(np.median(error)))
    if keep.sum() < 15 or np.median(error[keep]) > 1.:
        raise ValueError('edge line is not coherent')
    return float(slope),float(offset),int(keep.sum())


def estimate(rect, center):
    cx,cy = np.rint(center).astype(int)
    crop = rect[cy-45:cy+46,cx-45:cx+46]
    if crop.shape[:2] != (91,91):
        raise ValueError('ROI outside image')
    gray = cv2.GaussianBlur(cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY).astype(np.float32),(5,5),1.)
    sat = cv2.GaussianBlur(cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)[:,:,1].astype(np.float32),(5,5),1.)
    gy = cv2.Sobel(gray,cv2.CV_32F,0,1,ksize=3)/8
    gx = cv2.Sobel(sat,cv2.CV_32F,1,0,ksize=3)/8
    edges=[]
    strengths=[]
    # The outside edges of the light terminal bands have opposite polarities.
    for low,high,sign in [(10,35,1),(55,80,-1)]:
        points=[]
        for x in range(33,58):
            try:
                y,strength=peak(sign*gy[:,x],low,high)
                if strength >= .6:
                    points.append((x-45,y-45));strengths.append(strength)
            except ValueError:
                pass
        try:
            edges.append(fit_line(points))
        except ValueError as exc:
            raise ValueError(('top terminal: ' if sign==1 else 'bottom terminal: ')+str(exc)) from exc
    sides=[]
    for low,high,sign in [(10,37,1),(53,80,-1)]:
        points=[]
        for y in range(35,56):
            try:
                x,strength=peak(sign*gx[y,:],low,high)
                if strength >= .6:
                    points.append((y-45,x-45))
            except ValueError:
                pass
        try:
            sides.append(fit_line(points))
        except ValueError as exc:
            raise ValueError(('left body: ' if sign==1 else 'right body: ')+str(exc)) from exc
    m0,b0,_=edges[0];m1,b1,_=edges[1]
    xoff=(sides[0][1]+sides[1][1])/2
    yoff=((m0+m1)*xoff+b0+b1)/2
    angle=canonical_axis_angle_deg(np.degrees(np.arctan((m0+m1)/2))+90)
    disagreement=abs(np.degrees(np.arctan(m0)-np.arctan(m1)))
    length=(m1*xoff+b1)-(m0*xoff+b0)
    width=sides[1][1]-sides[0][1]
    if not (30<length<75 and 20<width<65 and disagreement<8):
        raise ValueError('terminal geometry inconsistent')
    return dict(center=[cx+xoff,cy+yoff],angle=float(angle),
                terminal_lines=edges,body_sides=sides,roi=[int(cx),int(cy)],
                length_px=length,width_px=width,edge_angle_disagreement_deg=disagreement,
                edge_strength_median=float(np.median(strengths)))


def summarize(rows):
    valid=[r for r in rows if 'center' in r]
    if not valid:
        return dict(valid=0,total=len(rows))
    c=np.array([r['center'] for r in valid]);a=unwrap_axis_angles_deg([r['angle'] for r in valid])
    return dict(valid=len(valid),total=len(rows),center_median=np.median(c,axis=0).tolist(),
                center_span=np.ptp(c,axis=0).tolist(),center_std=np.std(c,axis=0).tolist(),
                angle_median=float(np.median(a)),angle_span=float(np.ptp(a)),angle_std=float(np.std(a)))


def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);args=p.parse_args()
    data=json.loads((args.directory/'analysis.json').read_text())
    cfg=json.loads((Path(__file__).resolve().parents[1]/'config/smd_section_view.json').read_text())
    w,h=cfg['canonical_size'];dst=np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
    # Fixed ROI from pre-existing diagnostic; no per-frame OBB centre tracking.
    center=np.array(data['roi_center']);results=[];legacy=[];panels=[]
    for record in data['capture']:
        index=record['index']
        for kind,suffix in [('raw','raw.png'),('jpeg','jpeg.jpg')]:
            image=cv2.imread(str(args.directory/f'{index:03d}_{suffix}'))
            scale=np.float32([image.shape[1],image.shape[0]])/cfg['source_image_size']
            H=cv2.getPerspectiveTransform(np.float32(cfg['section_polygon_pixel'])*scale.astype(np.float32),dst)
            rect=cv2.warpPerspective(image,H,(w,h),flags=cv2.INTER_CUBIC)
            row=dict(index=index,kind=kind)
            try: row.update(estimate(rect,center))
            except ValueError as exc: row['error']=str(exc)
            results.append(row)
            old=dict(index=index,kind=kind)
            try: old.update(terminal_axis_from_bgr(rect,center))
            except ValueError as exc: old['error']=str(exc)
            legacy.append(old)
            if index in (0,1,15,52):
                cx,cy=np.rint(center).astype(int)
                panel=cv2.resize(rect[cy-45:cy+46,cx-45:cx+46],(273,273),interpolation=cv2.INTER_NEAREST)
                if 'center' in row:
                    for m,b,_ in row['terminal_lines']:
                        cv2.line(panel,(60,int((m*(-25)+b+45)*3)),(210,int((m*25+b+45)*3)),(0,255,0),1)
                    pt=tuple(np.rint((np.array(row['center'])-[cx-45,cy-45])*3).astype(int))
                    cv2.drawMarker(panel,pt,(0,0,255),cv2.MARKER_CROSS,15,1)
                cv2.putText(panel,f'{index:03d} {kind} '+('OK' if 'center' in row else 'FAIL'),(8,20),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
                panels.append(panel)
    summary={}
    for kind in ('raw','jpeg'):
        rows=[r for r in results if r['kind']==kind]
        summary[kind]=summarize(rows)
        summary[kind]['first30']=summarize(rows[:30]);summary[kind]['last30']=summarize(rows[30:])
        summary[kind]['legacy_colour_axis_valid']=sum('error' not in r for r in legacy if r['kind']==kind)
    output=dict(diagnostic_only=True,robot_motion_authorized=False,summary=summary,results=results,legacy=legacy)
    (args.directory/'terminal_edge_comparison.json').write_text(json.dumps(output,indent=2))
    cv2.imwrite(str(args.directory/'terminal_edge_comparison.jpg'),np.vstack([np.hstack(panels[i:i+2]) for i in range(0,len(panels),2)]))
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
