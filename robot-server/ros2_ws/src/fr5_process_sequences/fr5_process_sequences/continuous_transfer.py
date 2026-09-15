"""Bounded high-clearance MoveJ queues; contact/inspection remain stop points.

Requires the per-command blendT driver extension. Opt-in until commissioned.
"""
import time
import numpy as np
from .real_backend import BackendFailure

HIGH_LABELS = {'pick_combined_xy_abc_midpoint', 'pick_combined_xy_abc',
               'place_combined_xy_abc_midpoint', 'place_combined_xy_abc',
               'tray_after_mid_travel', 'tray_after_travel'}


def transfer_group(planned, index):
    group = []
    for w in planned[index:]:
        if w.linear or w.label not in HIGH_LABELS or w.tcp[2] < 350:
            break
        if group and (w.slot_code != group[0].slot_code or abs(w.tcp[2]-group[0].tcp[2])>.01):
            break
        group.append(w)
        if not ('midpoint' in w.label or 'mid_travel' in w.label):
            break
    if len(group)<2 or len(group)>3: return []
    if 'midpoint' in group[-1].label or 'mid_travel' in group[-1].label: return []
    return group


def wait_transfer_start(node, group, check_context):
    """Wait for the previous lift to settle; never send corrective motion."""
    backend = node.backend
    deadline = time.monotonic() + 2.0
    stable_since = None
    minimum_z = max(349.8, float(group[0].tcp[2]) - .2)
    last = None
    while time.monotonic() < deadline:
        check_context(); backend._assert_not_paused(); node.robot.assert_motion_permitted()
        state = node.spin_state()  # PortExecutor requires distinct fresh feedback.
        z = float(node.state_tcp(state)[2])
        joints = np.asarray(node.state_joints(state), dtype=float)
        error = float(np.max(abs(joints - group[0].reference_joints)))
        if not np.isfinite(z) or not np.isfinite(error):
            raise BackendFailure('SAFETY_STOP', 'nonfinite continuous transfer start feedback')
        if int(state.robot_mode) != 0 or int(state.tool_num) != 1 or int(state.work_num) != 0:
            raise BackendFailure('SAFETY_STOP', 'mode/frame changed before continuous transfer')
        if error > 1.5:
            raise BackendFailure('SAFETY_STOP', 'continuous transfer start reference drift')
        now = time.monotonic()
        last = dict(z_mm=z, minimum_z_mm=minimum_z, joint_error_deg=error,
                    motion_done=int(state.robot_motion_done))
        if z >= minimum_z and int(state.robot_motion_done) == 1:
            if stable_since is None: stable_since = now
            if now - stable_since >= .2:
                node.last_transfer_start_verification = dict(last, stable_seconds=now-stable_since,
                    observed_unix=time.time())
                return
        else:
            stable_since = None
    raise BackendFailure('SAFETY_STOP', 'continuous transfer start did not settle within 2 s; '
                         + str(last))


def execute_transfer(node, group, check_context):
    """Queue already-preflighted points; emit completion only at final endpoint."""
    if len(group)<2 or len(group)>3: raise ValueError('transfer must have 2..3 points')
    if transfer_group(group,0) != group: raise ValueError('invalid high transfer group')
    backend=node.backend; robot=node.robot
    # Retained pause has not been commissioned with buffered trajectories.
    if backend.control.enabled:
        raise BackendFailure('SAFETY_STOP','continuous transfer and retained resume cannot be combined yet')
    robot.assert_continuous_driver()
    check_context();backend._assert_not_paused();robot.assert_ready()
    wait_transfer_start(node, group, check_context)
    for left,right in zip(group,group[1:]):
        if np.max(abs(np.array(left.target_joints)-right.reference_joints))>1e-6:
            raise BackendFailure('SAFETY_STOP','broken preflight reference chain')
    # Resolve all points before starting; no point-definition round trips mid-flight.
    for i,w in enumerate(group,1):
        check_context();backend._assert_not_paused();robot.assert_ready()
        node.service('JNTPoint('+str(i)+','+','.join(f'{v:.6f}' for v in w.target_joints)+')')
    robot.assert_ready()
    wait_transfer_start(node, group, check_context)
    queued=[]
    try:
        for i,w in enumerate(group,1):
            check_context();backend._assert_not_paused()
            robot.assert_motion_permitted()
            state=node.spin_state()
            if int(state.robot_mode)!=0 or int(state.tool_num)!=1 or int(state.work_num)!=0:
                raise BackendFailure('SAFETY_STOP','mode/frame changed during transfer')
            if node.state_tcp(state)[2]<349.0:
                raise BackendFailure('SAFETY_STOP','transfer left high clearance')
            # Final zero blend closes this queue before any descent/gripper command.
            blend=50 if i<len(group) else 0
            command=f'MoveJ(JNT{i},{w.speed_percent},1,0,0,0,0,0,{blend})'
            # Include every intermediate target, even repeated waypoint labels.
            publish = getattr(node, 'publish_motion_target', None)
            if publish is not None:
                try:
                    publish(w, f'{node.phase}:{i:02d}:{w.label}')
                except Exception:
                    pass  # Ghost delivery does not control physical execution.
            check_context(); backend._assert_not_paused()
            robot.assert_motion_permitted()
            robot._service(command,'ROBOT_FAULT')
            queued.append(dict(label=w.label,blend_ms=blend,accepted_unix=time.time()))
        node.waypoint=group[-1]
        actual=node.wait_pose(group[-1].tcp,np.array(group[-1].target_joints))
        return actual,queued
    except BaseException:
        # Stop clears a partially accepted queue; never retry/replay this group.
        backend._recovery_required=True
        try:robot.stop_motion()
        except Exception:pass
        raise
