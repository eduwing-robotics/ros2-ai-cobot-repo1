"""Fixed contact-window appearance replay; no inferred height or runtime verdict."""
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from build_vrm_fixed_crop_dataset import ROOT, FixedSlotCropper


def contact_features(crop, geometry):
    """Eight fixed windows: corners and side midpoints; no part realignment."""
    h,w=crop.shape[:2]
    _,_,sw,sh=geometry
    gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
    clahe=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8)).apply(gray)
    features={name:[] for name in ('raw','clahe')}
    windows=[]
    for fx,fy in [(-.5,-.5),(0,-.5),(.5,-.5),(.5,0),(.5,.5),(0,.5),(-.5,.5),(-.5,0)]:
        cx,cy=w/2+fx*sw,h/2+fy*sh
        x,y=round(cx-16),round(cy-16)
        if x<0 or y<0 or x+32>w or y+32>h:
            raise ValueError('Contact window clipped')
        windows.append([x,y,32,32])
        for name,img in [('raw',gray),('clahe',clahe)]:
            # Preserve original pixel coordinates; no normalization of placement.
            features[name].append(img[y:y+32,x:x+32].astype(np.float32)/255)
    return {key:np.stack(value) for key,value in features.items()},windows


def main():
    base=ROOT/'runtime/inspection/vrm_seating_pairs'
    selected=json.loads((base/'normal_envelope_audit.json').read_text())['rows']
    historical=json.loads((ROOT/'vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1/saved_scene_validation_last/report.json').read_text())
    lookup={r['scene']:r for r in historical['rows'] if r['slot']=='vrm_05'}
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    prepared=[]
    for row in selected:
        if row['source']=='historical':
            r=lookup[row['scene']]; path=Path(r['source_image']); digest=r['image_sha256']
        else:
            r=json.loads((base/row['scene']/'scene.json').read_text())
            path=Path(r['image']); digest=r['image_sha256']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
        board=cropper.register(cv2.imread(str(path)))
        assert board.alignment_reason=='OK'
        assert board.alignment_score>=float(cropper.config['global_alignment']['minimum_score'])
        slot=next(s for s in cropper.fixed_slots(board.image_bgr) if s.slot_id=='vrm_05')
        cx,cy,w,h=slot.geometry; cw,ch=round(w*1.5),round(h*1.5)
        x,y=round(cx-cw/2),round(cy-ch/2)
        features,windows=contact_features(board.image_bgr[y:y+ch,x:x+cw],slot.geometry)
        prepared.append(dict(row=row,digest=digest,features=features,windows=windows))
    normals=[p for p in prepared if p['row']['source']=='historical' and p['row']['label']=='PASS']
    results=[]
    for p in prepared:
        tracks={}
        for track in ('raw','clahe'):
            refs=[n for n in normals if n['digest']!=p['digest']]
            # Independent window matches are diagnostic; may correspond to different normals.
            distances=np.stack([np.abs(p['features'][track]-n['features'][track]).mean((1,2)) for n in refs])
            nearest=distances.min(0)
            tracks[track]=dict(window_mae=nearest.tolist(),max_window_mae=float(nearest.max()))
        results.append(dict(scene=p['row']['scene'],source=p['row']['source'],label=p['row']['label'],
            tracks=tracks,windows=p['windows'],status='UNKNOWN'))
    summary={track:[min(r['tracks'][track]['max_window_mae'] for r in results if r['label']=='PASS'),
                    max(r['tracks'][track]['max_window_mae'] for r in results if r['label']=='PASS')]
             for track in ('raw','clahe')}
    (base/'contact_pixels_audit.json').write_text(json.dumps(dict(rows=results,normal_score_ranges=summary,
        authority='ADVISORY_ONLY',runtime_changed=False,training=False,robot_command_sent=False,
        conveyor_command_sent=False,limitation='Fixed geometry windows, not detected physical contact points. '
        'Selected retrospective scenes; illumination/texture confounding and mixed nearest normals remain. '
        'No threshold fitting, no per-part alignment, no height measurement.'),indent=2))
    print('normal ranges',summary)
    for r in results:
        if r['label']!='PASS':
            print(r['scene'],r['label'],{t:r['tracks'][t]['max_window_mae'] for t in summary})


if __name__=='__main__':
    main()
