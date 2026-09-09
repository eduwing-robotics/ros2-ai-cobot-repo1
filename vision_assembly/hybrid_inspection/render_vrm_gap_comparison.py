"""Draw existing registered geometry; no new detection or physical metrology."""
import json
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def main():
    folder = ROOT/'runtime/inspection/vrm_wall_repeatability_20260908_v2'
    audit = json.loads((folder/'audit.json').read_text())
    output = folder/'body_groove_comparison.jpg'
    if output.exists():
        raise FileExistsError(output)
    panels = []
    for row in audit['gap_comparison']:
        report_path = Path(row['report'])
        if not report_path.is_absolute():
            report_path = ROOT/report_path
        report = json.loads(report_path.read_text())
        slot = next(s for s in report['slots'] if s['slot_id']==row['slot'])
        boundary = slot['stages']['vrm_boundary']['measured']
        board = cv2.imread(str(report_path.parent/'aligned_board.png'))
        if board is None:
            raise ValueError('Registered image unavailable')
        cy = round(slot['stages']['pose']['measured']['expected_center_px'][1])
        x0,x1,y0,y1 = 0,215,max(0,cy-115),min(board.shape[0],cy+115)
        raw = board[y0:y1,x0:x1].copy()
        marked = raw.copy()
        poly = np.rint(np.asarray(boundary['polygon_board'])-[x0,y0]).astype(np.int32)
        cv2.polylines(marked,[poly],True,(70,220,70),1,cv2.LINE_AA)
        ref = next(s for s in audit['summary'] if s['slot']==row['slot'])
        wallx = round((ref['minimum_x_px']+ref['maximum_x_px'])/2)-x0
        cv2.line(marked,(wallx,0),(wallx,marked.shape[0]-1),(255,200,0),1,cv2.LINE_AA)
        bx = round(row['body_right_x_px'])-x0
        yy = marked.shape[0]//2
        cv2.arrowedLine(marked,(bx,yy),(wallx,yy),(255,255,255),1,cv2.LINE_AA,tipLength=.25)
        pair = []
        for im,title in [(raw,'REGISTERED CROP'),(marked,'MASK + GROOVE REFERENCE')]:
            im = cv2.resize(im,(430,460),interpolation=cv2.INTER_LINEAR)
            im = cv2.copyMakeBorder(im,65,0,0,0,cv2.BORDER_CONSTANT,value=(20,20,20))
            cv2.putText(im,f"{row['stamp']} {row['slot']} | {title}",(8,22),0,.42,(240,240,240),1,cv2.LINE_AA)
            cv2.putText(im,f"Gap {row['signed_groove_gap_interval_px'][0]:.1f}px | NOT calibrated mm",(8,47),0,.5,(0,220,255),1,cv2.LINE_AA)
            pair.append(im)
        panels.append(np.hstack(pair))
    result = np.vstack(panels)
    if not cv2.imwrite(str(output),result):
        raise ValueError('Unable to save visualization')
    print(output)


if __name__=='__main__':
    main()
