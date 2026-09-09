"""Compare isolated candidate and deployed VRM model on held-out normal captures."""
import json
from dataclasses import asdict
from pathlib import Path
import sys
import cv2
import torch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'vision_assembly/hybrid_inspection'))
from preprocessor_and_cropper import FixedSlotCropper,VrmStateClassifier


def main():
    torch.set_num_threads(2)
    experiment=ROOT/'runtime/inspection/vrm_deadline_candidate_20260909'
    old=VrmStateClassifier(ROOT/'vision_assembly/slot_classifier/models',device='cpu')
    new=VrmStateClassifier(experiment/'model',device='cpu')
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    base=ROOT/'runtime/inspection/hbm_release_regression_20260909'
    runs=[base/'fresh_all_normal/20260909_154032_384501',base/'fresh_all_normal_repeat/20260909_154330_779617']
    training={json.loads(l)['source_sha256'] for l in (experiment/'dataset/manifest.jsonl').read_text().splitlines()}
    rows=[]
    for run in runs:
        report=json.loads((run/'hybrid_report.json').read_text())
        if report['input_sha256'] in training: raise ValueError('Test image in training manifest')
        image=cv2.imread(str(run/'aligned_board.png'))
        if image is None: raise ValueError('Missing aligned source')
        for slot in cropper.fixed_slots(image):
            if slot.component_type!='VRM': continue
            a,b=old.inspect(slot,image),new.inspect(slot,image)
            rows.append(dict(report=str(run/'hybrid_report.json'),slot_id=slot.slot_id,
                             truth='CORRECT',old=asdict(a),candidate=asdict(b)))
            print(run.name,slot.slot_id,a.predicted_state,round(a.confidence,3),'->',b.predicted_state,round(b.confidence,3))
    summary={name:sum(r[name]['predicted_state']=='CORRECT' for r in rows) for name in ('old','candidate')}
    with (experiment/'normal_comparison.json').open('x') as stream:
        json.dump(dict(rows=rows,correct_at_fixed_090=summary,observations=len(rows),
                       production_promoted=False,independent_physical_parts=False,
                       limitation='Same-position repeats, already inspected development images; excluded from candidate fitting, not untouched independent acceptance'),stream,indent=2)
    print(summary)


if __name__=='__main__': main()
