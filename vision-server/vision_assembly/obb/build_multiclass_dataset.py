#!/usr/bin/env python3
"""Build a stratified six-class OBB dataset without changing source labels."""
import argparse
import random
import shutil
from pathlib import Path

import cv2
import numpy as np


NAMES = {0: 'gpu', 1: 'hbm', 2: 'power_module', 3: 'vrm',
         4: 'inductor', 5: 'smd_capacitor'}


def collect(image_dir, label_dir, prefix=None):
    pairs = []
    for image in sorted([*image_dir.glob('*.jpg'), *image_dir.glob('*.png')]):
        if prefix and not image.stem.startswith(prefix):
            continue
        label = label_dir / f'{image.stem}.txt'
        if label.is_file() and label.read_text(encoding='utf-8').strip():
            pairs.append((image, label))
    return pairs


def masked_training_image(image_path, label_path, margin_ratio=0.035):
    """Hide unlabelled tray sections so they are not learned as negatives."""
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f'Cannot read {image_path}')
    height, width = image.shape[:2]
    points = []
    for line in label_path.read_text(encoding='utf-8').splitlines():
        fields = line.split()
        if len(fields) != 9:
            continue
        values = np.asarray([float(value) for value in fields[1:]], np.float32)
        points.append(values.reshape(4, 2) * np.array([width, height], np.float32))
    if not points:
        return image
    points = np.concatenate(points, axis=0)
    margin = int(round(max(width, height) * margin_ratio))
    x1 = max(0, int(np.floor(points[:, 0].min())) - margin)
    y1 = max(0, int(np.floor(points[:, 1].min())) - margin)
    x2 = min(width, int(np.ceil(points[:, 0].max())) + margin)
    y2 = min(height, int(np.ceil(points[:, 1].max())) + margin)
    masked = np.full_like(image, 235)
    masked[y1:y2, x1:x2] = image[y1:y2, x1:x2]
    return masked


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--val-ratio', type=float, default=0.2)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--exclude-class', action='append', default=[])
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    output = root / 'multiclass_dataset'
    sources = {
        0: collect(root/'dataset/images/unlabeled', root/'dataset/labels/all', 'gpu_'),
    }
    real = root / 'real_multiclass'
    for class_id, name in NAMES.items():
        if class_id == 0:
            continue
        sources[class_id] = collect(real/'images/unlabeled', real/'labels/all', f'{name}_')

    for split in ('train', 'val'):
        for kind in ('images', 'labels'):
            path = output/kind/split
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    totals = {'train': 0, 'val': 0}
    for class_id, pairs in sources.items():
        if NAMES[class_id] in args.exclude_class:
            print(f'skip {NAMES[class_id]}: explicitly excluded')
            continue
        if not pairs:
            print(f'skip {NAMES[class_id]}: no completed labels')
            continue
        rng.shuffle(pairs)
        val_count = max(1, round(len(pairs) * args.val_ratio)) if len(pairs) > 1 else 0
        groups = {'val': pairs[:val_count], 'train': pairs[val_count:]}
        for split, items in groups.items():
            for image, label in items:
                prepared = masked_training_image(image, label)
                if not cv2.imwrite(str(output/'images'/split/image.name), prepared,
                                   [cv2.IMWRITE_JPEG_QUALITY, 95]):
                    raise RuntimeError(f'Could not write prepared image: {image.name}')
                shutil.copy2(label, output/'labels'/split/label.name)
            totals[split] += len(items)
        print(f'{NAMES[class_id]}: train={len(groups["train"])}, val={len(groups["val"])}')
    print(f'total: train={totals["train"]}, val={totals["val"]}')


if __name__ == '__main__':
    main()
