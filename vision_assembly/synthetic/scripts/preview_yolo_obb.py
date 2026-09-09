"""Draw YOLO-OBB labels on one generated synthetic image."""

import argparse
from pathlib import Path

import cv2
import numpy as np


CLASSES = ["gpu", "hbm", "power_module", "vrm", "inductor", "smd_capacitor"]
COLOURS = [(255, 80, 80), (80, 180, 255), (40, 210, 255), (120, 255, 120), (255, 220, 40), (255, 90, 210)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--label", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Cannot read image: {args.image}")
    height, width = image.shape[:2]
    for line in args.label.read_text(encoding="utf-8").splitlines():
        values = line.split()
        if len(values) != 9:
            continue
        class_id = int(values[0])
        corners = np.asarray([float(value) for value in values[1:]], dtype=np.float32).reshape(4, 2)
        corners[:, 0] *= width
        corners[:, 1] *= height
        corners = corners.astype(np.int32)
        colour = COLOURS[class_id % len(COLOURS)]
        cv2.polylines(image, [corners], True, colour, 2, cv2.LINE_AA)
        anchor = tuple(corners[0])
        cv2.putText(image, CLASSES[class_id], anchor, cv2.FONT_HERSHEY_SIMPLEX, 0.48, colour, 1, cv2.LINE_AA)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), image):
        raise RuntimeError(f"Cannot write preview: {args.output}")
    print(args.output)


if __name__ == "__main__":
    main()
