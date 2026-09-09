"""Uncalibrated empty-slot edge candidates; never outputs a physical clearance."""
import hashlib
import json
import cv2
import numpy as np
from build_vrm_fixed_crop_dataset import ROOT, FixedSlotCropper


def candidates(gray):
    gradient=np.abs(cv2.Sobel(cv2.GaussianBlur(gray,(3,3),0),cv2.CV_32F,1,0,ksize=3))
    profile=np.median(gradient[55:185],axis=0)
    peaks=[x for x in range(131,179) if profile[x]>profile[x-1] and profile[x]>=profile[x+1]]
    chosen=[]
    for x in sorted(peaks,key=lambda x:float(profile[x]),reverse=True):
        if all(abs(x-r['x'])>=4 for r in chosen):
            chosen.append(dict(x=int(x),strength=float(profile[x])))
        if len(chosen)==3:
            break
    return chosen


def main():
    base=ROOT/'vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1'
    output=base/'socket_wall_probe'
    if output.exists():
        raise FileExistsError(output)
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    rows,panels=[],[]
    wall_xs=[]
    for stamp in ['20260905_141311','20260906_131700','20260906_132543','20260906_141441']:
        path=ROOT/f'runtime/inspection/s22_inspection_roi_{stamp}.png'
        board=cropper.register(cv2.imread(str(path)))
        if board.alignment_reason!='OK' or board.alignment_score<cropper.config['global_alignment']['minimum_score']:
            raise ValueError('Alignment failed')
        slot=next(s for s in cropper.fixed_slots(board.image_bgr) if s.slot_id=='vrm_04')
        cx,cy,w,h=slot.geometry;cw,ch=round(w*1.5),round(h*1.5)
        x,y=round(cx-cw/2),round(cy-ch/2)
        crop=board.image_bgr[y:y+ch,x:x+cw].copy()
        if crop.shape[:2]!=(241,189):
            raise ValueError('Probe search band requires original fixed geometry')
        empty=stamp in ['20260905_141311','20260906_131700']
        row=dict(source=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),empty_reference=empty,origin=[x,y])
        overlay=crop.copy()
        if empty:
            gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
            local=cv2.createCLAHE(clipLimit=2.,tileGridSize=(8,8)).apply(gray)
            row.update(raw_candidates=candidates(gray),clahe_candidates=candidates(local))
            for n,c in enumerate(row['clahe_candidates']):
                cv2.line(overlay,(c['x'],55),(c['x'],185),(255,255,0),1)
                cv2.putText(overlay,str(n+1),(c['x'],48),0,.35,(255,255,0),1)
            if row['clahe_candidates']:
                wall_xs.append(row['clahe_candidates'][0]['x'])
        else:
            for wx in wall_xs:
                cv2.line(overlay,(wx,55),(wx,185),(255,255,0),1)
            report=json.loads((base/f'fresh_s22_inspection_roi_{stamp}_last/report.json').read_text())
            primary=next(r for r in report['rows'] if r['slot']=='vrm_04')['primary']
            if primary:
                cv2.polylines(overlay,[np.int32(primary['polygon'])],True,(0,170,255),1)
        panel=np.hstack([crop,overlay])
        panel=cv2.copyMakeBorder(panel,30,0,0,0,cv2.BORDER_CONSTANT)
        cv2.putText(panel,stamp+' UNVERIFIED EDGES',(3,20),0,.39,(255,255,255),1)
        panels.append(panel);rows.append(row)
    output.mkdir()
    cv2.imwrite(str(output/'comparison.jpg'),np.vstack(panels))
    result=dict(status='UNKNOWN',runtime_enabled=False,rows=rows,
        limitation='Fixed experimental image search band; gradient may mark inner wall, outer lip or shadow. No physical wall identity, clearance or collision verdict; unchanged part coordinates.')
    (output/'report.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
