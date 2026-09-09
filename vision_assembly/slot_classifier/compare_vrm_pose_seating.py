"""Compare frozen seating and geometry on the same saved registered pixels."""
import hashlib
import json
from pathlib import Path
import sys

import cv2
import torch
from PIL import Image
from torchvision import transforms

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'vision_assembly/hybrid_inspection'))
from preprocessor_and_cropper import FixedSlotCropper, VrmStateClassifier
from vrm_seating_common import crop_vrm_seating_slot


def main():
    torch.set_num_threads(2)
    base=ROOT/'runtime/inspection/vrm_fixed_pose_offline_20260905'
    geometry=json.loads((base/'evaluation.json').read_text())
    manifest=json.loads((ROOT/'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())
    bridge=ROOT/'runtime/inspection/vrm_multiscale_seating_plus_165057/integration_bridge'
    assert json.loads((bridge/'vrm_seating.json').read_text())['runtime_enabled'] is False
    model=torch.jit.load(str(bridge/'vrm_seating.torchscript.pt'),map_location='cpu').eval()
    state=VrmStateClassifier(ROOT/'vision_assembly/slot_classifier/models',device='cpu')
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    transform=transforms.Compose([transforms.Resize((224,224)),transforms.ToTensor(),
        transforms.Normalize((.485,.456,.406),(.229,.224,.225))])
    index={(r['scene'],r['slot']):r for r in geometry['rows']}
    rows=[]
    source_checks=[]
    for i,scene in enumerate(manifest['scenes']):
        source=ROOT/scene['image']
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        expected_hash=scene.get('image_sha256')
        if expected_hash is None:
            archived=json.loads((ROOT/scene['report']).read_text())
            expected_hash=archived.get('input_sha256',archived.get('image_sha256'))
        if expected_hash is not None:
            assert digest==expected_hash, f'Source changed: {source}'
        source_checks.append(dict(image=str(source),sha256=digest,archived_hash_verified=expected_hash is not None))
        board=cv2.imread(str(base/str(i)/'aligned.png'))
        assert board is not None
        slots=[s for s in cropper.fixed_slots(board) if s.component_type=='VRM']
        batch=torch.stack([transform(Image.fromarray(cv2.cvtColor(
            crop_vrm_seating_slot(board,s.geometry),cv2.COLOR_BGR2RGB))) for s in slots])
        with torch.inference_mode():
            scores=model(batch).softmax(1)[:,1].tolist()
        for slot,score in zip(slots,scores):
            presence=state.inspect(slot,board)
            nonempty=1-float(presence.probabilities.get('EMPTY',1))
            row=dict(scene=scene['physical_scene_id'],slot=slot.slot_id,
                     presence_label=scene['labels'].get(slot.slot_id),
                     expected=scene.get('expected_pose',{}).get(slot.slot_id),
                     seating_score=score,nonempty=nonempty,
                     seating_warning=bool(score>=.5 and nonempty>=.9))
            g=index.get((row['scene'],row['slot']))
            row['geometry_warning']=g['warning'] if g else None
            rows.append(row)
    summary={}
    for mode in ('seating','geometry','either','both'):
        counts={'normal':0,'false_warning':0,'defect':0,'detected':0}
        for row in rows:
            if row['expected'] not in ('PASS','FAIL') or row['presence_label']!='PRESENT':
                continue
            a,b=row['seating_warning'],row['geometry_warning']
            assert b is not None
            warning={'seating':a,'geometry':b,'either':a or b,'both':a and b}[mode]
            if row['expected']=='PASS':
                counts['normal']+=1
                counts['false_warning']+=int(warning)
            else:
                counts['defect']+=1
                counts['detected']+=int(warning)
        summary[mode]=counts
    historical=[]
    dataset=ROOT/'vision_assembly/slot_classifier/datasets/vrm_seating_v3'
    for line in (dataset/'manifest.jsonl').read_text().splitlines():
        entry=json.loads(line)
        if entry['split']!='holdout':
            continue
        crop=dataset/entry['crop_image']
        assert hashlib.sha256(crop.read_bytes()).hexdigest()==entry['crop_sha256']
        with Image.open(crop) as img:
            tensor=transform(img.convert('RGB')).unsqueeze(0)
        with torch.inference_mode():
            score=float(model(tensor).softmax(1)[0,1])
        historical.append(dict(scene=entry['scene_id'],slot=entry['slot_id'],
                               expected=entry['label'],score=score,warning=score>=.5))
    report=dict(summary=summary,rows=rows,source_checks=source_checks,
        historical_holdout=historical,
        model_sha256=hashlib.sha256((bridge/'vrm_seating.torchscript.pt').read_bytes()).hexdigest(),
        runtime_enabled=False,authority='ADVISORY_ONLY',training_performed=False,
        note='Retrospective development replay, not independent deployment certification. '
             'OR/AND are diagnostic comparisons only; no rule installed. No warning is not PASS.',
        robot_command_sent=False,conveyor_command_sent=False)
    (base/'seating_comparison.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(summary,indent=2))
    print('Historical holdout:',json.dumps(historical))


if __name__=='__main__':
    main()
