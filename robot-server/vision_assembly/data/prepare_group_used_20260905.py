import sys,json,time,copy
from pathlib import Path
import numpy as np
sys.path.insert(0,'/home/juchan-yoon/FR5_robot_control/vision_assembly/scripts')
from fixed_cycle_snapshot import validate_tray_detection_quality,finite_vector,atomic_write
from full_cycle_plan import build_plan
from safe_part_pick import robot_snapshot
kind=sys.argv[1];prefix,count={'hbm':('HBM',8),'long_orange':('PM',4),'black_block':('VRM',5),'marked_white':('IND',2)}[kind]
state=robot_snapshot()
if np.linalg.norm(np.array(state['tcp'][:3])-[-527.997,-60.954,337.88])>1:raise RuntimeError('not at TrayHome')
root=Path('vision_assembly');board=json.loads((root/'data/post_contact_cycle_20260905.json').read_text());live=json.loads((root/'data/tray_detections_last.json').read_text());recipes=json.loads((root/'config/part_gripper_recipes.json').read_text())
if not board.get('board_captured') or board.get('invalidated_unix'):raise RuntimeError('board snapshot invalidated')
now=time.time();stamp=live['timestamp_ros_ns']/1e9
if not 0<=now-stamp<2 or live['tray_registration']!='TRACKING' or live['base_transform_status'] not in ('OK','VALID_COORDINATES_ONLY'):raise RuntimeError('tray view not fresh/registered')
old=json.loads((root/'data/gpu_restart_single_20260905.json').read_text())
if live['handeye_sha256']!=old['tray_capture']['handeye_sha256']:raise RuntimeError('calibration changed')
parts=sorted([d for d in live['stable_detections'] if d['part_type']==kind],key=lambda d:d['instance_index'])
if [p['instance_index'] for p in parts]!=list(range(1,count+1)):raise RuntimeError('group inventory/identity mismatch')
frozen=[]
for d in parts:
 q=validate_tray_detection_quality(d,recipes['tray_snapshot_quality'])
 frozen.append(dict(part_type=kind,instance_index=d['instance_index'],base_xyz_mm=finite_vector(d['base_xyz_mm'],3,'center').tolist(),long_axis_angle_base_deg=d['long_axis_angle_base_deg'],reference_center_pixel=finite_vector(d['reference_center_pixel'],2,'pixel').tolist(),quality=q,consumed=False))
selected=[f'{prefix}-{i:02d}' for i in range(1,count+1)]
board.update(tray_captured=True,authorized_selected_slots=selected)
board['tray_capture']=dict(captured_unix=stamp,handeye_sha256=live['handeye_sha256'],parts=frozen,counts={kind:count})
path=root/f'data/restart_{prefix}_snapshot_20260905.json';atomic_write(path,board)
plan=build_plan(board,recipes,json.loads((root/'config/assembly_slots_r1.json').read_text()),snapshot_path=path,selected_slots=selected)
atomic_write(root/f'data/restart_{prefix}_plan_20260905.json',plan)
print('READY',selected)
