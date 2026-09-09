"""Offline CLI for unvalidated HBM row evidence; never emits PASS or FAIL.

--strips accepts a local JSON file containing left/right exclusive-end pixel
rectangles, e.g. {"left": [8,8,20,112], "right": [60,8,72,112]}.
Images must be local 8-bit three-channel color crops; OpenCV BGR is converted
to RGB without resizing or registration. All usability flags default false.
Exit 0 means artifacts were written, NOT an inspection pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

if __package__:
    from .hbm_pin_profile_candidate import inspect_hbm_pin_rows
else:
    from hbm_pin_profile_candidate import inspect_hbm_pin_rows


def _local_bytes(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f'Not a local file: {path}')
    return path.read_bytes()


def _decode_rgb(payload):
    image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if (image is None or image.dtype != np.uint8 or image.ndim != 3
            or image.shape[2] != 3 or min(image.shape[:2]) < 8
            or max(image.shape[:2]) > 2048):
        raise ValueError('Image must be 8-bit 3-channel color, each dimension 8..2048')
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def load_rgb(path):
    return _decode_rgb(_local_bytes(path))


def render_overlay(rgb, result):
    h, w = rgb.shape[:2]
    canvas = np.zeros((h + 260, max(w, 760), 3), np.uint8)
    canvas[:h, :w] = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    cv2.putText(canvas, 'UNKNOWN / ADVISORY_ONLY - offline, uncalibrated',
                (8, h+22), cv2.FONT_HERSHEY_SIMPLEX, .5, (230, 230, 230), 1)
    for index, (side, data) in enumerate(result['evidence']['sides'].items()):
        color = (60, 210, 90) if side == 'left' else (240, 170, 60)
        x0, y0, x1, y1 = data['strip_px']
        cv2.rectangle(canvas, (x0, y0), (x1-1, y1-1), color, 1)
        base = h+125+index*110
        cv2.putText(canvas, side+' white coverage: color=current gray=reference',
                    (8, base-78), cv2.FONT_HERSHEY_SIMPLEX, .4, color, 1)
        for profile, line_color in (
            (data.get('reference', {}).get('white_profile', []), (145, 145, 145)),
            (data['white_profile'], color),
        ):
            if profile:
                points = np.array([(10+int(i*720/max(1, len(profile)-1)),
                                    base-int(v*65)) for i, v in enumerate(profile)], np.int32)
                cv2.polylines(canvas, [points], False, line_color, 1)
        for start, end in data['deficit_intervals']:
            if data['axis'] == 'y':
                p0, p1 = (x0, y0+start), (x1-1, y0+end-1)
            else:
                p0, p1 = (x0+start, y0), (x0+end-1, y1-1)
            cv2.rectangle(canvas, p0, p1, (30, 30, 240), 1)
    return canvas


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, type=Path)
    parser.add_argument('--strips', required=True, type=Path)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--reference-reliable', action='store_true')
    parser.add_argument('--orientation-usable', action='store_true')
    parser.add_argument('--angle-error', type=float, default=None)
    parser.add_argument('--quality-usable', action='store_true')
    parser.add_argument('--axis', choices=('x', 'y'), default='y')
    parser.add_argument('--slot-id', default='hbm_unknown')
    args = parser.parse_args(argv)
    try:
        if args.output_dir.exists() or args.output_dir.is_symlink():
            raise ValueError('Output directory already exists; refusing overwrite')
        # Decode and hash the very same captured bytes, never reread for hashing.
        source_bytes = _local_bytes(args.image)
        reference_bytes = _local_bytes(args.reference) if args.reference is not None else None
        strips_bytes = _local_bytes(args.strips)
        rgb = _decode_rgb(source_bytes)
        reference = _decode_rgb(reference_bytes) if reference_bytes is not None else None
        strips = json.loads(strips_bytes.decode('utf-8'))
        result = inspect_hbm_pin_rows(
            rgb, strips=strips, reference_rgb=reference,
            reference_reliable=args.reference_reliable,
            orientation_usable=args.orientation_usable, angle_error_deg=args.angle_error,
            quality_usable=args.quality_usable, axis=args.axis, slot_id=args.slot_id)
        if result['status'] != 'UNKNOWN' or result['authority'] != 'ADVISORY_ONLY':
            raise ValueError('Candidate authority contract violated')
        result['evidence']['review_inputs'] = {
            'image': str(args.image.resolve()),
            'reference': str(args.reference.resolve()) if args.reference else None,
            'strips': str(args.strips.resolve()),
            'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
            'reference_sha256': (hashlib.sha256(reference_bytes).hexdigest()
                                 if reference_bytes is not None else None),
            'strips_sha256': hashlib.sha256(strips_bytes).hexdigest(),
            'hash_scope': 'Captured local file bytes; reproducibility only, not authority or validation.',
            'reference_reliable': args.reference_reliable,
            'orientation_usable': args.orientation_usable,
            'quality_usable': args.quality_usable,
            # String preserves nonfinite CLI input without invalid JSON numbers.
            'angle_error_argument': str(args.angle_error),
        }
        payload = json.dumps(result, indent=2, allow_nan=False)+'\n'
        ok, png = cv2.imencode('.png', render_overlay(rgb, result))
        if not ok:
            raise ValueError('Could not encode diagnostic PNG')
        # Atomic directory reservation; never reuse an existing destination.
        args.output_dir.mkdir(parents=True, exist_ok=False)
        with (args.output_dir / 'review.json').open('x', encoding='utf-8') as stream:
            stream.write(payload)
        with (args.output_dir / 'profile_overlay.png').open('xb') as stream:
            stream.write(png.tobytes())
    except (OSError, ValueError, cv2.error) as exc:
        parser.exit(2, f'Offline review error: {exc}\n')
    print(f'UNKNOWN / ADVISORY_ONLY: {args.output_dir}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
