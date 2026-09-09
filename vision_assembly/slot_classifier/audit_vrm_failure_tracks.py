"""Join archived geometry/state evidence by scene ID, never manifest index."""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    manifest = json.loads((ROOT / 'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())
    scenes = {s['physical_scene_id']: s for s in manifest['scenes']}
    base = ROOT / 'runtime/inspection/vrm_fixed_pose_offline_20260905'
    geometry = json.loads((base / 'evaluation.json').read_text())
    state = json.loads((base / 'seating_comparison.json').read_text())
    geo = {(r['scene'], r['slot']): r for r in geometry['rows']}
    groups = defaultdict(lambda: dict(count=0, geometry_warning=0, appearance_warning=0,
                                     geometry_miss_appearance_warning=0))
    output_rows = []
    for row in state['rows']:
        if row['expected'] not in ('PASS', 'FAIL'):
            continue
        scene = scenes[row['scene']]
        slot = row['slot']
        if scene.get('expected_pose', {}).get(slot) != row['expected']:
            raise ValueError(f'Stale archived label: {row["scene"]} {slot}')
        g = geo[(row['scene'], slot)]
        if scene.get('image_sha256') and scene['image_sha256'] != g['image_sha256']:
            raise ValueError('Scene hash mismatch')
        reason = scene.get('defect_reason', {}).get(slot)
        if row['expected'] == 'PASS':
            track, source = 'NORMAL', 'expected_pose'
        elif reason:
            track, source = reason, 'explicit defect_reason'
        elif 'translation' in scene.get('label_source', '').lower():
            # Setup describes combined displacement/lip, not measured height.
            track, source = 'TRANSLATION_OR_LIP_SETUP', scene['label_source']
        else:
            track, source = 'UNSPECIFIED_DEFECT', scene.get('label_source')
        counts = groups[track]
        counts['count'] += 1
        counts['geometry_warning'] += bool(row['geometry_warning'])
        counts['appearance_warning'] += bool(row['seating_warning'])
        counts['geometry_miss_appearance_warning'] += bool(
            row['expected'] == 'FAIL' and not row['geometry_warning'] and row['seating_warning'])
        output_rows.append(dict(**row, track=track, track_source=source,
                                estimated_position_error_mm=g.get('error_mm'),
                                estimated_angle_error_deg=g.get('angle_error_deg')))
    result = dict(authority='ADVISORY_ONLY', runtime_enabled=False,
        groups=dict(groups), rows=output_rows, training_performed=False,
        robot_command_sent=False, conveyor_command_sent=False,
        limitations=[
            'Archived 22-scene development replay only; later captures and historical VRM5 miss not included.',
            'Appearance warning does not identify rotation, displacement, or physical height.',
            'Geometry uses estimated segmentation outline, not measured gripper clearance.',
            'Setup labels do not prove measured height; no new ground truth inferred from scores.'])
    (ROOT / 'runtime/inspection/vrm_failure_tracks_20260905.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result['groups'], indent=2))


if __name__ == '__main__':
    main()
