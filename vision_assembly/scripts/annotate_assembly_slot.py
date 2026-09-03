#!/usr/bin/env python3
"""Annotate one assembly slot directly on a PlaceCamera image."""

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np


ORDER = ('TOP-LEFT', 'TOP-RIGHT', 'BOTTOM-RIGHT', 'BOTTOM-LEFT')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--slot-code', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    image = cv2.imread(str(args.image))
    if image is None:
        raise SystemExit(f'cannot read {args.image}')
    points = []
    window = f'ASSEMBLY SLOT - {args.slot_code}'

    def redraw():
        shown = image.copy()
        cv2.rectangle(shown, (0, 0), (shown.shape[1], 76), (18, 24, 30), -1)
        instruction = 'DONE - press ENTER' if len(points) == 4 else f'Click {ORDER[len(points)]} ({len(points)+1}/4)'
        cv2.putText(shown, f'DIRECT SLOT ANNOTATION: {args.slot_code}', (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, .75, (255, 255, 255), 2)
        cv2.putText(shown, instruction + '   [R reset / Q abort]', (20, 63),
                    cv2.FONT_HERSHEY_SIMPLEX, .65, (0, 255, 255), 2)
        for index, point in enumerate(points):
            cv2.circle(shown, point, 7, (0, 0, 255), -1, cv2.LINE_AA)
            cv2.putText(shown, str(index + 1), (point[0] + 9, point[1] - 9),
                        cv2.FONT_HERSHEY_SIMPLEX, .65, (0, 0, 255), 2)
        if len(points) > 1:
            cv2.polylines(shown, [np.asarray(points, np.int32)], len(points) == 4,
                          (0, 255, 255), 3, cv2.LINE_AA)
        cv2.imshow(window, shown)

    def mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4 and y >= 76:
            points.append((x, y)); redraw()

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, min(image.shape[1], 1280), min(image.shape[0], 850))
    cv2.setMouseCallback(window, mouse)
    redraw()
    while True:
        key = cv2.waitKey(30) & 0xFF
        if key in (ord('q'), 27):
            cv2.destroyAllWindows(); raise SystemExit('annotation aborted; no file written')
        if key == ord('r'):
            points.clear(); redraw()
        if key in (10, 13, 32) and len(points) == 4:
            break
    payload = {'schema_version': 1, 'timestamp_unix': time.time(),
               'source_image': str(args.image.resolve()), 'image_size': [image.shape[1], image.shape[0]],
               'coordinate_frame': 'PlaceCamera_image_pixel', 'display_only': True,
               'slots': [{'slot_code': args.slot_code, 'polygon_image_pixel': points,
                          'status': 'operator_direct_annotation'}]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps(payload, indent=2))
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
