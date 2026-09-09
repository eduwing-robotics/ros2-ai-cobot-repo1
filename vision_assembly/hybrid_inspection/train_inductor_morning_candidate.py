"""Fit an isolated memory bank using a confirmed-normal morning capture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'vision_assembly/inspection'))
from train_component_patchcore import train_component
from predict_component_patchcore import _checkpoint, _predict_outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--normal-report', type=Path, required=True)
    args = parser.parse_args()
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    previous = ROOT / 'runtime/inspection/patchcore/inductor_confirmed_i1_candidate_20260906'
    out = ROOT / 'runtime/inspection/patchcore/inductor_morning_candidate_20260907'
    out.mkdir(exist_ok=False)
    dataset = out / 'dataset'
    shutil.copytree(previous / 'dataset', dataset)
    manifest = []
    for slot in ['inductor_01', 'inductor_02']:
        source = args.normal_report.resolve().parent / f'patchcore_crops/inductor/{slot}.png'
        im = cv2.imread(str(source))
        if im is None:
            raise RuntimeError(f'Cannot read {source}')
        target = dataset / f'inductor/train/good/morning_{slot}.png'
        shutil.copy2(source, target)
        for name, gain, bgr, gamma in [('dark', .9, (1,1,1), 1), ('light', 1.1, (1,1,1), 1),
                                     ('warm', 1, (.94,1,1.04), 1), ('cool', 1, (1.04,1,.94), 1),
                                     ('gamma_dark', 1, (1,1,1), 1.15), ('gamma_light', 1, (1,1,1), .85)]:
            pixels = np.uint8(np.clip((im.astype(np.float32)/255)**gamma*gain*np.asarray(bgr)*255, 0, 255))
            if not cv2.imwrite(str(target.with_stem(target.stem + '__' + name)), pixels):
                raise RuntimeError('Write failed')
        manifest.append(dict(slot=slot, source=str(source), sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    train_hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in (dataset / 'inductor/train/good').glob('*.png')}
    for p in (dataset / 'inductor').rglob('*.png'):
        if 'train' not in p.parts and hashlib.sha256(p.read_bytes()).hexdigest() in train_hashes:
            raise RuntimeError(f'Train/evaluation duplicate: {p}')
    (out / 'manifest.json').write_text(json.dumps(dict(sources=manifest,
        confirmation='User confirmed normal placement and physically repositioned both inductors before this capture.',
        policy='Only two Inductor crops; no other slots or earlier ambiguous morning scenes. Fresh subsequent captures excluded from fit. Original RGB, photometric-only augmentation, no geometric normalization.'), indent=2))
    models = out / 'models'
    train_component('inductor', dataset, models, 0, .05, 'test/controlled_defect', ('layer2','layer3'),
                    backbone_checkpoint=_checkpoint(previous / 'models', 'inductor'))
    rows = []
    for split in ['test/good','test/controlled_defect','holdout/normal','holdout/direction_defect','fresh/normal','fresh/direction_defect']:
        pred = _predict_outputs('inductor', dataset / 'inductor' / split, _checkpoint(models, 'inductor'), out / 'eval' / split)
        rows.extend(dict(name=n, split=split, score=float(v['score'])) for n,v in pred.items())
    normal = [r['score'] for r in rows if r['split'].endswith(('good','normal'))]
    bad = [r['score'] for r in rows if r['split'].endswith('defect')]
    # Preserve existing criteria for a fair replay; never loosen to obtain a pass.
    shutil.copy2(previous / 'models/decision_thresholds.json', models / 'decision_thresholds.json')
    payload = dict(rows=rows, normal_max=max(normal), defect_min=min(bad),
                   thresholds_unchanged=True, deployed=False,
                   limitation='Development replay, not independent part or crack validation. Fresh physical tests and new-model normal-map calibration required before deployment.')
    (out / 'comparison.json').write_text(json.dumps(payload, indent=2))
    print(json.dumps({k:v for k,v in payload.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
