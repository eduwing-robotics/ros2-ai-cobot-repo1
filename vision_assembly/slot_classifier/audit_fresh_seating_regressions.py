"""Compare frozen fresh candidates on explicit controls; never fit or activate."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'runtime/inspection'


def main():
    names = ['vrm_seating_fresh_vrm5_20260907', 'vrm_seating_only_fresh_vrm5_20260907']
    evaluations = {n: json.loads((BASE/n/'evaluation.json').read_text())['rows'] for n in names}
    manifest = json.loads((ROOT/'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())
    controls = []
    for scene in manifest['scenes']:
        if not any(scene['image'].endswith(f'20260905_{s}.png') for s in
                   ('181938', '183451', '184100', '185803')):
            continue
        assert hashlib.sha256((ROOT/scene['image']).read_bytes()).hexdigest() == scene['image_sha256']
        for slot, pose in scene['expected_pose'].items():
            controls.append(dict(source=scene['image'], slot=slot,
                expected='flat' if pose == 'PASS' else 'seating', group='explicit_seating_controls'))
    fresh = json.loads((BASE/names[0]/'fresh_manifest.json').read_text())
    for row in fresh:
        if row['split'] == 'fresh_validation':
            assert hashlib.sha256((ROOT/row['scene_id']).read_bytes()).hexdigest() == row['source_sha256']
            controls.append(dict(source=row['scene_id'], slot=row['slot_id'],
                expected=row['label'], group='fresh_validation', physical_scene_id=row['physical_scene_id']))
    historical = [r for r in evaluations[names[0]] if '194959' in r['source'] and r['slot']=='vrm_05']
    assert len(historical) == 1 and historical[0]['expected'] == 'seating'
    controls.append(dict(source=historical[0]['source'], slot='vrm_05', expected='seating', group='historical_miss'))
    result = []
    for control in controls:
        scores = {}
        for name in names:
            rows = [r for r in evaluations[name] if r['source']==control['source'] and r['slot']==control['slot']]
            assert len(rows)==1 and rows[0]['split']!='train'
            scores[name] = rows[0]['seating_score']
        votes = [s >= .5 for s in scores.values()]
        result.append(dict(**control, scores=scores, disagreement=len(set(votes))>1,
            both_miss=control['expected']=='seating' and not any(votes),
            both_false_warning=control['expected']=='flat' and all(votes)))
    summary = {n: dict(misses=sum(r['expected']=='seating' and r['scores'][n]<.5 for r in result),
                       false_warnings=sum(r['expected']=='flat' and r['scores'][n]>=.5 for r in result)) for n in names}
    report = dict(rows=result, summary=summary, diagnostic_cutoff=.5,
        common_misses=sum(r['both_miss'] for r in result),
        disagreements=sum(r['disagreement'] for r in result),
        source_report_sha256={n:hashlib.sha256((BASE/n/'evaluation.json').read_bytes()).hexdigest() for n in names},
        authority='ADVISORY_ONLY', runtime_changed=False, training_performed=False,
        limitation='Retrospective explicit controls, not independent accuracy. Flat seating and gripper clearance are different labels. Consensus cannot certify seating.',
        robot_command_sent=False, conveyor_command_sent=False)
    (BASE/'fresh_seating_regression_comparison.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(controls=len(result),summary=summary, common_misses=report['common_misses'], disagreements=report['disagreements']),indent=2))
    for row in result:
        if row['both_miss'] or row['both_false_warning']:
            print(row['source'], row['slot'], row['expected'], row['scores'])


if __name__ == '__main__':
    main()
