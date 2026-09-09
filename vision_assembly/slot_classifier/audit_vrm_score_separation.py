"""Saved-score separability audit, not threshold selection or model training."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / 'runtime/inspection/vrm_multiscale_seating_plus_165057'


def main():
    model_hash = hashlib.sha256((CANDIDATE / 'candidate.npz').read_bytes()).hexdigest()
    evaluation = json.loads((CANDIDATE / 'evaluation.json').read_text())
    manifest = json.loads((ROOT / 'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())
    # Never mix training examples into an assessment of saved holdout scores.
    rows = {(r['source'], r['slot']): dict(r) for r in evaluation['rows']
            if r['split'] in ('holdout', 'session_holdout')}
    for scene in manifest['scenes']:
        report_path = ROOT / scene.get('report', '')
        if not report_path.is_file():
            continue
        report = json.loads(report_path.read_text())
        candidates = [c for c in report.get('candidates', []) if c.get('sha256') == model_hash]
        if not candidates:
            continue
        actual_hash = hashlib.sha256((ROOT / scene['image']).read_bytes()).hexdigest()
        if actual_hash != scene['image_sha256'] or report['image_sha256'] != actual_hash:
            raise ValueError(f'Source hash mismatch: {scene["image"]}')
        for r in candidates[0]['rows']:
            label = scene.get('expected_pose', {}).get(r['slot'])
            if label not in ('PASS', 'FAIL'):
                continue
            rows[(scene['image'], r['slot'])] = dict(
                source=scene['image'], slot=r['slot'], expected='flat' if label == 'PASS' else 'seating',
                seating_score=r['seating_score'], split='session_holdout',
                process_position_review=scene.get('process_position_review') if
                scene.get('process_position_review', {}).get('slot') == r['slot'] else None)
    summaries = {}
    for slot in [f'vrm_{i:02}' for i in range(1, 6)]:
        subset = [r for r in rows.values() if r['slot'] == slot]
        normal = [r for r in subset if r['expected'] == 'flat']
        defect = [r for r in subset if r['expected'] == 'seating']
        high = max(normal, key=lambda r: r['seating_score'], default=None)
        low = min(defect, key=lambda r: r['seating_score'], default=None)
        summaries[slot] = dict(normal_count=len(normal), defect_count=len(defect),
            highest_normal=high, lowest_defect=low,
            scalar_threshold_can_separate_saved_labels=(high['seating_score'] < low['seating_score'])
            if high and low else None,
            false_warnings_at_existing_0_5=sum(r['seating_score'] >= .5 for r in normal),
            misses_at_existing_0_5=sum(r['seating_score'] < .5 for r in defect))
    all_normal = [r['seating_score'] for r in rows.values() if r['expected'] == 'flat']
    all_defect = [r['seating_score'] for r in rows.values() if r['expected'] == 'seating']
    result = dict(authority='ADVISORY_ONLY', runtime_enabled=False, model_sha256=model_hash,
        global_scalar_separable=max(all_normal) < min(all_defect),
        threshold_selected=False, training_performed=False, robot_command_sent=False,
        conveyor_command_sent=False, summaries=summaries,
        limitation='Repeated development holdouts, not independent certification. Physical seating labels remain distinct from process-clearance concerns. Separability does not establish generalization.',
        rows=list(rows.values()))
    output = ROOT / 'runtime/inspection/vrm_score_separation_20260905.json'
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()
