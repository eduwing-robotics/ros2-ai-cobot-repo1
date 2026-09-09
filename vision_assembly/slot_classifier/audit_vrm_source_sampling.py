"""Compare original-source sampling to the canonical ROI without changing models."""
import json
import cv2
import numpy as np
from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper, central_rgb


def main():
    out = ROOT/'runtime/inspection/vrm_source_sampling_20260905'
    out.mkdir(parents=True, exist_ok=True)
    c = FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    rows, panels = [], []
    for stamp in ('134637','135454','135111'):
        base = ROOT/f'runtime/inspection/s22_inspection_roi_20260905_{stamp}'
        meta = json.loads(base.with_suffix('.json').read_text())
        # Saved homography uses raw input coordinates, not the rotated preview.
        source = cv2.imread(meta['input_image'])
        b = c.register(cv2.imread(str(base.with_suffix('.png'))))
        if b.alignment_reason != 'OK':
            raise RuntimeError('Registration failed')
        s = next(s for s in c.fixed_slots(b.image_bgr) if s.slot_id=='vrm_02')
        x,y,w,h=s.geometry
        w,h=round(w*.55),round(h*.55)
        # ECC warp maps aligned/reference coordinates into input ROI coordinates.
        affine=np.vstack([b.alignment_warp,[0,0,1]])
        aligned_to_source=np.linalg.inv(np.array(meta['source_to_roi_homography']))@affine
        corners=np.array([[[x-(w-1)/2,y-(h-1)/2],[x+(w-1)/2,y-(h-1)/2],
                           [x+(w-1)/2,y+(h-1)/2],[x-(w-1)/2,y+(h-1)/2]]],np.float32)
        points=cv2.perspectiveTransform(corners,aligned_to_source)[0]
        lengths=[float(np.linalg.norm(points[(i+1)%4]-points[i])) for i in range(4)]
        native_w=max(2,round((lengths[0]+lengths[2])/2)+1)
        native_h=max(2,round((lengths[1]+lengths[3])/2)+1)
        dest=np.array([[0,0],[native_w-1,0],[native_w-1,native_h-1],[0,native_h-1]],np.float32)
        direct=cv2.warpPerspective(source,cv2.getPerspectiveTransform(points,dest),
                                   (native_w,native_h),flags=cv2.INTER_LINEAR)
        old=cv2.cvtColor(np.array(central_rgb(b.image_bgr,s.geometry)),cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(out/f'{stamp}_direct_native.png'),direct)
        row={'capture':stamp,'canonical_size':[w,h],'source_native_size':[native_w,native_h],
             'source_quad':points.tolist(),'source_image':meta['input_image']}
        rows.append(row)
        panel=np.vstack([cv2.resize(old,(360,360),interpolation=cv2.INTER_NEAREST),
                         cv2.resize(direct,(360,360),interpolation=cv2.INTER_NEAREST)])
        cv2.putText(panel,stamp+' ROI / source',(5,25),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,255,255),1)
        panels.append(panel)
    (out/'audit.json').write_text(json.dumps(rows,indent=2)+'\n')
    cv2.imwrite(str(out/'comparison.png'),np.hstack(panels))
    print(json.dumps(rows,indent=2))


if __name__=='__main__':
    main()
