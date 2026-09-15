"""Fresh HBM02 pick-only retry; obsolete board poses cannot be executed."""
import json,time
from pathlib import Path
import numpy as np
from full_cycle_plan import _pick_correction,_pick_z,_plan_placement_orientation,choose_symmetric_pick_c,atomic_write_json

root=Path(__file__).resolve().parents[1]
target=json.loads((root/'data/hbm02_retry_fresh_2026-09-05.json').read_text())
if not 0<=time.time()-target['timestamp_unix']<120:raise RuntimeError('fresh target expired')
plan=json.loads((root/'data/remaining15_route_checked_2026-09-05.json').read_text())
item=next(i for i in plan['plan'] if i['slot_code']=='HBM-02')
recipe=json.loads((root/'config/part_gripper_recipes.json').read_text())['parts']['hbm']
slots=json.loads((root/'config/assembly_slots_r1.json').read_text())['slots']
board=json.loads((root/'data/remaining15_board_2026-09-05.json').read_text())
center=target['part_center_base_mm'];angle=target['long_axis_angle_base_deg']
abc=[-180.,0.,choose_symmetric_pick_c(angle,'tool_y',90.)]
correction=_pick_correction(recipe,'hbm',abc);z,mode=_pick_z(recipe,center[2],'hbm')
item.update(tray_surface_base_mm=center,tray_long_axis_base_deg=angle,pick_correction_base_mm=correction.tolist(),
            pick_final_tcp=[center[0]+correction[0],center[1]+correction[1],z,*abc],pick_z_mode=mode)
place,policy=_plan_placement_orientation(slot_code='HBM-02',part_type='hbm',policy=recipe['placement_orientation_policy'],
    slot=next(s for s in slots if s['slot_code']=='HBM-02'),board_rotation=np.array(board['board_capture']['T_base_board'])[:3,:3],pick_abc=abc)
item['place_final_tcp'][3:]=place;item['placement_orientation']=policy
plan['plan']=[item];plan['plan_selection']['selected_slots']=['HBM-02']
plan['created_unix']=target['timestamp_unix'];plan['source_captures']['tray_captured_unix']=target['timestamp_unix']
plan['source_captures']['tray_file']=str(root/'data/hbm02_retry_fresh_2026-09-05.json')
plan['execution_scope']='close_only_no_lift_or_board';plan.pop('route_preflight',None)
output=root/'data/hbm02_close_retry_plan_2026-09-05.json'
if output.exists():raise RuntimeError('refusing overwrite')
atomic_write_json(output,plan)
print('CLOSE ONLY',item['pick_final_tcp'])
