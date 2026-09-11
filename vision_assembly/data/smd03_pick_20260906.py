import sys,json,time,hashlib
from pathlib import Path
sys.path.insert(0,'/home/juchan-yoon/FR5_robot_control/vision_assembly/scripts')
import rclpy
from execute_full_fixed_cycle import Executor,validate_start_state,preflight_route,move_preflighted,MotionWaypoint,pose_error
root=Path('/home/juchan-yoon/FR5_robot_control')
record_path=root/'vision_assembly/data/smd03_pick_attempt_20260906.json'
if record_path.exists():raise RuntimeError('pick record already exists; explicit recovery required')
recipe_path=root/'vision_assembly/config/part_gripper_recipes.json'
recipe=json.loads(recipe_path.read_text())['parts']['right_white_brown']
height=float(recipe['grasp_height']['taught_tcp_z_mm'])
if abs(height+52.177)>1e-6 or recipe['grip']['args'][1]!=12 or recipe['tray_pick_open']['args'][1]!=18:
    raise RuntimeError('SMD03 taught recipe mismatch')
approach=json.loads((root/'vision_assembly/data/smd03_assembly_pregrasp_retry_20260906.json').read_text())
if approach['status']!='at_pregrasp_alignment_and_contact_height_unverified' or not 0<=time.time()-approach['completed_unix']<60:raise RuntimeError('fresh completed SMD03 approach required')
record=dict(part='SMD-03',status='checking',operator_alignment_report='fresh measured SMD03 target; same fixture height exercised by SMD02; operator requested remaining assembly',physical_alignment_independently_verified=False,physical_grasp_verified=False,part_held_candidate=False,recipe_sha256=hashlib.sha256(recipe_path.read_bytes()).hexdigest(),started_unix=time.time(),stages=[])
def save():record_path.write_text(json.dumps(record,ensure_ascii=False,indent=2))
rclpy.init();n=Executor();started_commands=False
try:
    if not n.client.wait_for_service(timeout_sec=10):raise RuntimeError('service unavailable')
    s=validate_start_state(n);n.assert_gripper_ready();start=n.snapshot()
    pe,ae=pose_error(start,approach['target'])
    if pe>.5 or ae>.2:raise RuntimeError('not at freshly measured corrected pregrasp position')
    stamp=s.timestamp;deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        s=validate_start_state(n)
        if s.timestamp>stamp:break
    else:raise RuntimeError('controller timestamp not advancing')
    if int(s.gripper_position)!=18:raise RuntimeError('unexpected initial gripper opening')
    route=[]
    for z in (height+5,height,height+20):
        target=tuple([*start[:2],z,*start[3:]])
        route.append(('SMD03Pick',MotionWaypoint('place_final_50mm_vertical',target,True)))
    planned,summary=preflight_route(n,route,n.state_joints(s),dict(travel=1,combined_rotation=1,vertical=1))
    record.update(start_tcp=start,summary=summary,targets=[list(w.tcp) for w in planned],status='preflighted');save()
    print(json.dumps(record,ensure_ascii=False),flush=True)
    started_commands=True;n.service('SetSpeed(20)')
    n.gripper(18,'SMD03 taught pre-pick opening')
    record['stages'].append('opening18_feedback_settled');save()
    for i,w in enumerate(planned[:2]):
        move_preflighted(n,w)
        record['stages'].append('descent_'+str(i+1));record['last_tcp']=n.snapshot();save()
    n.gripper(12,'SMD03 grasp')
    record.update(status='closed_feedback_settled',part_held_candidate=True);record['stages'].append('close12_feedback_settled');save()
    move_preflighted(n,planned[2])
    validate_start_state(n);n.assert_gripper_ready()
    record.update(status='paused_after_20mm_lift_visual_hold_check_required',last_tcp=n.snapshot(),last_gripper_position=int(n.state.gripper_position),completed_unix=time.time())
    record['stages'].append('vertical20mm_lift_complete');save()
    print(json.dumps(record,ensure_ascii=False),flush=True)
except BaseException as exc:
    record.update(status='interrupted_or_failed',error=str(exc),failed_unix=time.time())
    if started_commands:
        try:record['stop_response']=n.service('StopMotion()')
        except BaseException as stop_error:record['stop_error']=str(stop_error)
    save();raise
finally:n.destroy_node();rclpy.shutdown()
