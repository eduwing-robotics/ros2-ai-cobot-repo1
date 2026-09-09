"""Review archived explicit-empty SMD01 references in the current board frame."""
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from preprocessor_and_cropper import FixedSlotCropper

ROOT = Path(__file__).resolve().parents[2]


def main():
    dataset = ROOT / 'vision_assembly/slot_classifier/datasets/component_presence_v1'
    rows = [json.loads(line) for line in (dataset/'manifest.jsonl').read_text().splitlines() if line.strip()]
    rows = [r for r in rows if r['slot_id'] == 'smd_capacitor_01' and r['label'] == 'empty']
    out = ROOT / 'runtime/inspection/smd01_empty_reference_audit_20260907'
    out.mkdir(exist_ok=False)
    cropper = FixedSlotCropper(ROOT / 'vision_assembly/config/full_board_inspection.json')
    tiles, results = [], []
    for row in rows:
        source = dataset / row['source_image']
        sha = hashlib.sha256(source.read_bytes()).hexdigest()
        if sha != row['source_sha256']:
            raise RuntimeError(f'Source hash changed: {source}')
        registered = cropper.register(cv2.imread(str(source)))
        if registered.alignment_reason != 'OK' or registered.alignment_score < cropper.config['global_alignment']['minimum_score']:
            results.append(dict(source=str(source),accepted=False,reason=registered.alignment_reason,score=registered.alignment_score))
            continue
        slot = next(s for s in cropper.fixed_slots(registered.image_bgr) if s.slot_id == 'smd_capacitor_01')
        cx,cy,_,_ = slot.geometry
        x,y = int(cx)-90,int(cy)-70
        crop = registered.image_bgr[y:y+140,x:x+180].copy()
        gray = cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
        local = cv2.createCLAHE(clipLimit=2.,tileGridSize=(8,8)).apply(gray)
        edges = cv2.Canny(local,50,120)
        panels = np.hstack([crop,cv2.cvtColor(local,cv2.COLOR_GRAY2BGR),cv2.cvtColor(edges,cv2.COLOR_GRAY2BGR)])
        panel = cv2.resize(panels,None,fx=2,fy=2,interpolation=cv2.INTER_NEAREST)
        tile = cv2.copyMakeBorder(panel,35,0,0,0,cv2.BORDER_CONSTANT,value=(25,25,25))
        cv2.putText(tile,f"{source.stem} EMPTY | ORIGINAL / CLAHE / EDGES | ALIGN {registered.alignment_score:.3f}",
                    (8,24),cv2.FONT_HERSHEY_SIMPLEX,.52,(230,230,230),1,cv2.LINE_AA)
        tiles.append(tile)
        cv2.imwrite(str(out/(source.stem+'_crop.png')),crop)
        results.append(dict(source=str(source),sha256=sha,accepted=True,score=registered.alignment_score,
                            crop_origin=[x,y],source_label='explicit_empty_presence_only'))
    if tiles:
        cv2.imwrite(str(out/'comparison.png'),np.vstack(tiles))
    (out/'audit.json').write_text(json.dumps(dict(rows=results,
        policy='Diagnostic only; registration is board-level, no component-local alignment. Accepted means usable registration, NOT certified socket-wall coordinates. No model or runtime changes.'),indent=2))
    print(json.dumps(results,indent=2))


if __name__ == '__main__':
    main()
