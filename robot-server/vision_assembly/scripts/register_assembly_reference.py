#!/usr/bin/env python3
"""Manually register the numbered assembly reference to a PlaceCamera frame."""

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np


ORDER = ('TOP-LEFT', 'TOP-RIGHT', 'BOTTOM-RIGHT', 'BOTTOM-LEFT')


def collect(window, image, title):
    points = []
    shown = image.copy()

    def redraw():
        nonlocal shown
        shown = image.copy()
        cv2.rectangle(shown, (0, 0), (shown.shape[1], 72), (18, 24, 30), -1)
        instruction = 'DONE - press ENTER' if len(points) == 4 else f'Click {ORDER[len(points)]} ({len(points)+1}/4)'
        cv2.putText(shown, title, (20, 28), cv2.FONT_HERSHEY_SIMPLEX, .72, (255, 255, 255), 2)
        cv2.putText(shown, instruction + '   [R reset / Q abort]', (20, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, .65, (0, 255, 255), 2)
        for index, point in enumerate(points):
            cv2.circle(shown, point, 8, (0, 0, 255), -1, cv2.LINE_AA)
            cv2.putText(shown, str(index + 1), (point[0] + 10, point[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 0, 255), 2)
        if len(points) > 1:
            cv2.polylines(shown, [np.asarray(points, np.int32)], len(points) == 4,
                          (0, 255, 0), 2, cv2.LINE_AA)
        cv2.imshow(window, shown)

    def mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4 and y >= 72:
            points.append((x, y)); redraw()

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, min(image.shape[1], 1280), min(image.shape[0], 850))
    cv2.setMouseCallback(window, mouse)
    redraw()
    while True:
        key = cv2.waitKey(30) & 0xFF
        if key in (ord('q'), 27):
            raise KeyboardInterrupt
        if key == ord('r'):
            points.clear(); redraw()
        if key in (10, 13, 32) and len(points) == 4:
            cv2.destroyWindow(window)
            return np.asarray(points, np.float32)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--live', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reference = cv2.imread(str(args.reference)); live = cv2.imread(str(args.live))
    if reference is None or live is None:
        raise SystemExit('could not read reference/live image')
    try:
        reference_points = collect('1_REFERENCE_NUMBERED', reference, 'NUMBERED REFERENCE IMAGE')
        live_points = collect('2_NEW_PLACECAMERA', live, 'NEW PLACECAMERA LIVE IMAGE')
    except KeyboardInterrupt:
        cv2.destroyAllWindows(); raise SystemExit('registration aborted; no file written')
    H = cv2.getPerspectiveTransform(reference_points, live_points)
    projected = cv2.perspectiveTransform(reference_points.reshape(-1, 1, 2), H).reshape(-1, 2)
    errors = np.linalg.norm(projected - live_points, axis=1)
    payload = {
        'schema_version': 1, 'timestamp_unix': time.time(),
        'reference_image': str(args.reference.resolve()), 'live_image': str(args.live.resolve()),
        'reference_corners_pixel': reference_points.tolist(),
        'live_corners_pixel': live_points.tolist(),
        'homography_reference_to_live': H.tolist(),
        'corner_reprojection_error_px': errors.tolist(),
        'status': 'manual four-corner registration; display only until slot validation',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps(payload, indent=2))
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
