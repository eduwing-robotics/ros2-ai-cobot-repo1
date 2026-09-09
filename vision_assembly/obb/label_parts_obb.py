#!/usr/bin/env python3
"""Interactive six-class OBB labeler for real D435 images."""
import argparse
from pathlib import Path

import cv2
import numpy as np


NAMES = {
    0: 'gpu',
    1: 'hbm',
    2: 'power_module',
    3: 'vrm',
    4: 'inductor',
    5: 'smd_capacitor',
}
COLORS = {
    0: (255, 100, 20),
    1: (255, 0, 220),
    2: (0, 170, 255),
    3: (40, 40, 255),
    4: (0, 220, 220),
    5: (40, 220, 40),
}


def clockwise(points):
    points = np.asarray(points, np.float32)
    center = points.mean(axis=0)
    angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
    ordered = points[np.argsort(angles)]
    start = int(np.argmin(ordered[:, 0] + ordered[:, 1]))
    return np.roll(ordered, -start, axis=0)


def load_boxes(path, width, height):
    boxes = []
    if not path.is_file():
        return boxes
    for line in path.read_text(encoding='utf-8').splitlines():
        fields = line.split()
        if len(fields) != 9:
            continue
        try:
            class_id = int(fields[0])
            values = np.asarray([float(value) for value in fields[1:]], np.float32)
        except ValueError:
            continue
        if class_id not in NAMES:
            continue
        points = values.reshape(4, 2) * np.array([width, height], np.float32)
        boxes.append((class_id, clockwise(points)))
    return boxes


def save_boxes(path, boxes, width, height):
    scale = np.array([width, height], np.float32)
    lines = []
    for class_id, points in boxes:
        normalized = np.clip(points / scale, 0.0, 1.0)
        values = ' '.join(f'{value:.8f}' for value in normalized.reshape(-1))
        lines.append(f'{class_id} {values}')
    path.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')


def main():
    root = Path(__file__).parent / 'real_multiclass'
    parser = argparse.ArgumentParser()
    parser.add_argument('--images', type=Path, default=root / 'images/unlabeled')
    parser.add_argument('--labels', type=Path, default=root / 'labels/all')
    parser.add_argument('--default-class', choices=NAMES.values(), default='hbm')
    parser.add_argument('--relabel', action='store_true')
    args = parser.parse_args()
    args.labels.mkdir(parents=True, exist_ok=True)
    default_id = next(key for key, value in NAMES.items() if value == args.default_class)
    images = sorted([*args.images.glob('*.jpg'), *args.images.glob('*.png')])
    if not args.relabel:
        images = [
            image for image in images
            if not (args.labels / f'{image.stem}.txt').is_file()
        ]
    if not images:
        raise RuntimeError(f'No unlabeled images in {args.images}')

    print('Keys 0-5 select class | click 4 corners | ENTER add | U undo | S save | Q quit')
    print('0 GPU, 1 HBM, 2 Power Module, 3 VRM, 4 Inductor, 5 SMD Capacitor')
    index = 0
    selected = default_id
    while index < len(images):
        image_path = images[index]
        image = cv2.imread(str(image_path))
        if image is None:
            index += 1
            continue
        height, width = image.shape[:2]
        label_path = args.labels / f'{image_path.stem}.txt'
        boxes = load_boxes(label_path, width, height) if args.relabel else []
        points = []

        def mouse(event, x, y, flags, parameter):
            if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
                points.append((x, y))

        cv2.namedWindow('Multi-class OBB Labeler', cv2.WINDOW_NORMAL)
        cv2.setMouseCallback('Multi-class OBB Labeler', mouse)
        while True:
            canvas = image.copy()
            for class_id, box in boxes:
                color = COLORS[class_id]
                cv2.polylines(canvas, [np.int32(box)], True, color, 1, cv2.LINE_AA)
            for point in points:
                cv2.circle(canvas, point, 3, COLORS[selected], 1, cv2.LINE_AA)
            if len(points) > 1:
                cv2.polylines(canvas, [np.int32(points)], False,
                              COLORS[selected], 1, cv2.LINE_AA)
            text = (f'{index + 1}/{len(images)} {image_path.name} | '
                    f'class={selected}:{NAMES[selected]} | boxes={len(boxes)}')
            cv2.rectangle(canvas, (8, 8), (min(width - 8, 900), 48), (15, 15, 15), -1)
            cv2.putText(canvas, text, (18, 37), cv2.FONT_HERSHEY_SIMPLEX,
                        0.75, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.imshow('Multi-class OBB Labeler', canvas)
            key = cv2.waitKey(30) & 0xff
            if ord('0') <= key <= ord('5'):
                selected = key - ord('0')
            elif key in (10, 13) and len(points) == 4:
                boxes.append((selected, clockwise(points)))
                points = []
            elif key in (ord('u'), ord('U')):
                if points:
                    points.pop()
                elif boxes:
                    boxes.pop()
            elif key in (ord('s'), ord('S')):
                save_boxes(label_path, boxes, width, height)
                print(f'Saved {len(boxes)} boxes: {label_path.name}')
                index += 1
                break
            elif key in (ord('q'), ord('Q'), 27):
                cv2.destroyAllWindows()
                return
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
