"""Legacy per-pin evidence adapter. Outputs are advisory, not release decisions."""
import json
from pathlib import Path
import sys
from dataclasses import asdict
import cv2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vision_assembly/inspection"))
from full_board_inspector import inspect_leg_side


def compare(reference, sample):
    h, w = reference.shape[:2]
    if sample.shape != reference.shape:
        raise ValueError("Unmatched fixed-slot geometry")
    settings = dict(minimum_reference_peaks=6, maximum_reference_peaks=16,
        peak_min_distance_px=9, peak_profile_min=.022, left_keep_fraction=.9,
        reference_peak_radius_px=3, sample_peak_radius_px=3,
        missing_evidence_ratio=.05, uncertain_evidence_ratio=.3,
        maximum_lateral_shift_mm=1e6, maximum_extra_width_mm=1e6,
        max_profile_shift_px=0, sample_peak_search_radius_px=3)
    white = dict(lab_l_min=130, hsv_s_max=105, open_kernel_px=1)
    rows = []
    for side, xa, xb in (("left", .06, .25), ("right", .69, .88)):
        # End-of-row included on right; left corner dot excluded.
        rect = (int(w*xa), int(h*.12), int(w*xb), int(h*(.70 if side == "left" else .82)))
        x0, y0, x1, y1 = rect
        r = inspect_leg_side(reference[y0:y1,x0:x1], sample[y0:y1,x0:x1],
                             side, rect, settings, white, 10.)
        data = asdict(r)
        # A completely dark side is not proof of absence. Require remaining pins.
        if r.reference_peaks < settings["minimum_reference_peaks"]:
            data["reason"] = "REFERENCE_PIN_ANCHORS_INSUFFICIENT"
        elif sum(v >= .3 for v in r.evidence_ratio) < 3:
            data["status"] = "NOT_INSPECTABLE"
            data["reason"] = "INSUFFICIENT_VISIBLE_PIN_ANCHORS"
            data["missing_indices"] = []
            data["defect_points_px"] = []
        rows.append(data)
    return rows


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    base = ROOT / "runtime/inspection/hybrid_fixed_slot"
    ref = base / "20260908_174947_620562/fixed_slots/hbm"
    rows = {}
    for p in sorted((base / args.run / "fixed_slots/hbm").glob("*.png")):
        rows[p.stem] = compare(cv2.imread(str(ref / p.name)), cv2.imread(str(p)))
    print(json.dumps(rows, indent=2))
