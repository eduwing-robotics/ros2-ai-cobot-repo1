"""Isolated candidate experiment; never changes active model selection."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'vision_assembly/inspection'))
from train_component_patchcore import train_component
from predict_component_patchcore import _checkpoint, _predict_outputs


def main():
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    out = ROOT/'runtime/inspection/patchcore/inductor_appearance_candidate_20260906'
    out.mkdir(exist_ok=True)
    if (out/'comparison.json').exists():
        raise RuntimeError('Completed experiment already exists; choose a new version')
    dataset = out/'dataset'
    manifest = []
    def copy(source, split, name=None):
        target = dataset/'inductor'/split/(name or source.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest.append(dict(source=str(source), destination=str(target), split=split,
                             sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    original = ROOT/'vision_assembly/inspection/datasets/pcb_components_strict_v4/inductor'
    for split in ['train/good', 'test/good', 'test/controlled_defect']:
        for path in sorted((original/split).glob('*.png')):
            copy(path, split)
    # Both slots explicitly confirmed normal in this scene, unlike mixed trials.
    normal_run = ROOT/'runtime/inspection/hybrid_fixed_slot/20260906_182517_135335'
    for i in [1, 2]:
        copy(normal_run/'patchcore_crops/inductor'/f'inductor_0{i}.png', 'train/good', f'normal182507_inductor_0{i}.png')
    recent = [
        ('20260906_183201_489371', [1, 2], 'normal'),
        ('20260906_183249_740026', [1, 2], 'normal'),
        ('20260906_183337_961766', [1, 2], 'normal'),
        ('20260906_184959_868834', [1], 'normal'),
        ('20260906_172537_068340', [2], 'direction_defect'),
        ('20260906_174102_525585', [2], 'direction_defect'),
        ('20260906_175326_427204', [2], 'direction_defect'),
        ('20260906_184959_868834', [2], 'direction_defect'),
    ]
    for run, slots, label in recent:
        for i in slots:
            source = ROOT/'runtime/inspection/hybrid_fixed_slot'/run/'patchcore_crops/inductor'/f'inductor_0{i}.png'
            copy(source, 'holdout/'+label, f'{run}_inductor_0{i}.png')
    train_hashes = {r['sha256'] for r in manifest if r['split']=='train/good'}
    assert not any(r['sha256'] in train_hashes for r in manifest if r['split']!='train/good'), 'Train/eval duplicate'
    (out/'manifest.json').write_text(json.dumps(dict(files=manifest,
        policy='CANDIDATE_ONLY; recent holdout never passed to trainer',
        limitations='Same physical parts; recent normal repeats are temporally related to added training scene, not independent production validation.'), indent=2)+'\n')
    models = out/'models'
    train_component('inductor', dataset, models, 0, .1, 'test/controlled_defect', ('layer2','layer3'),
                    backbone_checkpoint=_checkpoint(ROOT/'runtime/inspection/patchcore/pcb_components_strict_v4','inductor'))
    results = {}
    for label, model_root in [('active', ROOT/'runtime/inspection/patchcore/pcb_components_strict_v4'), ('candidate', models)]:
        values = []
        for split in ['test/good', 'test/controlled_defect', 'holdout/normal', 'holdout/direction_defect']:
            prediction = _predict_outputs('inductor', dataset/'inductor'/split,
                                           _checkpoint(model_root,'inductor'), out/'eval'/label/split)
            values.extend(dict(name=n, split=split, score=float(v['score'])) for n,v in prediction.items())
        normals = [r['score'] for r in values if r['split'] in ['test/good','holdout/normal']]
        defects = [r['score'] for r in values if r['split'] in ['test/controlled_defect','holdout/direction_defect']]
        results[label] = dict(rows=values, normal_max=max(normals), defect_min=min(defects),
                              gap=min(defects)-max(normals),
                              defects_below_normal_max=sum(v<=max(normals) for v in defects))
    (out/'comparison.json').write_text(json.dumps(dict(results=results, deployed=False,
        limitation='Test data partially used by trainer validation; only recent holdout excluded from training/calibration. Surface-crack performance not established.'),indent=2)+'\n')
    print(json.dumps({k:{a:b for a,b in v.items() if a!='rows'} for k,v in results.items()},indent=2))


if __name__ == '__main__':
    main()
