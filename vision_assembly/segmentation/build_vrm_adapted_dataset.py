"""Explicit opt-in to reviewed defect body masks, not normal anomaly training."""
import hashlib
import json
import shutil
from pathlib import Path
import cv2
from common import load_yolo_segments,save_yolo_segments

ROOT=Path(__file__).resolve().parents[2]


def main():
    original=ROOT/'vision_assembly/segmentation/vrm_fixed_boundary_dataset_v2'
    adaptation=ROOT/'vision_assembly/segmentation/vrm_boundary_adaptation_v1'
    output=ROOT/'vision_assembly/segmentation/vrm_fixed_boundary_dataset_v3'
    if output.exists():
        raise ValueError('Refusing overwrite')
    partition=json.loads((adaptation/'partition.json').read_text())
    manifest=json.loads((original/'manifest.json').read_text())
    adapted=set(partition['adaptation_scene_ids'])
    retained=set(partition['retained_development_validation_scene_ids'])
    if adapted & retained or adapted & set(manifest['scene_splits']):
        raise ValueError('Scene overlap')
    additions=[]
    for row in partition['rows']:
        stem=row['stem']
        review=json.loads((adaptation/'reviews'/f'{stem}.json').read_text())
        if review.get('status')!='EXPERIMENTAL_BOUNDARY_REVIEWED' or not review.get('supervised_boundary_training_allowed'):
            raise ValueError('Reviewed manual boundary required')
        image=adaptation/'images'/f'{stem}.png'
        label=adaptation/'reviewed_labels'/f'{stem}.txt'
        if hashlib.sha256(image.read_bytes()).hexdigest()!=review['crop_sha256'] or hashlib.sha256(label.read_bytes()).hexdigest()!=review['label_sha256']:
            raise ValueError('Reviewed artifacts changed')
        pixels=cv2.imread(str(image))
        h,w=pixels.shape[:2]
        segments=load_yolo_segments(label,w,h)
        if len(segments)!=1 or segments[0][0]!=3:
            raise ValueError('Expected one reviewed VRM')
        additions.append((image,segments[0][1],w,h,dict(stem=stem,scene=row['scene_id'],split='train',
            slot=row['slot_id'],source_image=row['source_image'],source_sha256=row['source_sha256'],
            source_label_sha256=review['label_sha256'],annotation_origin='assistant reviewed approximate body polygon',
            physical_pose='FAIL',normal_patchcore_training_allowed=False,visible_instances=1)))
    output.mkdir(parents=True)
    for row in manifest['rows']:
        for kind,suffix in [('images','.png'),('labels','.txt')]:
            directory=output/kind/row['split']
            directory.mkdir(parents=True,exist_ok=True)
            shutil.copy2(original/kind/row['split']/(row['stem']+suffix),directory/(row['stem']+suffix))
    for image,poly,w,h,row in additions:
        shutil.copy2(image,output/'images/train'/image.name)
        save_yolo_segments(output/'labels/train'/(row['stem']+'.txt'),[(0,poly)],w,h)
        manifest['rows'].append(row)
    manifest['counts']['train']+=len(additions)
    manifest['total_visible_instances']+=len(additions)
    manifest['scene_splits'].update({s:'train' for s in adapted})
    manifest.update(adaptation_scene_ids=sorted(adapted),retained_development_validation_scene_ids=sorted(retained),
        limitation='Normal base plus3 reviewed defect body polygons for supervised boundary only; no normal PatchCore use. Existing normal test is repeated regression, not fresh blind validation. Exclude entire adaptation scenes from saved-scene evaluation.')
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (output/'vrm.yaml').write_text(f'path: {json.dumps(str(output))}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: vrm\n')
    print(manifest['counts'])


if __name__=='__main__':
    main()
