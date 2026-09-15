import sys,math,json,argparse,time
from pathlib import Path
import rclpy
sys.path.insert(0,'/home/juchan-yoon/FR5_robot_control/vision_assembly/scripts')
from execute_full_fixed_cycle import Executor,validate_start_state,preflight_route,move_preflighted,MotionWaypoint
p=argparse.ArgumentParser();p.add_argument('point',choices=['PlaceCamera','TrayHome']);p.add_argument('--execute',action='store_true');a=p.parse_args()
rclpy.init();n=Executor()
try:
 if not n.client.wait_for_service(timeout_sec=15):raise RuntimeError('service unavailable')
 state=validate_start_state(n);start=n.snapshot();n.assert_gripper_ready()
 vals=n.response_values(n.service('GetRobotTeachingPoint('+a.point+')'),14,'teaching point')
 if tuple(vals[12:14])!=(1.,0.):raise RuntimeError('teaching point tool/user mismatch')
 target=vals[:6].tolist();height=max(350.,start[2],target[2]);origin=(*start[:2],height,*start[3:]);end=(*target[:2],height,*target[3:]);mapped=list(end)
 for k in (3,4,5):mapped[k]=origin[k]+(end[k]-origin[k]+180)%360-180
 if a.point=='PlaceCamera' and mapped[5]<origin[5]:mapped[5]+=360
 segments=max(3,math.ceil(abs(mapped[5]-origin[5])/60))
 route=[(a.point,MotionWaypoint('post_grasp_lift_50mm_vertical',origin,True))]
 for step in range(1,segments):route.append((a.point,MotionWaypoint('place_combined_xy_abc_midpoint',tuple(((origin[k]+(mapped[k]-origin[k])*step/segments+180)%360-180) if k>=3 else origin[k]+(mapped[k]-origin[k])*step/segments for k in range(6)),False)))
 route.extend([(a.point,MotionWaypoint('place_combined_xy_abc',end,False)),(a.point,MotionWaypoint('place_final_50mm_vertical',tuple(target),True))])
 planned,summary=preflight_route(n,route,n.state_joints(state),dict(travel=25,combined_rotation=25,vertical=10));print(json.dumps(dict(point=a.point,target=target,summary=summary)),flush=True)
 if a.execute:
  n.service('SetSpeed(20)')
  for w in planned:move_preflighted(n,w)
  print('ARRIVED '+a.point+' '+json.dumps(n.snapshot()),flush=True)
 else:print('DRY RUN ONLY',flush=True)
finally:n.destroy_node();rclpy.shutdown()
