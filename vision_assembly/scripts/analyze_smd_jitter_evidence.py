#!/usr/bin/env python3
"""Offline paired-frame evidence; no ROS, commands, calibration or recipe writes."""
import argparse,json
from pathlib import Path
import cv2,numpy as np
from ultralytics import YOLO
from smd_set_selection import select_smd_set
from smd_terminal_axis import terminal_axis_from_obb,unwrap_axis_angles_deg


def translation(reference,current):
    margin=6
    template=reference[margin:-margin,margin:-margin].astype(np.float32)
    scores=cv2.matchTemplate(current.astype(np.float32),template,cv2.TM_CCOEFF_NORMED)
    _,score,_,peak=cv2.minMaxLoc(scores);x,y=peak
    if x in (0,scores.shape[1]-1) or y in (0,scores.shape[0]-1):
        raise ValueError('tracking peak reaches search boundary')
    def offset(a,b,c):
        denom=float(a)-2*float(b)+float(c)
        if denom>=-1e-8:return 0.
        return float(np.clip(.5*(float(a)-float(c))/denom,-.5,.5))
    dx=offset(scores[y,x-1],scores[y,x],scores[y,x+1])
    dy=offset(scores[y-1,x],scores[y,x],scores[y+1,x])
    return dict(shift_source_px=[x+dx-margin,y+dy-margin],correlation=float(score))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    a=parser.parse_args();root=Path(__file__).resolve().parents[1]
    cfg=json.loads((root/'config/smd_section_view.json').read_text())
    captures=json.loads((a.directory/'capture.json').read_text())
    model=YOLO(str(root/'models/smd_obb/pilot_06/weights/best.pt'))
    first=cv2.imread(str(a.directory/'000_raw.png'));ih,iw=first.shape[:2];w,h=cfg['canonical_size']
    H=cv2.getPerspectiveTransform(np.float32(cfg['section_polygon_pixel'])*np.float32([iw,ih])/np.float32(cfg['source_image_size']),np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]]));inv=np.linalg.inv(H)
    def detect(im):
        rect=cv2.warpPerspective(im,H,(w,h),flags=cv2.INTER_CUBIC)
        p=model.predict(rect,imgsz=960,conf=.5,device='0',verbose=False)[0]
        items=[] if p.obb is None else [dict(box=b,center=b.mean(0),confidence=float(c)) for b,c in zip(p.obb.xyxyxyxy.cpu().numpy(),p.obb.conf.cpu().numpy())]
        selected=select_smd_set(items,cfg['set_layout'],1,consumed_prefix_count=1)
        result={}
        for i,item in enumerate(selected,1):
            if item is None:continue
            axis=terminal_axis_from_obb(item['box'],minimum_axis_ratio=1.0)
            native=cv2.perspectiveTransform(item['box'].astype(np.float32).reshape(-1,1,2),inv)[:,0]
            center=cv2.perspectiveTransform(np.float32([[item['center']]]),inv)[0,0]
            result[i]=dict(center_canonical_px=item['center'].tolist(),center_source_px=center.tolist(),box_source_px=native.tolist(),angle_canonical_deg=float(axis['angle_canonical_deg']),axis_ratio=float(axis['axis_ratio']),axis_gate_passed=bool(axis['axis_ratio']>=1.35),confidence=item['confidence'])
        return result
    seed=detect(first);centers={i:np.rint(r['center_source_px']).astype(int) for i,r in seed.items()}
    def crop(im,i):
        x,y=centers[i];r=im[y-24:y+24,x-22:x+22]
        if r.shape[:2]!=(48,44):raise RuntimeError('ROI outside image')
        return r
    refs={i:cv2.cvtColor(crop(first,i),cv2.COLOR_BGR2GRAY) for i in seed}
    # Check Template tracking sign and subpixel recovery on a known synthetic translation.
    rng=np.random.default_rng(42);test=cv2.GaussianBlur(rng.normal(128,30,(128,128)).astype(np.float32),(5,5),1)
    known=np.float32([[1,0,.7],[0,1,-.4]])
    shifted=cv2.warpAffine(test,known,(128,128),borderMode=cv2.BORDER_REFLECT)
    check=translation(test[32:96,32:96],shifted[32:96,32:96])
    if np.linalg.norm(np.asarray(check['shift_source_px'])-[.7,-.4])>.12:raise RuntimeError('template translation self-check failed')
    repeated=[detect(first) for _ in range(3)]
    determinism=max(float(np.max(np.abs(np.asarray(run[i]['center_source_px'])-seed[i]['center_source_px']))) for run in repeated for i in seed)
    rows=[]
    for capture in captures:
        for kind,suffix in [('raw','raw.png'),('jpeg','jpeg.jpg')]:
            im=cv2.imread(str(a.directory/f"{capture['index']:03d}_{suffix}"))
            if im is None:raise RuntimeError('missing captured frame')
            try:found=detect(im);failure=None
            except (ValueError,RuntimeError,AttributeError) as exc:found={};failure=str(exc)
            for i in seed:
                gray=cv2.cvtColor(crop(im,i),cv2.COLOR_BGR2GRAY)
                row=dict(index=capture['index'],kind=kind,instance=i,brightness=float(gray.mean()),sharpness=float(cv2.Laplacian(gray,cv2.CV_64F).var()))
                if i in found:row.update(found[i])
                else:row['detection_error']=failure
                try:row.update(translation(refs[i],gray))
                except (cv2.error,ValueError) as exc:row['tracking_error']=str(exc)
                rows.append(row)
    stats={}
    for i in seed:
        stats[i]={}
        for kind in ('raw','jpeg'):
            selected=[r for r in rows if r['instance']==i and r['kind']==kind]
            detected=[r for r in selected if 'center_source_px' in r]
            tracking=[r for r in selected if 'shift_source_px' in r]
            quality_tracking=[r for r in tracking if r['correlation']>=.98]
            summary=dict(total_frames=len(selected),detected_frames=len(detected),tracking_frames=len(tracking),tracking_correlation_min=min((r['correlation'] for r in tracking),default=None),tracking_high_correlation_frames=len(quality_tracking))
            if detected:
                c=np.array([r['center_source_px'] for r in detected]);canonical=np.array([r['center_canonical_px'] for r in detected]);angle=unwrap_axis_angles_deg([r['angle_canonical_deg'] for r in detected])
                summary.update(center_span_source_px=np.ptp(c,axis=0).tolist(),center_span_canonical_px=np.ptp(canonical,axis=0).tolist(),angle_span_deg=float(np.ptp(angle)),axis_gate_pass_frames=sum(r['axis_gate_passed'] for r in detected))
                if len(detected)==60:
                    chunks=np.split(canonical,2)
                    summary['consecutive_30frame_center_spans']=[np.ptp(chunk,axis=0).tolist() for chunk in chunks]
            summary['tracking_reliable']=len(quality_tracking)>=max(2,.8*len(selected))
            summary['tracking_span_source_px']=np.ptp([r['shift_source_px'] for r in quality_tracking],axis=0).tolist() if summary['tracking_reliable'] else None
            if tracking:summary['unvalidated_tracking_span_source_px']=np.ptp([r['shift_source_px'] for r in tracking],axis=0).tolist()
            paired=[r for r in detected if 'shift_source_px' in r and r.get('correlation',0)>=.98]
            summary['center_minus_tracking_span_source_px']=np.ptp([np.array(r['center_source_px'])-r['shift_source_px'] for r in paired],axis=0).tolist() if summary['tracking_reliable'] and len(paired)>=2 else None
            stats[i][kind]=summary
        pairs=[]
        for index in range(len(captures)):
            pair=[r for r in rows if r['instance']==i and r['index']==index and 'center_source_px' in r]
            if len(pair)==2:pairs.append(np.array(pair[0]['center_source_px'])-pair[1]['center_source_px'])
        stats[i]['paired_raw_jpeg_center_difference_max_source_px']=np.max(np.abs(pairs),axis=0).tolist() if pairs else None
    # Worst raw model-X frames: plain source crop beside exact same crop with box.
    panels=[]
    for i in seed:
        candidates=[r for r in rows if r['instance']==i and r['kind']=='raw' and 'center_source_px' in r]
        if not candidates:continue
        selected=[min(candidates,key=lambda r:r['center_source_px'][0]),max(candidates,key=lambda r:r['center_source_px'][0])]
        line=[]
        for r in selected:
            im=cv2.imread(str(a.directory/f"{r['index']:03d}_raw.png"));plain=crop(im,i)
            x,y=centers[i];origin=np.array([x-22,y-24]);scale=5
            for overlay in (False,True):
                panel=cv2.resize(plain,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
                if overlay:
                    poly=np.rint((np.array(r['box_source_px'])-origin)*scale).astype(np.int32)
                    cv2.polylines(panel,[poly],True,(0,255,0),1)
                    c=tuple(np.rint((np.array(r['center_source_px'])-origin)*scale).astype(int))
                    cv2.drawMarker(panel,c,(0,0,255),cv2.MARKER_CROSS,18,1)
                header=np.full((34,panel.shape[1],3),25,np.uint8)
                cv2.putText(header,f"SMD{i} frame{r['index']:02d} {'OBB' if overlay else 'RAW'}",(5,23),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
                line.append(np.vstack([header,panel]))
        panels.append(np.hstack(line))
    cv2.imwrite(str(a.directory/'boundary_box_comparison.jpg'),np.vstack(panels))
    output=dict(diagnostic_only=True,robot_commands_sent=0,physical_alignment_verified=False,image_size=[iw,ih],source_frames=len(captures),same_image_inference_center_difference_max_px=determinism,template_tracking_synthetic_check=check,statistics=stats,rows=rows,limitations=['Template tracking measures local appearance translation, not independently measured physical terminal centers.','Subpixel native imagery and interpolation limit physical boundary accuracy.','This report cannot validate hand-eye/TCP calibration or authorize motion.'])
    (a.directory/'all_parts_evidence.json').write_text(json.dumps(output,indent=2))
    print(json.dumps({k:v for k,v in output.items() if k not in ('rows','limitations')},indent=2),flush=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(4,2,figsize=(12,10),sharex=True)
    for rowindex,i in enumerate(seed):
        for axis in (0,1):
            ax=axes[rowindex,axis]
            for kind,color in [('raw','tab:red'),('jpeg','tab:orange')]:
                selected=[r for r in rows if r['instance']==i and r['kind']==kind and 'center_source_px' in r]
                c=np.array([r['center_source_px'][axis] for r in selected]);ax.plot([r['index'] for r in selected],c-np.median(c),label=f'{kind} OBB',color=color,alpha=.8)
            selected=[r for r in rows if r['instance']==i and r['kind']=='raw' and r.get('correlation',0)>=.98]
            if stats[i]['raw']['tracking_reliable']:
                shift=np.array([r['shift_source_px'][axis] for r in selected]);ax.plot([r['index'] for r in selected],shift-np.median(shift),label='raw image tracking',color='tab:blue')
            else:ax.text(.02,.92,'Independent tracking: insufficient confidence',transform=ax.transAxes,fontsize=7)
            ax.set_title(f'SMD-{i:02d} source {"XY"[axis]}');ax.set_ylabel('native pixels, median centered');ax.grid(alpha=.25)
    axes[0,0].legend(fontsize=8);axes[-1,0].set_xlabel('paired frame');axes[-1,1].set_xlabel('paired frame')
    fig.tight_layout();fig.savefig(a.directory/'center_vs_image_tracking.png',dpi=160);plt.close(fig)

if __name__=='__main__':main()
