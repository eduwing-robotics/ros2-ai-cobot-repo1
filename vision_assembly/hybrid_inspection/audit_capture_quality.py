"""Replay photo-quality triage without models, capture, relabelling or motor I/O."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from capture_quality import assess_capture_quality
from preprocessor_and_cropper import FixedSlotCropper, PROJECT_DIR


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--include-degraded', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    cropper = FixedSlotCropper(PROJECT_DIR/'vision_assembly/config/full_board_inspection.json')
    mask = cropper.static_board_mask()
    records = []
    for path in args.images:
        source = cv2.imread(str(path))
        if source is None:
            raise RuntimeError(f'Cannot read {path}')
        registered = cropper.register(source)
        valid = registered.alignment_reason == 'OK' and registered.alignment_score >= float(
            cropper.config['global_alignment']['minimum_score'])
        variants = {'recorded': registered.image_bgr}
        if args.include_degraded:
            # Deliberately degraded arrays are synthetic triage tests, NOT new
            # real defect/training images or model-performance measurements.
            variants.update(synthetic_blur=cv2.GaussianBlur(registered.image_bgr, (41, 41), 10),
                            synthetic_black=np.zeros_like(registered.image_bgr),
                            synthetic_white=np.full_like(registered.image_bgr, 255))
        for name, pixels in variants.items():
            quality = assess_capture_quality(pixels, cropper.reference, mask, alignment_valid=valid)
            records.append(dict(source=str(path.resolve()), source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                variant=name, alignment_score=registered.alignment_score,
                                capture_quality=quality))
            print(path.name, name, quality['status'], quality['flags'], flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(dict(records=records, camera_capture_performed=False, model_fit_performed=False,
                       labels_changed=False, robot_command_sent=False, conveyor_command_sent=False,
                       limitation='Retrospective photo triage and synthetic gross degradation, not independent physical quality validation.'),
                  stream, indent=2)


if __name__ == '__main__':
    main()
