import json,time,sys,copy
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
sys.path.insert(0,'vision_assembly/scripts')
from fixed_cycle_snapshot import validate_tray_detection_quality,atomic_write
from full_cycle_plan import build_plan
from safe_part_pick import robot_snapshot
root=Path('vision_assembly');data=root/'data'
state=robot_snapshot()
if state['robot_mode']!=0 or state['motion_done']!=1 or np.linalg.norm(np.array(state['tcp'][:3])-[-527.997,-60.954,337.88])>1:raise RuntimeError('not stationary at TrayHome')
live=json.loads((data/'tray_detections_last.json').read_text());stamp=live['timestamp_ros_ns']/1e9
if not 0<=time.time()-stamp<2 or live['tray_registration']!='TRACKING' or live['base_transform_status'] not in ('OK','VALID_COORDINATES_ONLY'):raise RuntimeError('tray not fresh/registered')
old=json.loads((data/'restart_VRM_snapshot_20260905.json').read_text())
if live['handeye_sha256']!=old['tray_capture']['handeye_sha256']:raise RuntimeError('handeye changed')
refs=[p for p in old['tray_capture']['parts'] if p['part_type']=='black_block' and p['instance_index']>=3]
ds=[d for d in live['stable_detections'] if d['part_type']=='black_block']
if len(ds)!=3 or len(refs)!=3:raise RuntimeError('expected three remaining VRMs')
dist=np.array([[np.linalg.norm(np.array(d['base_xyz_mm'][:2])-r['base_xyz_mm'][:2]) for r in refs] for d in ds]);ii,jj=linear_sum_assignment(dist)
recipes=json.loads((root/'config/part_gripper_recipes.json').read_text());parts=[];bindings=[]
for i,j in zip(ii,jj):
 d,r=ds[i],refs[j]
 if dist[i,j]>5 or min(np.delete(dist[i],j))-dist[i,j]<2:raise RuntimeError('ambiguous or displaced identity')
 if np.linalg.norm(np.array(d['reference_center_pixel'])-r['reference_center_pixel'])>12:raise RuntimeError('pixel cell mismatch')
 q=validate_tray_detection_quality(d,recipes['tray_snapshot_quality'])
 parts.append(dict(part_type='black_block',instance_index=r['instance_index'],base_xyz_mm=d['base_xyz_mm'],reference_center_pixel=d['reference_center_pixel'],long_axis_angle_base_deg=d['long_axis_angle_base_deg'],quality=q,consumed=False))
 bindings.append(dict(part_type='black_block',physical_index=r['instance_index'],reference_center_pixel=d['reference_center_pixel'],distance_xy_mm=float(dist[i,j])))
board=json.loads((data/'vrm03_snapshot_20260906.json').read_text())
if not board['board_captured'] or not 0<=time.time()-board['board_capture']['captured_unix']<1800:raise RuntimeError('fresh board required')
board.update(tray_captured=True,authorized_selected_slots=['VRM-03'])
board['tray_capture']=dict(captured_unix=stamp,handeye_sha256=live['handeye_sha256'],parts=[p for p in parts if p['instance_index']==3],counts={'black_block':1})
plan=build_plan(board,recipes,json.loads((root/'config/assembly_slots_r1.json').read_text()),snapshot_path=data/'vrm03_ready_snapshot_20260906.json',selected_slots=['VRM-03'])
# Cell removal must account for all three parts still in this section.
plan['tray_inspection_reference']=dict(handeye_sha256=live['handeye_sha256'],parts=parts,bindings=bindings)
atomic_write(data/'vrm03_ready_snapshot_20260906.json',board)
atomic_write(data/'vrm03_plan_20260906.json',plan)
print(json.dumps(dict(bindings=bindings,plan=plan['plan']),indent=2))
