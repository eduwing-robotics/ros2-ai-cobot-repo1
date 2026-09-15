"""Freeze the three remaining non-SMD parts against their historical cells."""
import json
import time
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
from fixed_cycle_snapshot import atomic_write, validate_tray_detection_quality
from full_cycle_plan import build_plan
from safe_part_pick import robot_snapshot


def main():
    root = Path(__file__).resolve().parents[1]
    data = root / 'data'
    load = lambda name: json.loads((data / name).read_text())
    state = robot_snapshot()
    if (state['robot_mode'] != 0 or state['motion_done'] != 1
            or np.linalg.norm(np.array(state['tcp'][:3]) - [-527.997, -60.954, 337.88]) > 1):
        raise RuntimeError('stationary AUTO TrayHome required')
    live = load('tray_detections_last.json')
    stamp = live['timestamp_ros_ns'] / 1e9
    if (not 0 <= time.time() - stamp < 2 or live['tray_registration'] != 'TRACKING'
            or live['base_transform_status'] not in ('OK', 'VALID_COORDINATES_ONLY')):
        raise RuntimeError('fresh registered tray required')
    vrm = load('restart_VRM_snapshot_20260905.json')['tray_capture']
    ind = load('full_restart_raise03_snapshot_2026-09-04.json')['tray_capture']
    if live['handeye_sha256'] != vrm['handeye_sha256'] or live['handeye_sha256'] != ind['handeye_sha256']:
        raise RuntimeError('calibration mismatch')
    recipes = json.loads((root / 'config/part_gripper_recipes.json').read_text())
    parts = []
    bindings = []
    for kind, indices, reference in [('black_block', [5], vrm), ('marked_white', [1, 2], ind)]:
        refs = [p for p in reference['parts'] if p['part_type'] == kind and p['instance_index'] in indices]
        ds = [p for p in live['stable_detections'] if p['part_type'] == kind]
        if len(ds) != len(indices) or len(refs) != len(indices):
            raise RuntimeError(f'{kind} inventory mismatch')
        distances = np.array([[np.linalg.norm(np.array(d['base_xyz_mm'][:2]) - r['base_xyz_mm'][:2]) for r in refs] for d in ds])
        ii, jj = linear_sum_assignment(distances)
        for i, j in zip(ii, jj):
            others = np.delete(distances[i], j)
            if distances[i, j] > 5 or (len(others) and min(others) - distances[i, j] < 2):
                raise RuntimeError('physical cell identity failed')
            d, r = ds[i], refs[j]
            q = validate_tray_detection_quality(d, recipes['tray_snapshot_quality'])
            parts.append(dict(part_type=kind, instance_index=r['instance_index'],
                              base_xyz_mm=d['base_xyz_mm'], reference_center_pixel=d['reference_center_pixel'],
                              long_axis_angle_base_deg=d['long_axis_angle_base_deg'], quality=q, consumed=False))
            bindings.append(dict(part_type=kind, physical_index=r['instance_index'], distance_mm=float(distances[i, j])))
    board = load('last_non_smd_board_20260906.json')
    if not board['board_captured'] or not 0 <= time.time() - board['board_capture']['captured_unix'] < 600:
        raise RuntimeError('fresh board required')
    selected = ['VRM-05', 'IND-01', 'IND-02']
    board.update(authorized_selected_slots=selected, tray_captured=True)
    board['tray_capture'] = dict(captured_unix=stamp, handeye_sha256=live['handeye_sha256'], parts=parts)
    snapshot = data / 'last_non_smd_snapshot_20260906.json'
    output = data / 'last_non_smd_plan_20260906.json'
    if snapshot.exists() or output.exists():
        raise RuntimeError('refusing to overwrite prepared plan')
    plan = build_plan(board, recipes, json.loads((root / 'config/assembly_slots_r1.json').read_text()),
                      snapshot_path=snapshot, selected_slots=selected)
    atomic_write(snapshot, board)
    atomic_write(output, plan)
    print(json.dumps(dict(bindings=bindings, selected=selected,
                         rotations=[p['placement_orientation']['rotation_delta_deg'] for p in plan['plan']])), flush=True)


if __name__ == '__main__':
    main()
