"""Native-pixel SMD01 outline diagnostic, no pose normalization or runtime vote."""
import json
from pathlib import Path
import cv2
import numpy as np
from preprocessor_and_cropper import FixedSlotCropper

ROOT = Path(__file__).resolve().parents[2]


def bright_outline(image, threshold):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask = np.uint8(gray >= threshold) * 255
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask)
    h, w = gray.shape
    choices = [i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= 40
               and np.linalg.norm(centers[i] - [w/2, h/2]) < min(h, w)*.4]
    if not choices:
        return None
    idx = min(choices, key=lambda i: np.linalg.norm(centers[i] - [w/2, h/2]))
    contours, _ = cv2.findContours(np.uint8(labels == idx)*255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour = max(contours, key=cv2.contourArea)
    return contour


def main():
    evidence = json.loads((ROOT / 'runtime/inspection/pose_normal_defect_separation_20260907.json').read_text())
    out = ROOT / 'runtime/inspection/smd01_outline_audit_20260907'
    out.mkdir(exist_ok=False)
    cropper = FixedSlotCropper(ROOT / 'vision_assembly/config/full_board_inspection.json')
    tiles, results = [], []
    for index, row in enumerate(evidence['rows']):
        path = ROOT / 'runtime/inspection' / row['source'] / 'aligned_board.png'
        board = cv2.imread(str(path))
        if board is None:
            raise RuntimeError(f'Cannot read {path}')
        slot = next(s for s in cropper.fixed_slots(board) if s.slot_id == 'smd_capacitor_01')
        cx, cy, sx, sy = slot.geometry
        x, y = int(cx)-90, int(cy)-70
        crop = board[y:y+140, x:x+180].copy()
        if crop.shape[:2] != (140, 180):
            raise RuntimeError('Invalid crop')
        overlay = crop.copy()
        cv2.rectangle(overlay, (round(cx-sx/2-x), round(cy-sy/2-y)),
                      (round(cx+sx/2-x), round(cy+sy/2-y)), (255, 150, 0), 1)
        probes = []
        for t, color in [(100,(0,255,255)), (130,(0,255,0)), (160,(255,0,255))]:
            contour = bright_outline(crop, t)
            if contour is None:
                probes.append(dict(threshold=t, found=False))
                continue
            bx, by, bw, bh = cv2.boundingRect(contour)
            cv2.drawContours(overlay,[contour],-1,color,1)
            probes.append(dict(threshold=t, found=True, bbox_native_px=[bx,by,bw,bh],
                               area_px=cv2.contourArea(contour)))
        gray = cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
        local = cv2.createCLAHE(clipLimit=2., tileGridSize=(8,8)).apply(gray)
        edges = cv2.cvtColor(cv2.Canny(local,50,120),cv2.COLOR_GRAY2BGR)
        panels = np.hstack([crop,overlay,edges])
        panels = cv2.resize(panels,None,fx=2,fy=2,interpolation=cv2.INTER_NEAREST)
        tile = cv2.copyMakeBorder(panels,35,0,0,0,cv2.BORDER_CONSTANT,value=(25,25,25))
        cv2.putText(tile,f"{index+1} {row['truth']} | ORIGINAL / BRIGHT CONTOURS + NOMINAL ROI / CLAHE EDGES",
                    (8,24),cv2.FONT_HERSHEY_SIMPLEX,.55,(230,230,230),1,cv2.LINE_AA)
        tiles.append(tile)
        results.append(dict(source=str(path),truth=row['truth'],crop_origin=[x,y],probes=probes))
    cv2.imwrite(str(out/'comparison.png'),np.vstack(tiles))
    payload = dict(rows=results, status='DIAGNOSTIC_ONLY',
                   limitation='Blue rectangle is nominal component ROI, NOT detected socket wall. Bright contour may exclude metal ends or merge highlights. No clearance/height judgement or runtime changes.')
    (out/'audit.json').write_text(json.dumps(payload,indent=2))
    print(json.dumps(payload,indent=2))


if __name__ == '__main__':
    main()
