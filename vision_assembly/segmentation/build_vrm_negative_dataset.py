"""Explicit reviewed empty crops for supervised segmentation only."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main():
    base=ROOT/'vision_assembly/segmentation/vrm_fixed_boundary_dataset_v3'
    source=ROOT/'vision_assembly/segmentation/vrm_negative_review_v1'
    output=ROOT/'vision_assembly/segmentation/vrm_fixed_boundary_dataset_v4'
    if output.exists():
        raise FileExistsError(output)
    review=json.loads((source/'review.json').read_text())
    pending=json.loads((source/'manifest.json').read_text())['rows']
    if review['status']!='ASSISTANT_VISUALLY_REVIEWED_EMPTY_CROPS' or set(review['accepted_stems'])!={r['stem'] for r in pending}:
        raise ValueError('Explicit review required')
    manifest=json.loads((base/'manifest.json').read_text())
    added_scenes={r['scene'] for r in pending}
    for r in pending:
        path=source/(r['stem']+'.png')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=r['crop_sha256']:
            raise ValueError('Changed reviewed crop')
        if hashlib.sha256(Path(r['source_image']).read_bytes()).hexdigest()!=r['source_sha256']:
            raise ValueError('Changed scene')
        if manifest['scene_splits'].get(r['scene']) in {'val','test'}:
            raise ValueError('Scene leakage')
    output.mkdir()
    for row in manifest['rows']:
        for kind,ext in [('images','.png'),('labels','.txt')]:
            dest=output/kind/row['split']
            dest.mkdir(parents=True,exist_ok=True)
            shutil.copy2(base/kind/row['split']/(row['stem']+ext),dest/(row['stem']+ext))
    for row in pending:
        stem=row['stem']
        shutil.copy2(source/(stem+'.png'),output/'images/train'/(stem+'.png'))
        (output/'labels/train'/(stem+'.txt')).write_text('')
        manifest['rows'].append(dict(row,split='train',visible_instances=0,
            annotation_origin='assistant visual review: empty socket, no discernible VRM body',
            normal_patchcore_training_allowed=False))
    manifest['counts']['train']+=len(pending)
    manifest['scene_splits'].update({s:'train' for s in added_scenes})
    manifest['adaptation_scene_ids']=sorted(set(manifest['adaptation_scene_ids'])|added_scenes)
    manifest['retained_development_validation_scene_ids']=sorted(set(manifest['retained_development_validation_scene_ids'])-added_scenes)
    manifest['limitation']='Five reviewed empty crops added for supervised boundary learning only; exclude their entire scenes from development evaluation. Not normal PatchCore data. Normal val/test unchanged and reused, not blind.'
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (output/'vrm.yaml').write_text(f'path: {json.dumps(str(output))}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: vrm\n')
    print(manifest['counts'])


if __name__=='__main__':
    main()
