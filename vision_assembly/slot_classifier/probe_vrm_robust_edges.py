"""Offline multi-peak line fitting. All evidence remains UNKNOWN/advisory."""
import argparse
import hashlib
import json
import cv2
import numpy as np
from audit_vrm_texture_motion import load_slots
from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper


def fit_candidates(samples):
    """Deterministic two-point consensus; one vote per independent scan band."""
    points = [(i, y, x, strength) for i,(y,peaks) in enumerate(samples)
              for x,strength in peaks]
    hypotheses=[]
    for p in points:
        for q in points:
            if q[0]-p[0] < 3:
                continue
            slope=(q[2]-p[2])/(q[1]-p[1])
            if abs(slope)>np.tan(np.deg2rad(20)):
                continue
            intercept=p[2]-slope*p[1]
            votes=[]
            for y,peaks in samples:
                matches=[(abs(x-slope*y-intercept),s) for x,s in peaks
                         if abs(x-slope*y-intercept)<=2]
                if matches:
                    votes.append(min(matches))
            if len(votes)>=5:
                hypotheses.append(dict(slope=float(slope),intercept=float(intercept),
                    support=len(votes),strength=float(sum(v[1] for v in votes)),
                    residual=float(np.mean([v[0] for v in votes]))))
    if not hypotheses:
        return dict(status='UNKNOWN',reason='INSUFFICIENT_LINE_SUPPORT')
    hypotheses.sort(key=lambda h:(h['support'],h['strength'],-h['residual']),reverse=True)
    best=hypotheses[0]
    # Competing lines: compare their separation across the observed interval.
    ys=np.array([s[0] for s in samples])
    rivals=[h for h in hypotheses[1:] if
            np.median(np.abs((h['slope']-best['slope'])*ys+h['intercept']-best['intercept']))>4]
    rival=rivals[0] if rivals else None
    ambiguous=bool(rival and rival['support']>=best['support']-1 and
                   rival['strength']>=best['strength']*.8)
    alternatives=[]
    for hypothesis in hypotheses:
        if all(np.max(np.abs((hypothesis['slope']-a['slope'])*ys+
                             hypothesis['intercept']-a['intercept']))>2 for a in alternatives):
            alternatives.append(hypothesis)
        if len(alternatives)==4:
            break
    return dict(status='UNKNOWN',reason='COMPETING_LINES' if ambiguous else 'UNVERIFIED_LINE',
                candidate=best,competitor=rival,ambiguous=ambiguous,alternatives=alternatives)


def measure(crop, enhanced):
    gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
    if enhanced:
        gray=cv2.createCLAHE(2.,(8,8)).apply(gray)
    gray=cv2.GaussianBlur(gray,(5,5),1.).astype(np.float32)
    h,w=gray.shape
    edges=[]
    for axis,low,high,sign in [(0,.08,.38,1),(1,.08,.38,1),(0,.62,.92,-1),(1,.62,.92,-1)]:
        samples=[]
        for fraction in np.linspace(.25,.75,9):
            center=round((h if axis==0 else w)*fraction)
            band=gray[center-2:center+3,:] if axis==0 else gray[:,center-2:center+3]
            gradient=np.gradient(np.median(band,axis=axis))*sign
            a,b=round(len(gradient)*low),round(len(gradient)*high)
            peaks=[]
            for x in sorted(range(a,b),key=lambda x:gradient[x],reverse=True):
                if gradient[x]<1. or any(abs(x-p[0])<5 for p in peaks):
                    continue
                if gradient[x]<gradient[x-1] or gradient[x]<gradient[x+1]:
                    continue
                peaks.append((x,float(gradient[x])))
                if len(peaks)==3:
                    break
            samples.append((center,peaks))
        edges.append(dict(axis=axis,samples=samples,**fit_candidates(samples)))
    return edges


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--stamps',nargs='+',required=True)
    p.add_argument('--output',required=True)
    args=p.parse_args()
    output=ROOT/args.output
    if output.exists():
        raise ValueError('Refusing to overwrite prior experiment')
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    rows,panels=[],[]
    for stamp in args.stamps:
        source=ROOT/f'runtime/inspection/s22_inspection_roi_20260905_{stamp}.png'
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        for slot,(crop,_) in load_slots(cropper,source).items():
            raw,clahe=measure(crop,False),measure(crop,True)
            overlay=crop.copy()
            for edges,color in [(raw,(0,255,0)),(clahe,(0,180,255))]:
                for e in edges:
                    line=e.get('candidate')
                    if not line:
                        continue
                    points=[]
                    for y in (e['samples'][0][0],e['samples'][-1][0]):
                        x=round(line['slope']*y+line['intercept'])
                        points.append((x,y) if e['axis']==0 else (y,x))
                    cv2.line(overlay,*points,color,1)
            reasons=[]
            for a,b in zip(raw,clahe):
                if 'candidate' not in a or 'candidate' not in b:
                    reasons.append('INSUFFICIENT_LINE_SUPPORT')
                elif a['ambiguous'] or b['ambiguous']:
                    reasons.append('COMPETING_LINES')
                else:
                    positions=[s[0] for s in a['samples']]
                    gap=max(abs((a['candidate']['slope']-b['candidate']['slope'])*y+
                        a['candidate']['intercept']-b['candidate']['intercept']) for y in positions)
                    reasons.append('RAW_CLAHE_DISAGREEMENT' if gap>3 else 'UNVERIFIED_LINE')
            rows.append(dict(stamp=stamp,slot=slot,image_sha256=digest,raw=raw,clahe=clahe,
                             reasons=reasons,status='UNKNOWN'))
            panel=np.hstack([cv2.resize(crop,(160,210)),cv2.resize(overlay,(160,210))])
            panel=cv2.copyMakeBorder(panel,40,0,0,0,cv2.BORDER_CONSTANT)
            cv2.putText(panel,f'{stamp} {slot} LINE CANDIDATES',(3,15),0,.36,(255,255,255),1)
            count=sum(r=='UNVERIFIED_LINE' for r in reasons)
            cv2.putText(panel,f'{count}/4 consistent - NOT VALIDATED',(3,32),0,.36,(255,255,255),1)
            panels.append(panel)
            print(stamp,slot,reasons,flush=True)
    output.mkdir(parents=True)
    (output/'report.json').write_text(json.dumps(dict(authority='ADVISORY_ONLY',runtime_enabled=False,
        rows=rows,robot_command_sent=False,conveyor_command_sent=False,
        limitations='Heuristic line quality thresholds are not defect tolerances. Coherent socket edges can still be wrong. No component warping, calibrated angle, clearance or height measurement.'),indent=2))
    cv2.imwrite(str(output/'comparison.jpg'),np.vstack([np.hstack(panels[i:i+5]) for i in range(0,len(panels),5)]))


if __name__=='__main__':
    main()
