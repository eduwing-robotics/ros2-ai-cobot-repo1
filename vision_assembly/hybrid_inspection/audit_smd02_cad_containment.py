"""Offline fixed CAD boundary / bright silhouette distance, not a runtime vote."""
import json
import tempfile
from pathlib import Path

import cv2
import numpy as np
from audit_smd02_position_overlap import SOURCES
from audit_smd01_outline import bright_outline
from extract_unity_socket_candidates import extract
from preprocessor_and_cropper import FixedSlotCropper

ROOT = Path(__file__).resolve().parents[2]


def main():
    base=ROOT/'runtime/inspection'
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    spec=json.loads((ROOT/'vision_assembly/config/unity_socket_clearance.json').read_text())
    layout=json.loads((ROOT/'vision_assembly/config/board_layout_from_unity.json').read_text())
    scale=layout['board']['unity_to_physical_scale']
    mesh=Path('/home/hc/My project/Assets/반도체 기판 모델링(Unity)/ASt/motherBoard.obj')
    faces=[f for f in extract(mesh,spec) if f['component_type']=='SMD Capacitor']
    polygons=[]
    for f in faces:
        p=np.array(f['polygon_obj_xz_mm'],dtype=np.float32)
        p[:,0]=(p[:,0]*scale['x']/139+.5)*1600
        p[:,1]=(p[:,1]*scale['y']/110+.5)*1266
        polygons.append(p)
    # Select once from fixed nominal slot, never from detected component pose.
    placement=next(p for p in cropper.layout['placements'] if p['slot_id']=='smd_capacitor_02')
    c=placement['center_board_mm']
    center=np.array([(-c['x']/139+.5)*1600,(-c['y']/110+.5)*1266])
    distances=[float(np.linalg.norm(p.mean(axis=0)-center)) for p in polygons]
    order=np.argsort(distances)
    if distances[order[0]]>20 or distances[order[1]]-distances[order[0]]<30:
        raise ValueError('Ambiguous CAD slot assignment')
    polygon=polygons[order[0]]
    x,y=int(center[0])-65,int(center[1])-85
    rows,tiles=[],[]
    for source,truth in SOURCES.items():
        board=cv2.imread(str(base/source/'aligned_board.png'))
        if board is None or board.shape!=(1266,1600,3):
            raise ValueError(source)
        crop=board[y:y+170,x:x+130].copy()
        probes={}
        for threshold in (100,130,160):
            contour=bright_outline(crop,threshold)
            if contour is None:
                probes[str(threshold)]=None
                continue
            points=contour.reshape(-1,2)+[x,y]
            signed=[cv2.pointPolygonTest(polygon,(float(a),float(b)),True) for a,b in points]
            probes[str(threshold)]={'minimum_signed_clearance_px':min(signed),
                'maximum_outside_px':max(0.,-min(signed))}
        overlay=crop.copy()
        cv2.polylines(overlay,[np.rint(polygon-[x,y]).astype(np.int32)],True,(0,200,255),1)
        contour=bright_outline(crop,130)
        if contour is not None:
            cv2.drawContours(overlay,[contour],-1,(255,180,0),1)
        panel=cv2.resize(np.hstack([crop,overlay]),None,fx=3,fy=3,interpolation=cv2.INTER_NEAREST)
        panel=cv2.copyMakeBorder(panel,32,0,0,0,cv2.BORDER_CONSTANT)
        cv2.putText(panel,f'{len(rows)+1} {truth} | CAD yellow / bright outline cyan',(5,22),cv2.FONT_HERSHEY_SIMPLEX,.44,(255,255,255),1)
        tiles.append(panel)
        rows.append(dict(source=source,truth_scope=truth,probes=probes))
    out=Path(tempfile.mkdtemp(prefix='smd02_cad_containment_',dir=base))
    cv2.imwrite(str(out/'comparison.png'),np.vstack(tiles))
    payload=dict(rows=rows,polygon_image_px=polygon.tolist(),face_index=faces[order[0]]['face_index'],
        status='DIAGNOSTIC_ONLY',runtime_changed=False,
        limitation='Archived development scenes, no holdout. Bright contour is not full physical body. CAD floor is not measured printed upper wall; containment does not certify seating height. Fixed slot assignment only, no local fitting.')
    (out/'audit.json').write_text(json.dumps(payload,indent=2))
    print(out)
    for r in rows:
        print(r['truth_scope'],r['probes'])


if __name__=='__main__':
    main()
