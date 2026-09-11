"""Read-only controller IK probe; no motion/gripper commands or plan execution."""
import argparse,json,sys
from pathlib import Path
import numpy as np
import rclpy
from execute_full_fixed_cycle import Executor,validate_start_state,build_tcp_route,preflight_route
from full_cycle_plan import _plan_placement_orientation,_pick_correction,wrap_degrees,atomic_write_json

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--flip',nargs='*',default=[])
    p.add_argument('--output',type=Path)
    p.add_argument('--plan',type=Path)
    p.add_argument('--board',type=Path)
    a=p.parse_args();root=Path(__file__).resolve().parents[1]
    if a.output and a.output.exists():raise RuntimeError('refusing to overwrite route plan')
    plan=json.loads((a.plan or root/'data/remaining15_plan_2026-09-05.json').read_text())
    board=json.loads((a.board or root/'data/remaining15_board_2026-09-05.json').read_text())
    recipes=json.loads((root/'config/part_gripper_recipes.json').read_text())['parts']
    slots={s['slot_code']:s for s in json.loads((root/'config/assembly_slots_r1.json').read_text())['slots']}
    if any(s not in {i['slot_code'] for i in plan['plan']} for s in a.flip):raise RuntimeError('unknown slot')
    for item in plan['plan']:
        if item['slot_code']=='HBM-04':item['transfer_z_mm']=400.0
        if item['slot_code'] in a.flip:
            kind=item['part_type']
            if recipes[kind]['placement_orientation_policy']['symmetry_period_deg']!=180:raise RuntimeError('part lacks 180-degree symmetry')
            item['pick_final_tcp'][5]=wrap_degrees(item['pick_final_tcp'][5]+180)
            correction=_pick_correction(recipes[kind],kind,item['pick_final_tcp'][3:])
            item['pick_final_tcp'][:2]=(np.array(item['tray_surface_base_mm'][:2])+correction).tolist()
            item['pick_correction_base_mm']=correction.tolist()
            abc,policy=_plan_placement_orientation(slot_code=item['slot_code'],part_type=kind,
                policy=recipes[kind]['placement_orientation_policy'],slot=slots[item['slot_code']],
                board_rotation=np.array(board['board_capture']['T_base_board'])[:3,:3],pick_abc=item['pick_final_tcp'][3:])
            item['place_final_tcp'][3:]=abc;item['placement_orientation']=policy
    rclpy.init();node=Executor()
    try:
        if not node.client.wait_for_service(timeout_sec=8):raise RuntimeError('service unavailable')
        state=validate_start_state(node);start=node.snapshot();route=[]
        for item in plan['plan']:
            one=build_tcp_route([item],start,400 if item['slot_code']=='HBM-04' else 350,resume_after_grasp=False)
            route+=one;start=list(one[-1][1].tcp)
        try:
            _,summary=preflight_route(node,route,node.state_joints(state),plan['speeds_percent'])
        except Exception as exc:
            import re
            match=re.search(r'waypoint (\d+)',str(exc))
            if match:
                index=int(match.group(1))-1
                print('FAILED WAYPOINT',route[index],flush=True)
            raise
        print('READ-ONLY ROUTE PASSED',summary)
        if a.output:
            plan['route_preflight']=summary
            plan['route_revision']={'symmetric_pick_flips':a.flip,'height_overrides_mm':{'HBM-04':400},'status':'joint_preflight_only_not_physical_collision_validation'}
            atomic_write_json(a.output,plan)
    finally:node.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
