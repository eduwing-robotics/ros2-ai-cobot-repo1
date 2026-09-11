import json,time,hashlib,math,sys
from pathlib import Path
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo
from fairino_msgs.msg import RobotNonrtState
from scipy.spatial.transform import Rotation
sys.path.insert(0,'/home/juchan-yoon/FR5_robot_control/vision_assembly/scripts')
from execute_full_fixed_cycle import Executor,pose_error
from smd_manual_axis import canonical_axis_angle_deg
root=Path('/home/juchan-yoon/FR5_robot_control');manual_path=root/'vision_assembly/data/smd05_manual_axes_final_20260906.json';manual=json.loads(manual_path.read_text())
assert manual['mode']=='operator_two_terminal_axes' and manual['operator_confirmed_consumed_prefix_count']==4
assert 0<=time.time()-manual['timestamp_unix']<120,'manual source is stale'
he_path=root/'calibration/data/handeye_result.json';he=json.loads(he_path.read_text());best=he.get('best',he);fc=he.get('camera_to_flange') or best['camera_to_flange']
Tfc=np.eye(4);Tfc[:3,:3]=fc['rotation_matrix'];Tfc[:3,3]=fc['translation_m']
rclpy.init();n=Node('resolve_operator_smd_targets');info=[];states=[]
n.create_subscription(CameraInfo,'/camera/camera/color/camera_info',lambda x:info.append(x),qos_profile_sensor_data)
n.create_subscription(RobotNonrtState,'/nonrt_state_data',lambda x:states.append(x),10)
try:
 deadline=time.monotonic()+8
 while time.monotonic()<deadline:
  rclpy.spin_once(n,timeout_sec=.1)
  if info and len(states)>1 and states[-1].timestamp>states[0].timestamp:break
 else:raise RuntimeError('fresh camera/state unavailable')
 s=states[-1];c=info[-1]
 assert (c.width,c.height)==(1280,720)
 assert not Executor.safety_error(s) and s.robot_motion_done==1 and s.gripper_position==17
 tcp=[float(getattr(s,'cart_'+k+'_cur_pos')) for k in 'xyzabc'];pe,ae=pose_error(tcp,manual['reference_tcp_base']);assert pe<1 and ae<.2
 flange=[float(getattr(s,'flange_'+k+'_cur_pos')) for k in 'xyzabc'];Tbf=np.eye(4);Tbf[:3,:3]=Rotation.from_euler(best.get('euler_convention','xyz'),flange[3:],degrees=True).as_matrix();Tbf[:3,3]=np.array(flange[:3])/1000;Tbc=Tbf@Tfc
 fx,fy,cx,cy=c.k[0],c.k[4],c.k[2],c.k[5]
 for part in manual['parts']:
  i=part['instance_index'];assert i in (4,5)
  uv=np.asarray(part['terminal_endpoints_source_pixel'],float);assert uv.shape==(2,2) and np.isfinite(uv).all()
  xyz=[]
  for u,v in uv:
   ray=Tbc[:3,:3]@np.array([(u-cx)/fx,(v-cy)/fy,1.]);distance=(-.047291-Tbc[2,3])/ray[2];assert distance>0
   xyz.append((Tbc[:3,3]+distance*ray)*1000)
  xyz=np.array(xyz);center=xyz.mean(axis=0);axis=xyz[1]-xyz[0];length=float(np.linalg.norm(axis[:2]));assert 2<length<15
  angle=canonical_axis_angle_deg(math.degrees(math.atan2(axis[1],axis[0])))
  reference={4:[-627.696,-127.241],5:[-627.422,-114.436]}[i];assert np.linalg.norm(center[:2]-reference)<2
  out=dict(mode='operator_confirmed_terminal_target',instance_index=i,operator_confirmed_consumed_prefix_count=4,operator_terminal_points_confirmed=True,automatic_detection_validation_passed=False,robot_motion_authorized=False,timestamp_unix=time.time(),manual_source_timestamp=manual['timestamp_unix'],manual_source_sha256=hashlib.sha256(manual_path.read_bytes()).hexdigest(),handeye_sha256=hashlib.sha256(he_path.read_bytes()).hexdigest(),part_center_base_mm=center.tolist(),long_axis_angle_base_deg=angle,terminal_centers_base_mm=xyz.tolist(),terminal_distance_mm=length,reference_tcp=tcp,reference_flange=flange,camera_k=list(c.k))
  outpath=root/f'vision_assembly/data/smd{i:02d}_operator_target_final_20260906.json';outpath.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out),flush=True)
finally:n.destroy_node();rclpy.shutdown()
