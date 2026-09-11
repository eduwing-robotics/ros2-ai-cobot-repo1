"""Offline SMD01 appearance experiment; no production verdict or position labels."""
import hashlib
from pathlib import Path
import re

LABELS = ('NORMAL_SEATED', 'LIP_SEATING')
CROP_XYWH = (1181, 1014, 180, 140)
CROP_PIPELINE = 'S22_REGISTERED_RAW_RGB_FIXED_SMD01_CONTEXT_180X140_V1'


def assign_split(source):
    match = re.fullmatch(r's22_inspection_roi_(\d{8})_\d{6}\.png', Path(source).name)
    if not match:
        raise ValueError('Unrecognized source identity; do not guess a split')
    date = match[1]
    if date < '20260907':
        return 'train'
    if date == '20260907':
        return 'validation'
    return 'later_replay'


def unique_cases(cases):
    """Conflicts fail closed. A scene alias may not put identical bytes in two sets."""
    unique = {}
    for row in cases:
        if row['label'] not in LABELS:
            raise ValueError('Unsupported physical-condition label')
        digest = row['source_sha256']
        if not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Invalid source hash')
        key = unique.get(digest)
        if key and (key['label'] != row['label'] or key['split'] != row['split']):
            raise ValueError('Conflicting source label or split')
        unique.setdefault(digest, row)
    return list(unique.values())


def fixed_crop(image):
    import numpy as np
    if image is None or image.shape != (1266, 1600, 3) or image.dtype != np.uint8:
        raise ValueError('Expected registered original BGR 1600x1266 uint8')
    x, y, w, h = CROP_XYWH
    return image[y:y+h, x:x+w].copy()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def registration_hashes(root):
    import json
    config_path = root/'vision_assembly/config/full_board_inspection.json'
    config = json.loads(config_path.read_text())
    paths = [config_path]
    for key in ('reference_image', 'board_layout', 'physical_board', 'socket_clearance'):
        path = Path(config[key])
        paths.append(path if path.is_absolute() else root/path)
    return {str(p.resolve()): sha256(p) for p in paths}
