"""Audit proposed advisory geometry on archived explicit controls, not release accuracy."""
import hashlib
import json
from pathlib import Path
import sys
import argparse
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'vision_assembly/hybrid_inspection'))
from vrm_rotation_geometry import corroborated_rotation, multi_axis_rotation, strong_boundary_rotation


def main():
    base = ROOT / 'runtime/inspection/vrm_deadline_candidate_20260909'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=base / 'three_axis_audit.json')
    args = parser.parse_args()
    labels = {}
    def add(digest, slot, label):
        key = digest, slot
        if key in labels and labels[key] != label:
            raise ValueError(f'Conflicting truth: {key}')
        labels[key] = label
    for line in (base / 'dataset/manifest.jsonl').read_text().splitlines():
        row = json.loads(line)
        add(row['source_sha256'], row['slot_id'], row['label'])
    for row in json.loads((base / 'frozen_context_state/historical_evaluation.json').read_text())['rows']:
        add(row['source_sha256'], row['slot'], row['truth'])
    # Include the full explicitly labelled historical file, not only the six
    # scenes selected for the earlier feature experiment. Do not infer pose
    # from PRESENT or convert an unspecified seating defect into rotation.
    config = json.loads((ROOT / 'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())
    for scene in config['scenes']:
        source = ROOT / scene['image']
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if scene.get('image_sha256') and scene['image_sha256'] != digest:
            raise ValueError('Historical label source mismatch')
        for sid, presence in scene.get('labels', {}).items():
            pose = (scene.get('expected_pose') or {}).get(sid)
            reason = (scene.get('defect_reason') or {}).get(sid)
            label = ('empty' if presence == 'EMPTY' else 'correct'
                     if presence == 'PRESENT' and pose == 'PASS' else 'rotated'
                     if reason == 'ROTATION_POSITION_ERROR' else None)
            if label is not None:
                add(digest, sid, label)
    for stamp in ('153954', '154203'):
        path = ROOT / f'runtime/inspection/s22_inspection_roi_20260909_{stamp}.png'
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        for i in range(1, 6):
            add(digest, f'vrm_{i:02}', 'correct')
    rows = []
    for path in sorted((ROOT / 'runtime/inspection').rglob('hybrid_report.json')):
        report = json.loads(path.read_text())
        digest = report.get('input_sha256')
        for slot in report.get('slots', []):
            if slot.get('component_type') != 'VRM':
                continue
            old = corroborated_rotation(slot)
            proposed = multi_axis_rotation(slot) or strong_boundary_rotation(slot)
            truth = labels.get((digest, slot['slot_id']))
            if truth is None and not (proposed and not old):
                continue
            source = Path(report['input_image'])
            if not source.is_absolute():
                source = ROOT / source
            if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise ValueError('Source mismatch')
            rows.append(dict(report=str(path.relative_to(ROOT)), source_sha256=digest,
                slot=slot['slot_id'], truth=truth, old=old, proposed=proposed,
                newly_flagged=proposed and not old,
                axes=(slot.get('stages', {}).get('vrm_boundary', {}).get('measured') or {}).get('axes')))
    counts = Counter((r['truth'] or 'UNLABELLED') for r in rows if r['newly_flagged'])
    payload = dict(rows=rows, newly_flagged_by_label=dict(counts),
        labelled_unique_source_slots=len({(r['source_sha256'], r['slot']) for r in rows if r['truth']}),
        limitation='Repeated archived provider versions, reused development controls, unknown truth explicitly retained. Not release accuracy.',
        runtime_changed=False)
    with args.output.open('x') as stream:
        json.dump(payload, stream, indent=2)
    print(json.dumps({k:v for k,v in payload.items() if k != 'rows'}, indent=2))
    for row in rows:
        if row['newly_flagged']: print(row)


if __name__ == '__main__':
    main()
