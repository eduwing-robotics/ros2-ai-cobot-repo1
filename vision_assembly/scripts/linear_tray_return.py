"""One straight high-clearance return to TrayHome, with dense IK validation."""
from dataclasses import asdict, replace
import math
import numpy as np
from full_cycle_motion import MotionWaypoint, MotionPlanError, normalize_controller_tcp, validate_joint_path
from execute_full_fixed_cycle import preflight_route
from tray_home_gate import HOME


def coalesce_tray_return(node, planned, speeds):
    starts=[i for i,w in enumerate(planned) if w.label=='tray_after_raise']
    if not starts:
        return planned, None
    if len(starts)!=1:
        raise MotionPlanError('single-pick TrayHome return must have one clearance lift')
    start_index=starts[0];origin=planned[start_index]
    end_index=start_index+1
    while end_index<len(planned) and planned[end_index].label=='tray_after_mid_travel':
        end_index+=1
    if end_index>=len(planned) or planned[end_index].label!='tray_after_travel':
        raise MotionPlanError('TrayHome high return endpoint missing')
    end=planned[end_index];group=planned[start_index+1:end_index+1]
    if len(group)==1 and end.linear:
        return planned, None  # Existing short straight arrival is already one MoveL.
    if len(group)!=3 or not origin.linear or any(w.linear for w in group):
        raise MotionPlanError('unexpected TrayHome high return geometry')
    if end_index+1>=len(planned) or planned[end_index+1].label!='tray_after_inspect':
        raise MotionPlanError('TrayHome return must end before inspection descent')
    if origin.tcp[2]<350 or any(abs(w.tcp[2]-origin.tcp[2])>1e-6 for w in group):
        raise MotionPlanError('single TrayHome return requires constant high clearance')
    if any(abs(end.tcp[k]-HOME[k])>1e-6 for k in (0,1)):
        raise MotionPlanError('TrayHome endpoint differs from existing inspection pose')
    mapped=list(end.tcp)
    for k in (3,4,5):mapped[k]=origin.tcp[k]+(end.tcp[k]-origin.tcp[k]+180)%360-180
    for pose in (origin.tcp,end.tcp):
        if abs((pose[3]-180+180)%360-180)>1e-6 or abs(pose[4])>1e-6:
            raise MotionPlanError('single TrayHome return requires a level tool')
    if abs(mapped[5]-origin.tcp[5])>=180-1e-6:
        raise MotionPlanError('ambiguous 180 degree return rotation')
    # The original TCP checkpoints must lie on exactly this line/rotation arc.
    for i,w in enumerate(group,1):
        if w.slot_code!=origin.slot_code:
            raise MotionPlanError('return crosses part boundary')
        expected=[origin.tcp[k]+(mapped[k]-origin.tcp[k])*i/3 for k in range(6)]
        if (any(abs(w.tcp[k]-expected[k])>1e-5 for k in (0,1,2))
                or any(abs((w.tcp[k]-expected[k]+180)%360-180)>1e-5 for k in (3,4,5))):
            raise MotionPlanError('return checkpoints do not define a straight Cartesian path')
    # Validate the entire continuous line, not merely a distant endpoint. A
    # >95deg total span may be legitimate (e.g. J6 unwinding ~100deg); the old
    # 95deg inter-sample gate is preserved and tightened to 10deg here. No IK
    # branch jump or J6/soft-limit exception is permitted.
    count=max(3,math.ceil(math.dist(origin.tcp[:3],end.tcp[:3])/10.),
              math.ceil(abs(mapped[5]-origin.tcp[5])/5.))
    dense=[(origin.slot_code,MotionWaypoint('tray_return_validation_sample',
        normalize_controller_tcp(tuple(origin.tcp[k]+(mapped[k]-origin.tcp[k])*i/count for k in range(6))),True))
        for i in range(1,count+1)]
    sampled,summary=preflight_route(node,dense,np.asarray(origin.target_joints),speeds)
    validated=validate_joint_path([w.target_joints for w in sampled],
        initial_joints_deg=origin.target_joints,max_step_deg=10.)
    if max(abs(a-b) for a,b in zip(sampled[-1].target_joints,end.target_joints))>.01:
        raise MotionPlanError('single return changes the validated endpoint IK branch')
    merged=replace(end,linear=True,reference_joints=origin.target_joints,
        target_joints=sampled[-1].target_joints,
        minimum_soft_limit_margin_deg=min(w.minimum_soft_limit_margin_deg for w in sampled))
    evidence=dict(policy='trayhome_single_movel_dense_ik_v1',motion_commands=1,
        previous_motion_commands=len(group),original_checkpoints=[asdict(w) for w in group],
        validated_samples=[asdict(w) for w in sampled],sample_maximum_joint_step_deg=validated.maximum_step_deg,
        endpoint_joint_span_deg=max(abs(a-b) for a,b in zip(origin.target_joints,merged.target_joints)),
        maximum_cartesian_sample_distance_mm=10.,maximum_yaw_sample_degrees=5.,
        speed_percent=merged.speed_percent,start_tcp=list(origin.tcp),target_tcp=list(end.tcp))
    return [*planned[:start_index+1],merged,*planned[end_index+1:]], evidence
