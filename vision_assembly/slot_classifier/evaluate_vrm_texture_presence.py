"""Offline central-texture presence probe; never activates a production model.

Frozen ImageNet features consume original RGB without CLAHE. Central crops
deliberately exclude socket edges: pose and seating remain separate tasks.
"""
from pathlib import Path
import json
import sys
import argparse

import cv2
import numpy as np
import torch
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneGroupOut
from torchvision import models, transforms

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'vision_assembly/hybrid_inspection'))
from preprocessor_and_cropper import FixedSlotCropper


def central_rgb(board, geometry, scale=.55):
    x, y, w, h = geometry
    crop = cv2.getRectSubPix(board, (max(8, round(w * scale)), max(8, round(h * scale))), (float(x), float(y)))
    return Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--context', action='store_true', help='Concatenate central texture and 1.30x socket context features')
    parser.add_argument('--stress', action='store_true', help='Offline input sensitivity checks, never additional physical samples')
    args = parser.parse_args()
    torch.set_num_threads(2)
    torch.manual_seed(20260905)
    model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1)
    model.classifier = torch.nn.Identity()
    model.eval()
    transform = transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(),
        transforms.Normalize((.485,.456,.406),(.229,.224,.225))])
    cropper = FixedSlotCropper(ROOT / 'vision_assembly/config/full_board_inspection.json')
    cache = {}
    board_cache = {}

    def features(path, slot_id):
        if path not in cache:
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError(f'Cannot read {path}')
            board = cropper.register(image)
            if board.alignment_reason != 'OK':
                raise ValueError(f'Uncertain registration: {path}')
            slots = [s for s in cropper.fixed_slots(board.image_bgr) if s.component_type == 'VRM']
            board_cache[path] = (board.image_bgr, slots)
            scales = (.55, 1.30) if args.context else (.55,)
            batch = torch.stack([transform(central_rgb(board.image_bgr, s.geometry, scale))
                                 for s in slots for scale in scales])
            with torch.inference_mode():
                vectors = model(batch).numpy().reshape(len(slots), -1)
            cache[path] = {s.slot_id: v for s, v in zip(slots, vectors)}
        return cache[path][slot_id]

    dataset = ROOT / 'vision_assembly/slot_classifier/datasets/vrm_state_v2'
    rows = [json.loads(line) for line in (dataset/'manifest.jsonl').read_text().splitlines() if line]
    x = np.stack([features(dataset/r['source_image'], r['slot_id']) for r in rows])
    y = np.array([int(r['label'] != 'empty') for r in rows])
    groups = np.array([r['scene_id'] for r in rows])
    predictions = np.zeros(len(rows), int)
    probabilities = np.zeros(len(rows))
    for train, test in LeaveOneGroupOut().split(x,y,groups):
        clf = LogisticRegression(C=1.0, class_weight='balanced', max_iter=2000)
        clf.fit(x[train], y[train])
        predictions[test] = clf.predict(x[test])
        probabilities[test] = clf.predict_proba(x[test])[:,1]
    clf = LogisticRegression(C=1.0,class_weight='balanced',max_iter=2000).fit(x,y)
    session = json.loads((ROOT/'vision_assembly/config/vrm_seating_session_20260905.json').read_text())
    fresh = []
    for scene in session['scenes']:
        for slot_id in sorted(scene['labels']):
            prob = float(clf.predict_proba(features(ROOT/scene['image'],slot_id)[None])[:,1][0])
            fresh.append({'scene':scene['physical_scene_id'],'slot_id':slot_id,
                'expected':'EMPTY' if scene['labels'][slot_id] == 'EMPTY' else 'PRESENT','present_probability':prob,
                'prediction':'PRESENT' if prob >= .5 else 'EMPTY'})
    report = {'authority':'ADVISORY_ONLY','runtime_enabled':False,
        'method':('central55_context130_RGB_frozen_EfficientNetB0_logistic_C1'
                  if args.context else 'central_55pct_original_RGB_frozen_EfficientNetB0_logistic_C1'),
        'session_role':'development_regression_already_inspected; not blind validation',
        'validation':'leave_one_scene_id_out; split validity limited by recorded scene IDs',
        'counts':{'empty':int(sum(y==0)),'present':int(sum(y==1))},
        'cross_validation':[
            {'scene':r['scene_id'],'slot_id':r['slot_id'],'expected':int(y[i]),
             'prediction':int(predictions[i]),'present_probability':float(probabilities[i])}
            for i,r in enumerate(rows)],
        'empty_recall':float(np.mean(predictions[y==0]==0)),
        'present_recall':float(np.mean(predictions[y==1]==1)),
        'fresh_session':fresh,
        'limitations':['Only five historical empty observations.',
            'Fresh session observations share physical setups; not independent slot trials.',
            'Central presence cannot detect seating or displaced parts outside the crop.'],
        'robot_command_sent':False,'conveyor_command_sent':False}
    stress = []
    if args.stress:
        for scene in session['scenes']:
            board, slots = board_cache[ROOT/scene['image']]
            for name, gain, dx, dy in [('dark',.85,0,0),('bright',1.15,0,0),
                                       ('left',1.,-3,0),('right',1.,3,0),
                                       ('up',1.,0,-3),('down',1.,0,3)]:
                altered = np.clip(board.astype(np.float32)*gain,0,255).astype(np.uint8)
                scales = (.55,1.30) if args.context else (.55,)
                batch = torch.stack([transform(central_rgb(altered,
                    (s.geometry[0]+dx,s.geometry[1]+dy,*s.geometry[2:]),scale))
                    for s in slots for scale in scales])
                with torch.inference_mode():
                    vectors = model(batch).numpy().reshape(len(slots),-1)
                probs = clf.predict_proba(vectors)[:,1]
                for s,prob in zip(slots,probs):
                    stress.append({'scene':scene['physical_scene_id'],'slot_id':s.slot_id,
                        'perturbation':name,'expected':'EMPTY' if scene['labels'][s.slot_id]=='EMPTY' else 'PRESENT',
                        'prediction':'PRESENT' if prob>=.5 else 'EMPTY','present_probability':float(prob)})
    report['synthetic_input_stress'] = stress
    report['stress_note'] = 'Sensitivity diagnostics only; not physical validation or training augmentation.'
    args.output.mkdir(parents=True,exist_ok=True)
    np.savez(args.output/'classifier_candidate.npz',coef=clf.coef_,intercept=clf.intercept_,classes=clf.classes_)
    (args.output/'evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['counts','empty_recall','present_recall']}))
    for label in ('EMPTY', 'PRESENT'):
        subset = [r for r in fresh if r['expected'] == label]
        print('fresh', label, sum(r['prediction']==label for r in subset), '/', len(subset))
    print('report',args.output/'evaluation.json')
    if stress:
        print('stress errors',sum(r['expected']!=r['prediction'] for r in stress),'/',len(stress))


if __name__ == '__main__':
    main()
