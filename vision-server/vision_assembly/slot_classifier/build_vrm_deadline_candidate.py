"""Build isolated developmental dataset. Never overwrite active models/data."""
import hashlib
import json
from pathlib import Path
import sys
import cv2

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'vision_assembly/hybrid_inspection'))
from preprocessor_and_cropper import FixedSlotCropper
from vrm_state_common import crop_vrm_state_slot, VRM_STATE_CROP_PIPELINE


def main():
    output=ROOT/'runtime/inspection/vrm_deadline_candidate_20260909/dataset'
    output.mkdir(parents=True,exist_ok=False)
    (output/'crops').mkdir()
    old=ROOT/'vision_assembly/slot_classifier/datasets/vrm_state_v2'
    rows=[json.loads(l) for l in (old/'manifest.jsonl').read_text().splitlines() if l]
    for row in rows:
        row['crop_image']=str(old/row['crop_image'])
        if not Path(row['crop_image']).is_file(): raise ValueError('Missing historical crop')
    base=ROOT/'runtime/inspection/vrm_direction_followup_20260909'
    # Only explicitly requested target states, not inferred neighbour labels.
    controls=[
        (ROOT/'runtime/inspection/normal_validation_20260909/20260909_104727_014632',{f'vrm_{i:02}':'correct' for i in range(1,6)}),
        (base/'fresh_rotated_vrm2/20260909_114305_740435',{'vrm_02':'rotated'}),
        (base/'fresh_rotated_vrm3/20260909_133021_748728',{'vrm_03':'rotated'}),
        (base/'fresh_rotated_vrm4/20260909_120026_970654',{'vrm_04':'rotated'}),
        (base/'fresh_rotated_vrm5/20260909_131152_674429',{'vrm_05':'rotated'}),
        (base/'fresh_missing_vrm2/20260909_115148_417384',{'vrm_02':'empty'}),
        (base/'fresh_missing_vrm1_vrm4_vrm5/20260909_133552_676235',{'vrm_01':'empty','vrm_04':'empty','vrm_05':'empty'}),
    ]
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    for run,labels in controls:
        report=json.loads((run/'hybrid_report.json').read_text())
        source=Path(report['input_image'])
        if hashlib.sha256(source.read_bytes()).hexdigest()!=report['input_sha256']:
            raise ValueError('Source mismatch')
        image=cv2.imread(str(run/'aligned_board.png'))
        if image is None: raise ValueError('Missing aligned board')
        slots={s.slot_id:s for s in cropper.fixed_slots(image)}
        for sid,label in labels.items():
            path=output/'crops'/f'{run.name}_{sid}.png'
            if not cv2.imwrite(str(path),crop_vrm_state_slot(image,slots[sid].geometry)):
                raise ValueError('Write failed')
            rows.append(dict(scene_id='controlled_'+run.name,slot_id=sid,label=label,
                             crop_image=str(path),source_sha256=report['input_sha256'],
                             illumination='ambient',crop_pipeline=VRM_STATE_CROP_PIPELINE,
                             provenance='Previously user-acknowledged target placement; developmental data',report=str(run/'hybrid_report.json')))
    with (output/'manifest.jsonl').open('x') as stream:
        for row in rows: stream.write(json.dumps(row)+'\n')
    (output/'limitations.json').write_text(json.dumps(dict(
        training_rows=len(rows),fresh_153954_and_154203_excluded=True,
        current_144833_excluded_same_placement=True,
        independent_parts=False,old_model_already_exposed_to_historical_validation=True,
        promotion_allowed=False),indent=2))
    print(output,len(rows))


if __name__=='__main__': main()
