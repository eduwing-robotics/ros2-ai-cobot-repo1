"""Export explicitly visually reviewed manual labels, not SAM predictions."""
import hashlib
import json
import cv2
import numpy as np
from pathlib import Path
from common import save_yolo_segments

ROOT=Path(__file__).resolve().parents[2]


def main():
    root=ROOT/'vision_assembly/segmentation/vrm_boundary_adaptation_v1'
    decision=json.loads((root/'manual_polygon_drafts.json').read_text())
    if decision.get('status')!='ASSISTANT_VISUALLY_REVIEWED_EXPERIMENTAL_BOUNDARY_LABELS':
        raise ValueError('Manual review required')
    partition=json.loads((root/'partition.json').read_text())
    if set(partition['adaptation_scene_ids']) & set(partition['retained_development_validation_scene_ids']):
        raise ValueError('Scene overlap')
    targets=root/'reviewed_labels'
    targets.mkdir(exist_ok=False)
    for row in partition['rows']:
        stem=row['stem']
        image_path=root/'images'/f'{stem}.png'
        if hashlib.sha256(image_path.read_bytes()).hexdigest()!=row['crop_sha256']:
            raise ValueError('Crop changed')
        image=cv2.imread(str(image_path))
        poly=np.float32(decision['polygons'][stem])
        if abs(cv2.contourArea(poly))<4 or not cv2.isContourConvex(poly):
            raise ValueError('Invalid manual polygon')
        save_yolo_segments(targets/f'{stem}.txt',[(3,poly)],image.shape[1],image.shape[0])
        review=dict(status='EXPERIMENTAL_BOUNDARY_REVIEWED',reviewer='assistant',
            annotation_origin='manual polygon, not SAM pseudo-label',
            supervised_boundary_training_allowed=True,normal_patchcore_training_allowed=False,
            pose_label=row['expected_pose'],scene_id=row['scene_id'],source_sha256=row['source_sha256'],
            crop_sha256=row['crop_sha256'],label_sha256=hashlib.sha256((targets/f'{stem}.txt').read_bytes()).hexdigest(),
            limitation=decision['review_basis'])
        (root/'reviews'/f'{stem}.json').write_text(json.dumps(review,indent=2))
    print('Exported3 experimental manual masks; no training performed. Generic COMPLETE not set.')


if __name__=='__main__':
    main()
