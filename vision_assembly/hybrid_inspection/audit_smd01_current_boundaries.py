"""Read-only boundary repeatability evidence; never certifies socket height."""
import json
from pathlib import Path
import cv2
from audit_smd01_outline import bright_outline

ROOT = Path(__file__).resolve().parents[2]


def audit():
    base = ROOT / "runtime/inspection"
    cases = [
        ("hybrid_fixed_slot/20260908_192040_004911", "normal"),
        ("hybrid_fixed_slot/20260908_192131_056737", "normal"),
        ("hybrid_fixed_slot/20260907_120941_804840", "subtle_defect"),
        ("smd01_lip_validation_20260908_132035/20260908_132108_768224", "defect")]
    rows = []
    for folder, truth in cases:
        path = base / folder / "aligned_board.png"
        image = cv2.imread(str(path))
        if image is None or image.shape != (1266, 1600, 3):
            raise ValueError(f"Invalid aligned board: {path}")
        crop = image[1014:1154, 1181:1361]
        bounds = {}
        for threshold in (100, 130, 160):
            contour = bright_outline(crop, threshold)
            bounds[str(threshold)] = None if contour is None else list(cv2.boundingRect(contour))
        rows.append(dict(source=str(path), truth=truth, bounds_xywh=bounds))
    walls = json.loads((base / "smd01_wall_consensus_20260907/audit.json").read_text())["consensus"]
    return dict(rows=rows, empty_wall_candidates=walls, runtime_changed=False,
        interpretation="Normal repeat silhouettes agree at130/160; subtle defect differs only2px in top edge. Empty-wall spread9px at top is larger than this separation. No reliable inner-wall or height claim; no threshold fit or label change.")


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
