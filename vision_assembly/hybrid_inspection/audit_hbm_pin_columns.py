"""Offline original-RGB white component column localization. Never a verdict.

No image warp or template refresh. Missing anchors abstain; detected anchors
do not establish pin count, component pose, or normality. Engineering limits
below are uncalibrated. Do not import this probe into the production decision.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def locate_columns(rgb):
    if not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3 or min(rgb.shape[:2]) < 32:
        raise ValueError("Expected RGB uint8 crop, at least 32px")
    h, w = rgb.shape[:2]
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)[:, :, 0]
    sat = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[:, :, 1]
    mask = ((lab >= 130) & (sat <= 105)).astype(np.uint8)
    n, _, stats, centers = cv2.connectedComponentsWithStats(mask, 8)
    result = {}
    for side, bounds in (("left", (.03, .40)), ("right", (.60, .97))):
        # Exclude central coloured logo and lower orientation-dot region.
        points = []
        for i in range(1, n):
            x, y, bw, bh, area = stats[i]
            cx, cy = centers[i]
            if (bounds[0]*w <= cx <= bounds[1]*w and .10*h <= cy <= .72*h
                    and 3 <= area <= .0025*h*w and bw <= .09*w and bh <= .07*h):
                points.append([float(cx), float(cy), int(area)])
        p = np.asarray(points, dtype=float).reshape(-1, 3)
        best = []
        for seed in p:
            near = p[np.abs(p[:, 0]-seed[0]) <= max(3, .025*w)]
            near = near[np.argsort(near[:, 1])]
            if len(near) > len(best):
                best = near.tolist()
        reason = "INSUFFICIENT_COLUMN_ANCHORS"
        line = None
        if len(best) >= 6:
            reason = "COLUMN_GEOMETRY_UNRESOLVED"
            anchors = np.array(best)
            gaps = np.diff(anchors[:, 1])
            # Reject isolated logo/dot clusters; deliberately do not demand
            # perfectly periodic pins on irregular printed parts.
            if np.ptp(anchors[:, 1]) >= .30*h and gaps.min() >= 3:
                slope, intercept = np.polyfit(anchors[:, 1], anchors[:, 0], 1)
                residual = float(np.max(np.abs(anchors[:, 0] - (slope*anchors[:, 1]+intercept))))
                if residual <= max(3, .025*w) and abs(slope) <= .20:
                    reason = "UNVERIFIED_WHITE_COLUMN"
                    line = {"x_per_y": float(slope), "x_intercept": float(intercept), "max_residual_px": residual}
        result[side] = {"status": "UNKNOWN", "reason": reason,
                        "anchors_px": best, "fit": line, "candidate_components": points}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for run in args.run:
        for path in sorted((run / "fixed_slots/hbm").glob("hbm_*.png")):
            bgr = cv2.imread(str(path))
            if bgr is None:
                raise ValueError(str(path))
            rows.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "slot_id": path.stem, "sides": locate_columns(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))})
    if not rows:
        raise ValueError("No crops found")
    with args.output.open("x") as stream:
        json.dump({"authority": "OFFLINE_ONLY", "verdict": "UNKNOWN",
                   "limitations": "White columns are unverified; no missing-pin judgement or reference update", "rows": rows}, stream, indent=2)
    for run in args.run:
        subset = [r for r in rows if Path(r["path"]).is_relative_to(run)]
        print(run.name, {side: sum(r["sides"][side]["fit"] is not None for r in subset) for side in ("left", "right")}, "of", len(subset))


if __name__ == "__main__":
    main()
