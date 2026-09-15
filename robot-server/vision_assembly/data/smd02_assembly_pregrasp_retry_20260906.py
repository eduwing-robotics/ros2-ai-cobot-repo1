import sys,json,time,hashlib,math
from pathlib import Path
sys.path.insert(0,'/home/juchan-yoon/FR5_robot_control/vision_assembly/scripts')
import rclpy
from execute_full_fixed_cycle import Executor,validate_start_state,preflight_route,move_preflighted,MotionWaypoint,pose_error
root=Path('/home/juchan-yoon/FR5_robot_control')
p=json.loads(Path('/tmp/smd02_assembly_fresh_20260906.json').read_text())
recipe_path=root/'vision_assembly/config/part_gripper_recipes.json'
recipe_bytes=recipe_path.read_bytes();recipe=json.loads(recipe_bytes)['parts']['right_white_brown']
record_path=root/'vision_assembly/data/smd02_assembly_pregrasp_retry_20260906.json'
if record_path.exists():raise RuntimeError('existing approach record requires recovery review')
record=dict(part='SMD-02',physical_alignment_verified=False,physical_contact_height_verified=False,part_held=False,measurement_timestamp=p['timestamp_unix'],stages=[],status='checking')
def save():record_path.write_text(json.dumps(record,indent=2)+'\n')
def fresh():
    if not p.get('validation_passed') or not 0<=time.time()-p['timestamp_unix']<=120:raise RuntimeError('measurement invalid/expired')
    if p.get('instance_index')!=2 or p.get('operator_confirmed_consumed_prefix_count')!=1:raise RuntimeError('wrong physical instance')
    if recipe_path.read_bytes()!=recipe_bytes:raise RuntimeError('recipe changed')
    if p['handeye_sha256']!=hashlib.sha256((root/'calibration/data/handeye_result.json').read_bytes()).hexdigest():raise RuntimeError('handeye changed')
fresh();rclpy.init();n=Executor();started=False
try:
    if not n.client.wait_for_service(timeout_sec=10):raise RuntimeError('service unavailable')
    s=validate_start_state(n);stamp=s.timestamp;deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        s=validate_start_state(n)
        if s.timestamp>stamp:break
    else:raise RuntimeError('state timestamp not advancing')
    n.assert_gripper_ready();start=n.snapshot()
    pe,ae=pose_error(start,[-527.998,-120.961,77.862,180,0,89.999])
    if pe>1 or ae>.2 or int(s.gripper_position)!=17:raise RuntimeError('expected empty observation state')
    xyz=p['part_center_base_mm'];correction=recipe['grasp_center_correction_base_mm']
    if math.hypot(xyz[0]+626.861,xyz[1]+152.345)>2:raise RuntimeError('outside reviewed SMD02 region')
    if [correction['x'],correction['y']]!=[-2.089,2.779]:raise RuntimeError('correction changed')
    xy=[xyz[0]+correction['x'],xyz[1]+correction['y']]
    policy=recipe['pick_orientation_policy'];delta=(p['long_axis_angle_base_deg']-start[5]+180)%360-180
    if policy['symmetric_rotation_branch']!='negative' or not -policy['maximum_rotation_deg']<=delta<=0:raise RuntimeError('rotation outside recipe')
    high=start[2]+100;origin=[*start[:2],high,*start[3:]];target=[*xy,high,*start[3:5],start[5]+delta]
    route=[('SMD02',MotionWaypoint('post_grasp_lift_50mm_vertical',tuple(origin),True))]
    for i in range(1,4):route.append(('SMD02',MotionWaypoint('place_combined_xy_abc_midpoint',tuple(origin[k]+(target[k]-origin[k])*i/3 for k in range(6)),False)))
    final_z=recipe['grasp_height']['taught_tcp_z_mm']+10
    if final_z-xyz[2]<5:raise RuntimeError('insufficient nominal surface clearance')
    for z in (xyz[2]+100,xyz[2]+50,xyz[2]+20,final_z):route.append(('SMD02',MotionWaypoint('place_final_50mm_vertical',tuple([*xy,z,*target[3:]]),True)))
    planned,summary=preflight_route(n,route,n.state_joints(s),dict(travel=10,combined_rotation=10,vertical=3))
    record.update(status='preflighted',start_tcp=start,summary=summary,rotation_delta_deg=delta,target=list(planned[-1].tcp),recipe_sha256=hashlib.sha256(recipe_bytes).hexdigest());save();print(json.dumps(record),flush=True)
    fresh();started=True;n.service('SetSpeed(20)')
    for i,w in enumerate(planned):
        fresh();move_preflighted(n,w);record['stages'].append(w.label);record['last_tcp']=n.snapshot();save()
    n.gripper(18,'SMD02 inspection opening')
    record.update(status='at_pregrasp_alignment_and_contact_height_unverified',last_tcp=n.snapshot(),gripper_position=int(n.state.gripper_position),completed_unix=time.time());save();print(json.dumps(record),flush=True)
except BaseException as e:
    record.update(status='failed',error=str(e))
    if started:
        try:record['stop_response']=n.service('StopMotion()')
        except BaseException as stop_error:record['stop_error']=str(stop_error)
    save();raise
finally:n.destroy_node();rclpy.shutdown()
