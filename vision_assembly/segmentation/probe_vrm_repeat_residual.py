"""Pairwise image residuals only; no correction of component coordinates."""
import json
import hashlib
import cv2
import numpy as np
from build_vrm_fixed_crop_dataset import FixedSlotCropper, ROOT


def main():
    base = ROOT / 'vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1'
    output = base / 'repeat_residual_155607_160026.json'
    if output.exists():
        raise FileExistsError(output)
    cropper = FixedSlotCropper(ROOT / 'vision_assembly/config/full_board_inspection.json')
    boards, reports = [], []
    for stamp in ['155607', '160026']:
        report = json.loads((base / f'fresh_s22_inspection_roi_20260906_{stamp}_last/report.json').read_text())
        row = report['rows'][0]
        path = ROOT / row['source_image']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['image_sha256']
        board = cropper.register(cv2.imread(str(path)))
        if board.alignment_reason != 'OK':
            raise ValueError(board.alignment_reason)
        boards.append(cv2.cvtColor(board.image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32))
        reports.append({r['slot']: r for r in report['rows']})
    rows = []
    for slot, a in reports[0].items():
        b = reports[1][slot]
        x, y = a['crop_origin_px']
        # Fixed body interior and fixed right-adjacent region: diagnostics only.
        # Adjacent region may contain shadows/neighbor features, not a certified fiducial.
        probes = {}
        for name, (dx, dy, w, h) in {'body': (45, 70, 85, 100), 'adjacent': (180, 55, 65, 135)}.items():
            patches = [im[y+dy:y+dy+h, x+dx:x+dx+w].copy() for im in boards]
            window = cv2.createHanningWindow((w, h), cv2.CV_32F)
            shift, response = cv2.phaseCorrelate(*patches, window)
            probes[name] = dict(shift_px=list(shift), response=response)
        pa, pb = a['primary'], b['primary']
        rows.append(dict(slot=slot, probes=probes,
                         mask_center_dx_px=pb['center_px'][0]-pa['center_px'][0],
                         mask_right_dx_px=max(p[0] for p in pb['polygon'])-max(p[0] for p in pa['polygon'])))
    result = dict(status='UNKNOWN', runtime_enabled=False, rows=rows,
                  limitation='Pairwise diagnostic, repeated texture/shadows may bias phase correlation. No shift subtracted, no causal attribution or physical motion truth inferred.')
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
