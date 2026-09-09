"""Build explicitly authorized training crops, rejecting reserved validation data."""
import hashlib
import json

import cv2

from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper
from vrm_seating_common import crop_vrm_seating_slot


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec=json.loads((ROOT/'vision_assembly/config/vrm_pose_training_session_20260905.json').read_text())
    if spec.get('training_allowed') is not True:
        raise ValueError('Training not authorized')
    reserved=json.loads((ROOT/spec['reserved_validation_manifest']).read_text())
    reserved_ids={s['physical_scene_id'] for s in reserved['scenes']}
    reserved_hashes={digest(ROOT/s['image']) for s in reserved['scenes']}
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    output=ROOT/'vision_assembly/slot_classifier/datasets/vrm_pose_session_20260905'
    records=[]
    for scene in spec['scenes']:
        if scene['split']=='excluded':
            continue
        path=ROOT/scene['image']
        sha=digest(path)
        if scene['split']!='train' or scene['physical_scene_id'] in reserved_ids or sha in reserved_hashes:
            raise ValueError('Reserved validation scene cannot enter training')
        if sha!=scene['image_sha256']:
            raise ValueError('Source hash mismatch')
        board=cropper.register(cv2.imread(str(path)))
        if board.alignment_reason!='OK' or board.alignment_score<float(cropper.config['global_alignment']['minimum_score']):
            raise ValueError('Uncertain registration')
        slots={s.slot_id:s for s in cropper.fixed_slots(board.image_bgr) if s.component_type=='VRM'}
        if set(scene['labels'])!=set(slots):
            raise ValueError('All five labels required')
        for slot_id,label in scene['labels'].items():
            if label not in ('NORMAL','PLACEMENT_DEFECT'):
                raise ValueError('Unexpected label')
            destination=output/'crops'/label.lower()/f"{scene['physical_scene_id']}__{slot_id}.png"
            destination.parent.mkdir(parents=True,exist_ok=True)
            crop=crop_vrm_seating_slot(board.image_bgr,slots[slot_id].geometry)
            if not cv2.imwrite(str(destination),crop):
                raise OSError('Crop write failed')
            records.append(dict(physical_scene_id=scene['physical_scene_id'],split='train',
                slot_id=slot_id,label=label,crop_image=str(destination.relative_to(output)),
                source_image=scene['image'],source_sha256=sha,crop_sha256=digest(destination),
                authority='EXPLICIT_USER_CONTROLLED',normal_patchcore_training_allowed=False))
    (output/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    print(f'Archived {len(records)} crops from {len({r["physical_scene_id"] for r in records})} physical training scenes; validation and excluded scenes omitted.')


if __name__=='__main__':
    main()
