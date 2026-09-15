"""Isolated normal-only photometric augmentation; no runtime geometry changes."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'vision_assembly/inspection'))
from train_component_patchcore import train_component
from predict_component_patchcore import _checkpoint, _predict_outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-current-normal', action='store_true')
    parser.add_argument('--include-restored-i2', action='store_true',
                        help='Include user-confirmed normal I2 from202933; evaluate203108 separately.')
    parser.add_argument('--include-normal-repeat', action='store_true')
    parser.add_argument('--include-confirmed-i1-205808', action='store_true')
    args = parser.parse_args()
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    if args.include_confirmed_i1_205808:
        args.include_normal_repeat = True
    if args.include_normal_repeat:
        args.include_restored_i2 = True
    if args.include_restored_i2:
        args.include_current_normal = True
    name = ('inductor_restored_pair_candidate_20260906' if args.include_restored_i2 else
            'inductor_current_normal_candidate_20260906' if args.include_current_normal else 'inductor_photometric_candidate_20260906')
    if args.include_normal_repeat:
        name = 'inductor_restored_repeat_candidate_20260906'
    if args.include_confirmed_i1_205808:
        name = 'inductor_confirmed_i1_candidate_20260906'
    out = ROOT/'runtime/inspection/patchcore'/name
    out.mkdir(exist_ok=False)
    source = ROOT/'runtime/inspection/patchcore/inductor_appearance_candidate_20260906/dataset'
    dataset = out/'dataset'
    shutil.copytree(source, dataset)
    promoted = '20260906_195041_935881' if args.include_current_normal else None
    if promoted:
        # User explicitly says I1 is normal/untouched. Only this slot, never I2,
        # from one development scene; adjacent-time scenes remain evaluation.
        shutil.copy2(ROOT/'runtime/inspection/inductor_capture_repeat_20260906'/promoted/'patchcore_crops/inductor/inductor_01.png',
                     dataset/'inductor/train/good/current_normal_i1.png')
    restored_source = ROOT/'runtime/inspection/hybrid_fixed_slot/20260906_202943_105443/patchcore_crops/inductor/inductor_02.png'
    if args.include_restored_i2:
        shutil.copy2(restored_source,dataset/'inductor/train/good/restored_normal_i2.png')
    repeat_source = ROOT/'runtime/inspection/inductor_restored_pair_live_20260906/20260906_204004_286842/patchcore_crops/inductor/inductor_02.png'
    if args.include_normal_repeat:
        shutil.copy2(repeat_source,dataset/'inductor/train/good/restored_repeat_normal_i2.png')
    confirmed_i1 = ROOT/'runtime/inspection/hybrid_fixed_slot/20260906_205818_570243/patchcore_crops/inductor/inductor_01.png'
    if args.include_confirmed_i1_205808:
        # User explicitly confirmed this I1 normal; I2 in same image is defective.
        shutil.copy2(confirmed_i1,dataset/'inductor/train/good/confirmed_normal_i1_205808.png')
    manifest = []
    # Pixelwise RGB changes only: do not blur, move, rotate, or recenter parts.
    variants = [('dark', .9, (1,1,1)), ('light', 1.1, (1,1,1)),
                ('warm', 1., (.94,1,1.04)), ('cool', 1., (1.04,1,.94)),
                ('gamma_dark', 1., (1,1,1)), ('gamma_light', 1., (1,1,1))]
    for path in sorted((dataset/'inductor/train/good').glob('*.png')):
        im = cv2.imread(str(path)).astype(np.float32)/255
        for name, gain, bgr in variants:
            gamma = {'gamma_dark':1.15, 'gamma_light':.85}.get(name,1)
            transformed = np.uint8(np.clip((im**gamma)*gain*np.asarray(bgr)*255,0,255))
            target = path.with_name(path.stem+'__'+name+'.png')
            if not cv2.imwrite(str(target), transformed):
                raise RuntimeError(str(target))
            manifest.append(dict(source=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                 target=str(target),gain=gain,gamma=gamma,bgr=bgr))
    # Evaluation-only physical captures; neither these nor their transforms enter fit.
    folders = ['inductor_capture_repeat_20260906', 'board_focus_trial_20260906',
               'focus_lock_trial_20260906', 'hybrid_inductor_candidate_validation']
    for folder in folders:
        for report in sorted((ROOT/'runtime/inspection'/folder).glob('*/hybrid_report.json')):
            if report.parent.name == promoted:
                continue  # entire source scene excluded from evaluation
            for idx, label in [(1,'normal'),(2,'direction_defect')]:
                dst = dataset/'inductor'/('fresh/'+label)
                dst.mkdir(parents=True,exist_ok=True)
                shutil.copy2(report.parent/f'patchcore_crops/inductor/inductor_0{idx}.png',
                             dst/f'{folder}_{report.parent.name}_inductor_0{idx}.png')
    train_hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in (dataset/'inductor/train/good').glob('*.png')}
    if args.include_restored_i2:
        for idx in [1,2]:
            # Separate physical capture; same parts/lighting remains a limitation.
            dst = dataset/'inductor/fresh/normal'
            shutil.copy2(ROOT/f'runtime/inspection/hybrid_fixed_slot/20260906_203118_756503/patchcore_crops/inductor/inductor_0{idx}.png',
                         dst/f'normal_restored_203108_inductor_0{idx}.png')
    for p in (dataset/'inductor').rglob('*.png'):
        if 'train' not in p.parts and hashlib.sha256(p.read_bytes()).hexdigest() in train_hashes:
            raise RuntimeError('Train/eval duplicate: '+str(p))
    (out/'manifest.json').write_text(json.dumps(dict(augmentations=manifest,promoted_normal_scene=promoted,
        restored_normal_source=str(restored_source) if args.include_restored_i2 else None,
        repeat_normal_source=str(repeat_source) if args.include_normal_repeat else None,
        confirmed_i1_source=str(confirmed_i1) if args.include_confirmed_i1_205808 else None,
        policy='CANDIDATE_ONLY; no spatial augmentation; fresh mixed scenes use only I1 NORMAL and I2 direction defect from user observations; not independent physical-part validation'),indent=2))
    models = out/'models'
    train_component('inductor',dataset,models,0,.05,'test/controlled_defect',('layer2','layer3'),
        backbone_checkpoint=_checkpoint(ROOT/'runtime/inspection/patchcore/pcb_components_strict_v4','inductor'))
    rows=[]
    for split in ['test/good','test/controlled_defect','holdout/normal','holdout/direction_defect','fresh/normal','fresh/direction_defect']:
        pred=_predict_outputs('inductor',dataset/'inductor'/split,_checkpoint(models,'inductor'),out/'eval'/split)
        rows.extend(dict(name=n,split=split,score=float(v['score'])) for n,v in pred.items())
    normal=[r['score'] for r in rows if r['split'].endswith(('good','normal'))]
    bad=[r['score'] for r in rows if r['split'].endswith('defect')]
    result=dict(rows=rows,normal_max=max(normal),defect_min=min(bad),gap=min(bad)-max(normal),deployed=False,
                limitation='No labeled surface-crack validation; test partly used for trainer validation. No automatic authority.')
    (out/'comparison.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':
    main()
