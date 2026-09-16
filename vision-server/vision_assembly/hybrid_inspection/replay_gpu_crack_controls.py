"""Replay user-labelled current defects and archived normal surface crops.

Archived surface crops have different framing; abstentions are not successful
normal classifications. No source file, model or training label is modified.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import cv2
from gpu_surface_crack import inspect_gpu_crack


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    paths = [('user_labelled_current_crack',root/'runtime/inspection/hybrid_fixed_slot'/run/'fixed_slots/gpu/ai_gpu.png')
             for run in ('20260914_201154_859671','20260914_201837_148806',
                         '20260914_202207_020385','20260914_202531_682221')]
    dataset = root/'vision_assembly/inspection/datasets/gpu_surface_crack_v1/gpu'
    for split in ('train/good','test/good','test/crack'):
        paths.extend((split,path) for path in sorted((dataset/split).glob('*.png')))
    rows = []
    for label,path in paths:
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(str(path))
        e = inspect_gpu_crack(image,'PRESENT',True)
        rows.append(dict(label=label,path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),evidence=asdict(e)))
    summary = {label:dict(total=sum(r['label']==label for r in rows),
                         candidates=sum(r['label']==label and r['evidence']['status']=='FAIL' for r in rows),
                         abstained=sum(r['label']==label and 'roi_crop_xyxy' not in r['evidence']['measured'] for r in rows))
               for label in dict.fromkeys(r['label'] for r in rows)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(summary=summary,rows=rows,
        limitation='Current defect photographs are development data and repeated views of one GPU. Archived normals differ in framing/illumination; no matched independent normal or accuracy qualification.'),indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
