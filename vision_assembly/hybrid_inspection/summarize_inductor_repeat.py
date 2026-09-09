"""Summarize stored frozen-setting capture repetition without changing models."""
import json
from pathlib import Path
import cv2
import numpy as np
from diagnose_inductor_capture_drift import metrics

ROOT=Path(__file__).resolve().parents[2]


def main():
    folder=ROOT/'runtime/inspection/inductor_capture_repeat_20260906'
    rows=[]
    tiles=[]
    for path in sorted(folder.glob('*/hybrid_report.json')):
        report=json.loads(path.read_text())
        i1=next(s for s in report['slots'] if s['slot_id']=='inductor_01')
        gpu=next(s for s in report['slots'] if s['slot_id']=='ai_gpu')
        im=cv2.imread(str(path.parent/'patchcore_crops/inductor/inductor_01.png'))
        score=i1['stages']['surface']['score']
        rows.append(dict(report=str(path),source=report['input_image'],sha256=report['input_sha256'],
            score=score,metrics=metrics(im),registration=report['registration'],
            gpu_orientation=gpu['stages']['orientation'],candidates=report['advisory_candidates']))
        tile=cv2.copyMakeBorder(cv2.resize(im,(336,336)),36,0,0,0,cv2.BORDER_CONSTANT)
        cv2.putText(tile,f'{path.parent.name[9:15]} score={score:.3f}',(5,24),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1,cv2.LINE_AA)
        tiles.append(tile)
    if len(rows)!=3 or len({r['sha256'] for r in rows})!=3:
        raise RuntimeError('Expected three distinct captures')
    cv2.imwrite(str(folder/'inductor1_repeat_comparison.jpg'),np.hstack(tiles))
    (folder/'summary.json').write_text(json.dumps(dict(rows=rows,
        policy='Unchanged placement requested; frozen model. Capture+rectification variability observed, exact cause not isolated; not training data.'),indent=2)+'\n')
    print(json.dumps([dict(score=r['score'],metrics=r['metrics'],gpu_reason=r['gpu_orientation']['reason']) for r in rows],indent=2))


if __name__=='__main__':
    main()
