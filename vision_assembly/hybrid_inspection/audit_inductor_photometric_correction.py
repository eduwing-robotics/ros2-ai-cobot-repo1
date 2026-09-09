"""Offline bounded color-gain experiment; never imported by production inspection.

No spatial transforms, fitting, threshold updates, or training-data promotion.
White-surface percentiles are a diagnostic proxy, not a calibrated light sensor.
"""
import json
import os
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'vision_assembly/inspection'))
from predict_component_patchcore import _checkpoint, _predict_outputs


def bounded_gain(image, reference):
    source = np.percentile(image, 95, axis=(0, 1))
    gain = np.clip(np.asarray(reference) / np.maximum(source, 1), .9, 1.1)
    corrected = np.rint(np.clip(image.astype(np.float32) * gain, 0, 255)).astype(np.uint8)
    return corrected, gain


def main():
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    experiment = ROOT / 'runtime/inspection/patchcore/inductor_confirmed_i1_candidate_20260906'
    dataset = experiment / 'dataset/inductor'
    out = ROOT / 'runtime/inspection/inductor_color_gain_audit_20260907'
    out.mkdir(exist_ok=False)
    crops = out / 'crops'
    crops.mkdir()
    originals = [p for p in (dataset / 'train/good').glob('*.png') if '__' not in p.stem]
    reference = np.median([np.percentile(cv2.imread(str(p)), 95, axis=(0, 1)) for p in originals], axis=0)
    sources = []
    for split in ['test/good', 'test/controlled_defect', 'holdout/normal',
                  'holdout/direction_defect', 'fresh/normal', 'fresh/direction_defect']:
        sources.extend((p, 'normal' if split.endswith(('good', 'normal')) else 'defect')
                       for p in sorted((dataset / split).glob('*.png')))
    for scene in ['20260907_094826_340451', '20260907_095642_786832', '20260907_100101_684903']:
        for index in [1, 2]:
            # Current morning captures are evaluation-only, not new ground truth.
            sources.append((ROOT / f'runtime/inspection/hybrid_fixed_slot/{scene}/patchcore_crops/inductor/inductor_0{index}.png', 'morning_unlabelled'))
    rows = []
    for index, (path, label) in enumerate(sources):
        image = cv2.imread(str(path))
        if image is None:
            raise RuntimeError(f'Unreadable: {path}')
        corrected, gain = bounded_gain(image, reference)
        for mode, pixels in [('raw', image), ('gain', corrected)]:
            if not cv2.imwrite(str(crops / f'{index:04d}_{mode}.png'), pixels):
                raise RuntimeError('Image write failed')
        rows.append(dict(index=index, source=str(path), label=label, gain_bgr=gain.tolist()))
    predictions = _predict_outputs('inductor', crops, _checkpoint(experiment / 'models', 'inductor'), out / 'prediction')
    for row in rows:
        for mode in ['raw', 'gain']:
            row[mode] = predictions[f"{row['index']:04d}_{mode}"]['score']
    threshold = .4391077906
    summary = {}
    for mode in ['raw', 'gain']:
        normals = [r[mode] for r in rows if r['label'] == 'normal']
        defects = [r[mode] for r in rows if r['label'] == 'defect']
        summary[mode] = dict(normal_count=len(normals), normal_flags=sum(s > threshold for s in normals),
                             defect_count=len(defects), defect_flags=sum(s > threshold for s in defects),
                             normal_max=max(normals), defect_min=min(defects))
    payload = dict(reference_bgr=reference.tolist(), threshold_unchanged=threshold,
                   summary=summary, rows=rows, deployed=False,
                   limitation='Development replay only; morning physical truth not assigned. Crop percentiles depend on part content. No runtime changes or motion commands.')
    (out / 'comparison.json').write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps(dict(summary=summary, morning=[r for r in rows if r['label'] == 'morning_unlabelled']), indent=2))


if __name__ == '__main__':
    main()
