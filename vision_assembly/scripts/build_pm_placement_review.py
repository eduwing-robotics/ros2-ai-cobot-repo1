#!/usr/bin/env python3
"""Build one PM03/04 hover-only trial from a fresh snapshot and observed target.

No robot access. The image-plane target and carried offset are provisional;
this plan is forbidden from final descent/release by the executor.
"""
import argparse
import copy
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from full_cycle_plan import build_plan

ROOT = Path(__file__).resolve().parents[2]


def build_review(snapshot, recipes, slots, reference, slot_code, snapshot_path=None):
    if slot_code not in ('PM-03', 'PM-04'):
        raise ValueError('PM03/04 only')
    snapshot = copy.deepcopy(snapshot)
    all_parts = copy.deepcopy(snapshot['tray_capture']['parts'])
    snapshot['authorized_selected_slots'] = [slot_code]
    snapshot['tray_capture']['parts'] = [x for x in all_parts
        if x['part_type'] == 'long_orange' and x['instance_index'] == int(slot_code[-2:])]
    recipes = copy.deepcopy(recipes)
    recipes['parts']['long_orange'].pop('validated_placement_centers', None)
    recipes['parts']['long_orange']['placement_orientation_policy']['skip_rotation_below_deg'] = 0.0
    plan = build_plan(snapshot, recipes, slots, selected_slots=[slot_code], snapshot_path=snapshot_path)
    if all(x.get('reference_center_pixel') is not None for x in all_parts):
        plan['tray_inspection_reference'] = dict(
            handeye_sha256=snapshot['tray_capture'].get('handeye_sha256'), parts=all_parts,
            bindings=[dict(part_type=x['part_type'], physical_index=x['instance_index'],
                           reference_center_pixel=x['reference_center_pixel']) for x in all_parts])
    item = plan['plan'][0]
    observed = next(x for x in reference['measurements'] if x['slot_code'] == slot_code)
    delta = np.asarray(observed['visible_center_minus_nominal_board_mm'], dtype=float)
    if delta.shape != (2,) or not np.isfinite(delta).all() or np.linalg.norm(delta) > 5:
        raise ValueError('reference center correction invalid or exceeds 5mm')
    rotation = np.asarray(snapshot['board_capture']['T_base_board'], dtype=float)[:3,:3]
    placement = snapshot['resolved_placements'][slot_code]
    old = np.array(item['place_final_tcp'][:2])
    # Remove the old static slot TCP correction before applying the visible
    # center shift and a provisional offset carried from this fresh pick.
    static = np.asarray(placement['place_tcp_compensation_base_mm'])[:2]
    base_extra = np.asarray(placement.get('place_tcp_correction_base_mm', [0,0]))[:2]
    nominal = old - static - base_extra
    pick_rotation = Rotation.from_euler('xyz', item['pick_final_tcp'][3:], degrees=True).as_matrix()
    place_rotation = Rotation.from_euler('xyz', item['place_final_tcp'][3:], degrees=True).as_matrix()
    carried = place_rotation @ pick_rotation.T @ np.r_[item['pick_correction_base_mm'], 0.0]
    target = nominal + (rotation @ np.r_[delta, 0.0])[:2] + carried[:2]
    item['place_final_tcp'][:2] = target.tolist()
    plan['execution_scope'] = 'placement_review_hover_only'
    plan['placement_review'] = dict(slot=slot_code, previous_tcp_xy_mm=old.tolist(),
        candidate_tcp_xy_mm=target.tolist(), visible_center_shift_board_mm=delta.tolist(),
        provisional_carried_offset_base_mm=carried.tolist(),
        limitations=['reference image part-height parallax uncorrected',
                    'pick detector bias versus actual held offset not yet separated'],
        final_descent_authorized=False)
    return plan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--slot', choices=['PM-03','PM-04'], required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    read = lambda path: json.loads(path.read_text())
    result = build_review(read(a.snapshot), read(ROOT/'vision_assembly/config/part_gripper_recipes.json'),
        read(ROOT/'vision_assembly/config/assembly_slots_r1.json'), read(a.reference), a.slot, a.snapshot)
    if a.output.exists():
        raise RuntimeError('refusing to overwrite review plan')
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result['placement_review'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
