"""Compare frozen candidates on explicit seating controls, not generic pose labels."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    manifest = ROOT / 'vision_assembly/config/vrm_presence_context_holdout_20260905.json'
    data = json.loads(manifest.read_text())
    stamps = ('181938', '183451', '184100', '185803')
    controls = []
    for scene in data['scenes']:
        if not any(scene['image'].endswith(f'20260905_{s}.png') for s in stamps):
            continue
        assert hashlib.sha256((ROOT / scene['image']).read_bytes()).hexdigest() == scene['image_sha256']
        for slot, pose in scene['expected_pose'].items():
            controls.append(dict(image=scene['image'], slot=slot, frozen_report=scene['report'],
                seating='flat' if pose == 'PASS' else 'seating',
                evidence=[scene.get('label_source'), scene.get('additional_label_source')],
                process_position=scene.get('process_position_review')
                    if scene.get('process_position_review', {}).get('slot') == slot else None))
    results = []
    for name in ('vrm_multiscale_seating_plus_165057', 'vrm_seating_only_multiscale_20260907'):
        report = json.loads((ROOT / 'runtime/inspection' / name / 'evaluation.json').read_text())
        rows = []
        for control in controls:
            matches = [r for r in report['rows'] if r['source'] == control['image'] and r['slot'] == control['slot']]
            if name == 'vrm_multiscale_seating_plus_165057':
                frozen = json.loads((ROOT / control['frozen_report']).read_text())
                assert frozen['image_sha256'] == hashlib.sha256((ROOT / control['image']).read_bytes()).hexdigest()
                matches = [r for c in frozen['candidates'] if Path(c['candidate']).name == name
                           for r in c['rows'] if r['slot'] == control['slot']]
            if len(matches) != 1:
                raise ValueError(f'Missing/ambiguous control: {control}')
            score = matches[0]['seating_score']
            rows.append(dict(**control, score=score,
                correct=(score >= .5) == (control['seating'] == 'seating')))
        results.append(dict(model=name, count=len(rows), correct=sum(r['correct'] for r in rows), rows=rows))
    output = ROOT / 'runtime/inspection/seating_explicit_controls_20260907.json'
    output.write_text(json.dumps(dict(authority='ADVISORY_ONLY', training_allowed=False,
        runtime_enabled=False, results=results,
        limitation='Development controls selected after observing errors; not independent accuracy. Flat seating does not imply safe lateral clearance.'), indent=2))
    print(json.dumps([{k: r[k] for k in ('model', 'count', 'correct')} for r in results]))


if __name__ == '__main__':
    main()
