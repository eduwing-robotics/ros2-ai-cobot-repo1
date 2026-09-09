"""Replay current-camera controls; not independent model validation."""
import hashlib
import json
from pathlib import Path
import cv2
from preprocessor_and_cropper import FixedSlotCropper
from opencv_inspectors import check_inductor_marker

ROOT = Path(__file__).resolve().parents[2]


def main():
    out = ROOT/'runtime/inspection/inductor_marker_axis_audit_20260906.json'
    if out.exists():
        raise FileExistsError(out)
    cropper = FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    rows = []
    for stamp in ['131407','132543','152933','153345','153918','154722','155607','160026','171520','172527']:
        path = ROOT/f'runtime/inspection/s22_inspection_roi_20260906_{stamp}.png'
        board = cropper.register(cv2.imread(str(path)))
        if board.alignment_reason != 'OK':
            raise ValueError('Registration failed')
        for slot in cropper.fixed_slots(board.image_bgr):
            if slot.component_type != 'Inductor':
                continue
            result = check_inductor_marker(slot.crop_bgr)
            rows.append(dict(capture=stamp, slot=slot.slot_id, status=result.status,
                             reason=result.reason, measured=result.measured,
                             source_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    out.write_text(json.dumps(dict(rows=rows, authority='ADVISORY_ONLY',
        limitation='Development-selected controls. Earlier VRM-session inductor poses assumed unchanged/normal, not freshly individually certified. 172527/inductor02 user-confirmed defect;171520/inductor01 direction confirmed. No normal training or independent accuracy claim.'), indent=2))
    for r in rows:
        strict=r['measured'].get('strict_marker')
        print(r['capture'],r['slot'],r['status'],round(strict['axis_error_deg'],2) if strict else None)


if __name__=='__main__':
    main()
