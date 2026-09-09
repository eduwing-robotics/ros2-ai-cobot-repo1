"""Diagnostic CAD projection versus active nominal ROIs; never edits calibration."""
import json
import tempfile
from pathlib import Path

import cv2
import numpy as np
from extract_unity_socket_candidates import extract
from preprocessor_and_cropper import FixedSlotCropper

ROOT = Path(__file__).resolve().parents[2]


def main():
    report_dir = ROOT/'runtime/inspection/hybrid_fixed_slot/20260908_194313_711865'
    board = cv2.imread(str(report_dir/'aligned_board.png'))
    if board is None or board.shape != (1266,1600,3):
        raise ValueError('Missing canonical image')
    cropper = FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    layout = json.loads((ROOT/'vision_assembly/config/board_layout_from_unity.json').read_text())
    spec = json.loads((ROOT/'vision_assembly/config/unity_socket_clearance.json').read_text())
    mesh = Path('/home/hc/My project/Assets/반도체 기판 모델링(Unity)/ASt/motherBoard.obj')
    faces = extract(mesh, spec)
    scale = layout['board']['unity_to_physical_scale']
    width,height = cropper.board_size_mm
    left, right = board.copy(), board.copy()
    rows = []
    for face in faces:
        # User corrected the OBJ Z/image Y direction: positive Z is image down.
        # No local recenter/rotation and no physical overrides.
        polygon = np.array(face['polygon_obj_xz_mm'], dtype=float)
        polygon[:,0] = (polygon[:,0]*scale['x']/width+.5)*1600
        polygon[:,1] = (polygon[:,1]*scale['y']/height+.5)*1266
        cv2.polylines(left,[np.rint(polygon).astype(np.int32)],True,(0,200,255),2)
        rows.append(dict(face_index=face['face_index'],component_type=face['component_type'],
                         polygon_image_px=polygon.tolist()))
    for slot in cropper.fixed_slots(board):
        cx,cy,sx,sy = slot.geometry
        cv2.rectangle(right,(round(cx-sx/2),round(cy-sy/2)),
                      (round(cx+sx/2),round(cy+sy/2)),(255,180,0),2)
    panels=[]
    for image,title in [(left,'CAD FLOOR PROJECTION / VERTICAL DIRECTION CORRECTED'),
                        (right,'ACTIVE NOMINAL PART ROI / NOT SOCKET WALL')]:
        image=cv2.copyMakeBorder(image,45,0,0,0,cv2.BORDER_CONSTANT)
        cv2.putText(image,title,(12,30),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),1)
        panels.append(image)
    out=Path(tempfile.mkdtemp(prefix='unity_socket_projection_',dir=ROOT/'runtime/inspection'))
    if not cv2.imwrite(str(out/'comparison.png'),np.hstack(panels)):
        raise OSError('Image write failed')
    (out/'audit.json').write_text(json.dumps(dict(source=str(report_dir),rows=rows,
        status='DIAGNOSTIC_ONLY',runtime_changed=False,
        projection_signs=dict(image_x_from_obj_x=1,image_y_from_obj_z=1),
        limitation='Original CAD centers retained. User-corrected vertical direction; physical overrides intentionally not applied. Previous mismatch is not evidence of a different physical layout. No inferred slot IDs or local fitting. Image is archived, not live.'),indent=2))
    print(out)


if __name__=='__main__':
    main()
