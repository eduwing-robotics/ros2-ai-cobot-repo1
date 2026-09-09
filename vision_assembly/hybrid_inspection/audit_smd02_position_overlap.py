"""Read-only development replay: SMD02 normal/known lip-defect overlap.

No threshold fitting, new capture, relabelling, or production report mutation.
Run in the hybrid inspection environment after sourcing ROS setup.bash.
"""
import json
from pathlib import Path

import cv2
from audit_smd01_outline import bright_outline
from main import build_advisory_candidates
from preprocessor_and_cropper import FixedSlotCropper

ROOT = Path(__file__).resolve().parents[2] / "runtime/inspection"
SOURCES = {
    **{f"hybrid_fixed_slot/{stamp}": "user_declared_normal_placement"
       for stamp in (
           "20260908_190443_911029", "20260908_192131_056737",
           "20260908_193836_791919", "20260908_194222_647819",
           "20260908_194313_711865")},
    "hybrid_smd02_lip_full_132929/20260904_133349_966892": "controlled_lip_defect",
    "hybrid_smd02_lip_full_133042/20260904_133430_586470": "controlled_lip_defect",
    "hybrid_smd02_lip_full_133138/20260904_133510_984394": "controlled_lip_defect",
}


def main():
    rows = []
    cropper = FixedSlotCropper(ROOT.parents[1] / "vision_assembly/config/full_board_inspection.json")
    for source, truth in SOURCES.items():
        report = json.loads((ROOT / source / "hybrid_report.json").read_text())
        row = next(s for s in report["slots"] if s["slot_id"] == "smd_capacitor_02")
        pose = row["stages"]["pose"]
        measured = pose["measured"]
        candidates = build_advisory_candidates([row])
        board = cv2.imread(str(ROOT / source / "aligned_board.png"))
        if board is None or board.shape != (1266, 1600, 3):
            raise ValueError(f"Invalid aligned board: {source}")
        slot = next(s for s in cropper.fixed_slots(board) if s.slot_id == "smd_capacitor_02")
        cx, cy, _, _ = slot.geometry
        x, y = int(cx) - 65, int(cy) - 85
        crop = board[y:y+170, x:x+130]
        if crop.shape != (170, 130, 3):
            raise ValueError("Clipped diagnostic window")
        outlines = {}
        for threshold in (100, 130, 160):
            contour = bright_outline(crop, threshold)
            if contour is None:
                outlines[str(threshold)] = None
                continue
            bx, by, bw, bh = cv2.boundingRect(contour)
            outlines[str(threshold)] = [x+bx, y+by, bw, bh]
        rows.append({
            "source": source, "truth_scope": truth,
            "input_sha256": report.get("input_sha256"),
            "transverse_mm": measured["absolute_transverse_offset_mm"],
            "raw_offset_mm": measured["raw_offset_mm"],
            "common_bias_mm": measured.get("common_bias_correction_mm"),
            "mask_area_px": measured.get("mask_area_px"),
            "surface_score": row["stages"]["surface"].get("score"),
            "codes": candidates[0]["codes"] if candidates else [],
            "bright_outline_board_xywh": outlines,
        })
    normal = [r["transverse_mm"] for r in rows if r["truth_scope"].startswith("user")]
    defect = [r["transverse_mm"] for r in rows if r["truth_scope"].startswith("controlled")]
    print(json.dumps({
        "rows": rows,
        "normal_range_mm": [min(normal), max(normal)],
        "defect_range_mm": [min(defect), max(defect)],
        "larger_is_bad_threshold_separates": max(normal) < min(defect),
        "limitation": "Archived developmental evidence, not independent holdout. Normal refers only to SMD02 placement, not whole-board condition. Different capture dates; no measurement accuracy or physical height certification.",
        "runtime_changed": False, "motion_command_sent": False,
        "outline_limit": "Fixed board-coordinate raw grayscale connected-component probes only. Bright silhouette can exclude dark body or join highlights. Nominal ROI is not a measured socket wall; these boxes cannot certify containment or height.",
    }, indent=2))


if __name__ == "__main__":
    main()
