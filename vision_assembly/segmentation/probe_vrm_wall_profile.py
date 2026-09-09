"""Local raw/CLAHE edge-track diagnostic; no motion or metric clearance."""
import json
import cv2
import numpy as np
from build_vrm_fixed_crop_dataset import ROOT, FixedSlotCropper


def track(gray):
    gradient=np.abs(cv2.Sobel(cv2.GaussianBlur(gray,(3,3),0),cv2.CV_32F,1,0))
    points=[]
    for y in range(55,196,10):
        profile=np.median(gradient[y-3:y+4,152:168],axis=0)
        if profile.max()>0:
            points.append([int(np.argmax(profile))+152,y])
    return points


def main():
    base=ROOT/'vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1/socket_wall_probe'
    out=base/'profile'
    if out.exists():
        raise FileExistsError(out)
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    panels=[];rows=[]
    for stamp in ['20260905_141311','20260906_131700']:
        path=ROOT/f'runtime/inspection/s22_inspection_roi_{stamp}.png'
        board=cropper.register(cv2.imread(str(path)))
        if board.alignment_reason!='OK' or board.alignment_score<cropper.config['global_alignment']['minimum_score']:
            raise ValueError('Alignment failed')
        crop=board.image_bgr[305:546,3:192].copy()
        gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
        raw=track(gray);clahe=track(cv2.createCLAHE(clipLimit=2.,tileGridSize=(8,8)).apply(gray))
        overlay=crop.copy()
        for points,color in [(raw,(0,170,255)),(clahe,(255,255,0))]:
            cv2.polylines(overlay,[np.int32(points)],False,color,1)
        if len(raw)!=len(clahe) or not raw:
            raise ValueError('No comparable tracks')
        delta=np.abs(np.array(raw)[:,0]-np.array(clahe)[:,0])
        rows.append(dict(source=str(path),raw=raw,clahe=clahe,
            max_raw_clahe_disagreement_px=int(delta.max()),
            raw_x_span_px=int(np.ptp(np.array(raw)[:,0])),
            boundary_hits=sum(x in [152,167] for x,y in raw)))
        panel=np.hstack([crop,overlay]);panel=cv2.copyMakeBorder(panel,30,0,0,0,cv2.BORDER_CONSTANT)
        cv2.putText(panel,stamp+' RAW orange / CLAHE cyan',(2,20),0,.33,(255,255,255),1)
        panels.append(panel)
    out.mkdir()
    cv2.imwrite(str(out/'comparison.jpg'),np.vstack(panels))
    result=dict(status='UNKNOWN',runtime_enabled=False,rows=rows,
        limitation='Strongest local row edge may jump between wall and texture; search band is experimental. No slope correction, calibrated uncertainty, mm gap, or per-part alignment.')
    (out/'report.json').write_text(json.dumps(result,indent=2))
    for r in rows:
        print(r['source'],r['max_raw_clahe_disagreement_px'],r['raw_x_span_px'],r['boundary_hits'])


if __name__=='__main__':
    main()
