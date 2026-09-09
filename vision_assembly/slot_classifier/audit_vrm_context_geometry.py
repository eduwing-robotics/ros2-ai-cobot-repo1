"""Join frozen-model controls to hash-verified archived geometry; no runtime writes."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'vision_assembly/hybrid_inspection'))
from vrm_context_pose import context_pose_codes
from vrm_rotation_geometry import corroborated_rotation


def main():
    folder = ROOT / 'runtime/inspection/vrm_deadline_candidate_20260909/frozen_context_state'
    controls = json.loads((folder / 'historical_evaluation.json').read_text())['rows']
    wanted = {r['source_sha256'] for r in controls}
    indexed = {}
    for path in sorted((ROOT / 'runtime/inspection').rglob('hybrid_report.json')):
        report = json.loads(path.read_text())
        digest = report.get('input_sha256')
        if digest not in wanted:
            continue
        source = Path(report['input_image'])
        if not source.is_absolute():
            source = ROOT / source
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Source changed: {path}')
        indexed.setdefault(digest, []).append((path, report))
    rows = []
    for control in controls:
        observations = []
        for path, report in indexed.get(control['source_sha256'], []):
            slots = [s for s in report['slots'] if s['slot_id'] == control['slot']]
            if len(slots) != 1:
                raise ValueError('Missing or duplicate slot')
            slot = slots[0]
            codes = context_pose_codes(slot)
            rotation = corroborated_rotation(slot)
            observations.append(dict(report=str(path.relative_to(ROOT)),
                                     report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                     context_codes=codes, rotation_candidate=rotation,
                                     geometry_warning=bool(codes or rotation),
                                     boundary_reason=slot.get('stages', {}).get('vrm_boundary', {}).get('reason')))
        rows.append(dict(**control, archived_geometry=observations))
    summary = {}
    for truth in ('correct', 'empty', 'rotated'):
        subset = [r for r in rows if r['truth'] == truth]
        available = [r for r in subset if r['archived_geometry']]
        summary[truth] = dict(total=len(subset), matched=len(available),
            any_archive_warning=sum(any(o['geometry_warning'] for o in r['archived_geometry']) for r in available),
            all_archives_warning=sum(all(o['geometry_warning'] for o in r['archived_geometry']) for r in available))
    result = dict(summary=summary, rows=rows, runtime_changed=False,
                  limitation='Archived providers may differ from current runtime. Missing geometry is not PASS. No best-report selection or release authority.')
    with (folder / 'geometry_join.json').open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
