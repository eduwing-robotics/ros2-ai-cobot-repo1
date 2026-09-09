"""Read-only model-input audit; generated images are diagnostic, not training."""
import json
from pathlib import Path
import cv2
import numpy as np
from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper, central_rgb


def main():
    output = ROOT / 'runtime/inspection/vrm02_crop_audit_20260905'
    output.mkdir(parents=True, exist_ok=True)
    cropper = FixedSlotCropper(ROOT / 'vision_assembly/config/full_board_inspection.json')
    panels, records, crops = [], [], []
    for stamp in ('134637', '135454', '135111'):
        path = ROOT / f'runtime/inspection/s22_inspection_roi_20260905_{stamp}.png'
        board = cropper.register(cv2.imread(str(path)))
        slot = next(s for s in cropper.fixed_slots(board.image_bgr) if s.slot_id == 'vrm_02')
        crop = cv2.cvtColor(np.array(central_rgb(board.image_bgr, slot.geometry)), cv2.COLOR_RGB2BGR)
        crops.append(crop)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        record = {'capture': stamp, 'alignment_score': board.alignment_score,
                  'warp': board.alignment_warp.tolist(), 'geometry': slot.geometry,
                  'crop_shape': list(crop.shape), 'gray_mean': float(gray.mean()),
                  'gray_std': float(gray.std()),
                  'laplacian_variance': float(cv2.Laplacian(gray, cv2.CV_64F).var())}
        records.append(record)
        cv2.imwrite(str(output / f'{stamp}_vrm02_native.png'), crop)
        context = slot.crop_bgr.copy()
        cx,cy,w,h = slot.geometry
        x,y = slot.crop_origin_px
        cv2.rectangle(context,(round(cx-w*.275-x), round(cy-h*.275-y)),
                      (round(cx+w*.275-x), round(cy+h*.275-y)),(0,255,255),1)
        panel = np.vstack([cv2.resize(context,(360,360)),cv2.resize(crop,(360,360),interpolation=cv2.INTER_NEAREST)])
        cv2.putText(panel, stamp, (8,25),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,255,255),2)
        panels.append(panel)
    a,b = [cv2.cvtColor(c,cv2.COLOR_BGR2GRAY).astype(float) for c in crops[:2]]
    pair = {'empty_pair_mean_absolute_difference':float(np.abs(a-b).mean()),
            'empty_pair_pixel_correlation':float(np.corrcoef(a.ravel(),b.ravel())[0,1])}
    report = {'records':records,'pair':pair,'note':'Diagnostic metrics only; no threshold or input changes.'}
    (output/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    cv2.imwrite(str(output/'comparison.png'),np.hstack(panels))
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
