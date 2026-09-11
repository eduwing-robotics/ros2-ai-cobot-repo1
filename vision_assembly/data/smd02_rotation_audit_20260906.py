import json, math, time, sys
from pathlib import Path
import numpy as np
import rclpy
sys.path.insert(0, '/home/juchan-yoon/FR5_robot_control/vision_assembly/scripts')
from execute_full_fixed_cycle import Executor, validate_start_state, preflight_route, MotionWaypoint, pose_error
root=Path('/home/juchan-yoon/FR5_robot_control')
p=json.loads(Path('/tmp/smd02_retry_pick_fresh_20260906.json').read_text())
part=next(x for x in p['parts'] if x['instance_index']==2)
assert p['validation_passed'] and part['validation_passed']
recipe=json.loads((root/'vision_assembly/config/part_gripper_recipes.json').read_text())['parts']['right_white_brown']
xy=[part['part_center_base_mm'][0]+recipe['grasp_center_correction_base_mm']['x'],part['part_center_base_mm'][1]+recipe['grasp_center_correction_base_mm']['y']]
rclpy.init(); n=Executor()
# This audit only permits read-only controller queries, never movement or gripper commands.
original_service=n.service
def readonly(command,*args,**kwargs):
    if not command.startswith(('GetJointSoftLimitDeg(', 'GetSafetyStopState(', 'GetInverseKinRef(')):
        raise RuntimeError('audit forbids controller mutation: '+command)
    return original_service(command,*args,**kwargs)
n.service=readonly
try:
    assert n.client.wait_for_service(timeout_sec=10)
    s=validate_start_state(n); stamp=s.timestamp
    deadline=time.monotonic()+4
    while time.monotonic()<deadline:
        s=validate_start_state(n)
        if s.timestamp>stamp:break
    else:raise RuntimeError('stale robot state')
    start=n.snapshot(); ref=json.loads((root/'vision_assembly/config/smd_section_view.json').read_text())['reference_tcp_base']
    pe,ae=pose_error(start,ref)
    assert pe<1 and ae<.2
    initial=n.state_joints(s)
    outputs=[]
    for name,delta in [('measured_axis',(part['long_axis_angle_base_deg']-start[5]+180)%360-180),('candidate_limit',-105.0)]:
        assert -105<=delta<=0
        high=start[2]+100
        anchors=[[ *start[:2],high,*start[3:]]]
        origin=anchors[0]; target=[*xy,high,*start[3:5],start[5]+delta]
        for i in range(1,4):anchors.append([origin[k]+(target[k]-origin[k])*i/3 for k in range(6)])
        # IK through descent and retreat is geometric only; contact clearance is not validated.
        for z in (part['part_center_base_mm'][2]+100,part['part_center_base_mm'][2]+50,part['part_center_base_mm'][2]+20,recipe['grasp_height']['taught_tcp_z_mm']+10,recipe['grasp_height']['taught_tcp_z_mm'],recipe['grasp_height']['taught_tcp_z_mm']+100):
            anchors.append([*xy,z,*target[3:]])
        dense=[]; prev=start
        for index,end in enumerate(anchors):
            steps=max(1, math.ceil(max(abs(end[k]-prev[k]) for k in range(3))/10),math.ceil(abs(end[5]-prev[5])/5))
            for j in range(1,steps+1):
                tcp=tuple(prev[k]+(end[k]-prev[k])*j/steps for k in range(6))
                dense.append(('SMD02RotationAudit',MotionWaypoint('place_final_50mm_vertical' if index==0 or index>=4 else 'place_combined_xy_abc_midpoint',tcp,index==0 or index>=4)))
            prev=end
        planned,summary=preflight_route(n,dense,initial,dict(travel=10,combined_rotation=10,vertical=5))
        outputs.append(dict(case=name,rotation_delta_deg=delta,summary=summary,anchors=anchors,waypoints=[dict(tcp=list(w.tcp),joints=list(w.target_joints),margin=w.minimum_soft_limit_margin_deg) for w in planned]))
        print(json.dumps(dict(case=name,rotation_delta_deg=delta,summary=summary)),flush=True)
    out=dict(timestamp_unix=time.time(),robot_motion_authorized=False,controller_mutations=0,measurement_timestamp_unix=p['timestamp_unix'],measurement_used_for_geometry_only=True,physical_contact_clearance_verified=False,initial_tcp=start,initial_joints=initial.tolist(),cases=outputs)
    (root/'vision_assembly/data/smd02_rotation_audit_20260906.json').write_text(json.dumps(out,indent=2)+'\n')
finally:n.destroy_node();rclpy.shutdown()
