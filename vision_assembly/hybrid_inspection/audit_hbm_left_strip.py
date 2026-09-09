"""Offline strip coverage probe, not automatic ROI fitting or pin validation."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows = []
    for run in args.run:
        for slot in ("hbm_01", "hbm_02", "hbm_03", "hbm_04"):
            path = run / "fixed_slots/hbm" / (slot + ".png")
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError(str(path))
            h, w = image.shape[:2]
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)[:, :, 0]
            sat = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 1]
            trials = []
            for shift in (0, 4, 8, 12):
                x0, x1 = int(w*.06)+shift, int(w*.25)+shift
                y0, y1 = int(h*.12), int(h*.70)
                region = lab[y0:y1, x0:x1]
                low_sat = sat[y0:y1, x0:x1] <= 105
                mask = (region >= 130) & low_sat
                trials.append({"shift_px":shift,"bbox_px":[x0,y0,x1,y1],
                               "white_pixels":int(mask.sum()),
                               "rows_with_two_white_pixels":int((mask.sum(axis=1)>=2).sum()),
                               "lab_l_p95":float(np.percentile(region,95))})
            rows.append({"path":str(path),"slot_id":slot,"trials":trials})
    with args.output.open("x") as stream:
        json.dump({"authority":"OFFLINE_ONLY","warning":"Bright pixels are not validated pins; shifted strip can admit body/logo",
                   "rows":rows},stream,indent=2)
    print(args.output)


if __name__ == "__main__":
    main()
