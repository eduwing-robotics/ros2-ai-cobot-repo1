"""Saved-crop comparison of pre-fit morning scenes and post-fit physical holdouts."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'vision_assembly/inspection'))
from predict_component_patchcore import _checkpoint, _predict_outputs


def main():
    base = ROOT / 'runtime/inspection'
    model = base / 'patchcore/inductor_morning_candidate_20260907'
    out = base / 'inductor_morning_score_comparison_20260907'
    out.mkdir(exist_ok=False)
    crops = out / 'crops'
    crops.mkdir()
    folders = [base / 'hybrid_fixed_slot' / s for s in
               ['20260907_094826_340451','20260907_095642_786832','20260907_100101_684903']]
    folders += sorted((base / 'inductor_morning_candidate_validation_20260907').glob('*/hybrid_report.json'))
    folders = [p.parent if p.suffix == '.json' else p for p in folders]
    hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in
              (model / 'dataset/inductor/train/good').glob('*.png')}
    rows = []
    for folder in folders:
        for slot in ['inductor_01','inductor_02']:
            source = folder / f'patchcore_crops/inductor/{slot}.png'
            sha = hashlib.sha256(source.read_bytes()).hexdigest()
            if sha in hashes:
                raise RuntimeError(f'Training leakage: {source}')
            name = folder.name + '_' + slot
            shutil.copy2(source, crops / (name + '.png'))
            rows.append(dict(name=name, source=str(source), sha256=sha))
    for label, path in [('previous', base / 'patchcore/inductor_confirmed_i1_candidate_20260906/models'),
                        ('candidate', model / 'models')]:
        pred = _predict_outputs('inductor', crops, _checkpoint(path, 'inductor'), out / label)
        for row in rows:
            row[label] = float(pred[row['name']]['score'])
    payload = dict(rows=rows, train_overlap=False, limitation='Same physical parts and nearby captures; not independent production validation. Earliest I2 remains direction-defective, not normal training.')
    (out / 'comparison.json').write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == '__main__':
    main()
