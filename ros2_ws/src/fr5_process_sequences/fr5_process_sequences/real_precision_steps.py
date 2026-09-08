"""Single-operation bridge to the tested fixed-fixture routes.

No ROS node, sequencing loop, camera motion, or production DB lives here.
Pick explicitly includes its agreed TrayHome removal inspection. Place ends
at the slot's 100 mm retract. All coordinates remain backend-owned.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
from .real_backend import BackendFailure, HeldPart
from .real_contract import Action, Event


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def single_route(item, start, transfer_z, action):
    from execute_full_fixed_cycle import build_tcp_route
    from tray_home_gate import add_inspections
    from full_cycle_motion import MotionWaypoint
    route = build_tcp_route([item], list(start), transfer_z, resume_after_grasp=False)
    if action is Action.PICK:
        inspected = add_inspections(route, start)
        end = next(i for i, (_, w) in enumerate(inspected) if w.label == 'tray_after_inspect')
        return inspected[:end + 1]
    # Same wrapped, two-midpoint board transfer as the tested inspection route,
    # rebased on the measured pose after the Sequencer's explicit joint moves.
    end = next(i for i, (_, w) in enumerate(route) if w.label == 'place_combined_xy_abc')
    destination = route[end][1]
    height = max(float(destination.tcp[2]), float(start[2]), 350.)
    origin = (*start[:2], height, *start[3:])
    target = list(destination.tcp); target[2] = height
    for axis in (3, 4, 5):
        target[axis] = origin[axis] + (target[axis] - origin[axis] + 180) % 360 - 180
    outgoing = [MotionWaypoint('tray_after_depart', origin, True)]
    for f in (1/3, 2/3):
        outgoing.append(MotionWaypoint('place_combined_xy_abc_midpoint',
            tuple(origin[k] + f * (target[k] - origin[k]) for k in range(6)), False))
    outgoing.append(MotionWaypoint(destination.label, (*destination.tcp[:2], height, *destination.tcp[3:]), False))
    return [(item['slot_code'], w) for w in outgoing] + route[end + 1:]


class PortExecutor:
    """Use the API node's subscribed feedback; never spin a second ROS executor."""
    def __init__(self, backend, operation):
        self.backend = backend; self.operation = operation; self.robot = backend._robot
        self.waypoint = None; self.phase = ''; self.last_pose_verification = None

    @property
    def state_sequence(self):
        with self.robot._lock:
            return self.robot._state_sequence

    def operation_clock(self):
        control = getattr(self.backend, 'control', None)
        return control.clock() if control is not None else time.monotonic()

    def spin_state(self, timeout_sec=.25, *, after_sequence=None):
        baseline = self.state_sequence if after_sequence is None else after_sequence
        deadline = self.operation_clock() + timeout_sec
        while self.operation_clock() < deadline:
            self.backend._assert_not_paused()
            with self.robot._lock:
                state = self.robot._state
                sequence = self.robot._state_sequence
                age = time.monotonic() - self.robot._state_received_at
            if state is not None and sequence > baseline and 0 <= age <= .25:
                error = self.safety_error(state)
                if error: raise BackendFailure('SAFETY_STOP', error)
                return state
            time.sleep(.005)
        raise BackendFailure('ROBOT_TIMEOUT', 'no distinct fresh FR5 feedback within 250 ms')

    @staticmethod
    def state_joints(state):
        return np.array([getattr(state, f'j{i}_cur_pos') for i in range(1, 7)], float)

    @staticmethod
    def state_tcp(state):
        return [float(getattr(state, f'cart_{axis}_cur_pos')) for axis in 'xyzabc']

    @staticmethod
    def safety_error(state):
        from execute_cached_hbm_remaining import Executor
        return Executor.safety_error(state)

    @staticmethod
    def response_values(response, count, label):
        from execute_cached_hbm_remaining import Executor
        return Executor.response_values(response, count, label)

    def service(self, command, *, state_validator=None, timeout_sec=None):
        self.backend._assert_not_paused()
        if command.startswith(('Move', 'SetSpeed', 'JNTPoint')):
            self.robot.assert_ready()
            state = self.robot._fresh_state()
            if state_validator is not None: state_validator(state)
        if command.startswith(('MoveJ(', 'MoveL(')):
            w = self.waypoint
            if w is None: raise BackendFailure('SAFETY_STOP', 'motion without preflight target')
            try:
                self.backend._ghost.publish_stage_target(w.target_joints,
                    job_id=self.operation.job_id, operation_id=self.operation.operation_id,
                    action=self.operation.action.value, phase=self.phase,
                    point_name=self.operation.slot_code or self.operation.point_name)
            except Exception:
                pass  # visualization delivery is never an execution permission
            self.robot.assert_ready()
            if state_validator is not None: state_validator(self.robot._fresh_state())
            self.backend._assert_not_paused()
        return self.robot._service(command, 'ROBOT_FAULT')

    def wait_pose(self, target, target_joints):
        from execute_full_fixed_cycle import pose_error
        deadline = self.operation_clock() + self.backend._arm_timeout_sec
        while self.operation_clock() < deadline:
            state = self.spin_state()
            pose = self.state_tcp(state)
            p, a = pose_error(pose, target)
            if (int(state.robot_motion_done) == 1 and p <= 1 and a <= 1
                    and np.max(abs(self.state_joints(state) - target_joints)) <= 1):
                self.last_pose_verification = dict(tcp=pose, state_sequence=self.state_sequence,
                    observed_unix=time.time(), gripper_position=float(state.gripper_position))
                return pose
        raise BackendFailure('ROBOT_TIMEOUT', 'single-step arm completion timeout')

    def gripper(self, position, profile):
        phase = getattr(self, 'gripper_phase', 'GRASP')
        if phase not in ('PREOPEN', 'GRASP', 'RELEASE'):
            raise BackendFailure('INVALID_REQUEST', 'unknown gripper phase')
        self.last_gripper_verification = None
        from feedback_settle import FeedbackSettle
        # Tested settling policy: stable TCP for .5 s before changing fingers.
        settle = FeedbackSettle(duration=.5); anchor = None
        deadline = self.operation_clock() + 8
        while self.operation_clock() < deadline:
            state = self.spin_state(); pose = np.asarray(self.state_tcp(state))
            if not bool(state.gripper_feedback_valid) or int(state.gripperfaultnum) or int(state.grippererro):
                raise BackendFailure('GRIPPER_FAILED', 'invalid gripper feedback/fault')
            if anchor is None: anchor = pose.copy()
            valid = (int(state.robot_motion_done) == 1 and np.max(abs(pose[:3]-anchor[:3])) <= .2
                and np.max(abs((pose[3:]-anchor[3:]+180)%360-180)) <= .1)
            if not valid: anchor = pose.copy()
            if settle.update(self.state_sequence, time.monotonic(), valid): break
        else: raise BackendFailure('GRIPPER_FAILED', 'TCP did not settle before gripper command')
        self.backend._assert_not_paused()
        self.robot.move_profiled_gripper(position, profile)
        settle = FeedbackSettle(duration=1.0)
        no_object = FeedbackSettle(duration=1.0)
        accepted_after = time.monotonic() + .2
        deadline = self.operation_clock() + self.backend._gripper_timeout_sec
        while self.operation_clock() < deadline:
            state = self.spin_state(); now = time.monotonic()
            motion_status = int(state.grip_motion_done)
            sample = dict(phase=phase, target_position=float(position),
                actual_position=float(state.gripper_position),
                grip_motion_done=motion_status,
                gripper_feedback_valid=bool(state.gripper_feedback_valid),
                robot_motion_done=int(state.robot_motion_done),
                gripperfaultnum=int(state.gripperfaultnum), grippererro=int(state.grippererro),
                state_sequence=self.state_sequence, observed_unix=time.time(),
                controller_object_detected=motion_status == 1,
                physical_holding_verified=False)
            self.last_gripper_verification = sample
            if not sample['gripper_feedback_valid'] or sample['gripperfaultnum'] or sample['grippererro']:
                raise BackendFailure('GRIPPER_FAILED', 'invalid gripper feedback/fault: ' + json.dumps(sample))
            if motion_status not in (0, 1, 2):
                raise BackendFailure('GRIPPER_FAILED', 'unknown gripper motion status: ' + json.dumps(sample))
            ready = (now >= accepted_after and sample['robot_motion_done'] == 1
                and sample['actual_position'] == float(position))
            # FR5 v3.9.7: 1=completed/object detected; 2=completed/no object.
            # Empty opening/release may complete with 2. Closing with 2 must
            # not authorize a lift or be mislabeled as a motion timeout.
            valid = ready and (motion_status == 1 or
                (motion_status == 2 and phase in ('PREOPEN', 'RELEASE')))
            if settle.update(self.state_sequence, now, valid):
                sample['continuous_feedback_verified'] = True
                return
            if no_object.update(self.state_sequence, now,
                    ready and phase == 'GRASP' and motion_status == 2):
                raise BackendFailure('GRIPPER_FAILED',
                    'GRASP_OBJECT_NOT_DETECTED: close motion completed but controller reports no object; '
                    'hold position for operator reconciliation, no automatic lift: ' + json.dumps(sample))
        raise BackendFailure('GRIPPER_FAILED',
            'GRIPPER_FEEDBACK_TIMEOUT: no continuous 1 s valid completion; last_feedback=' +
            json.dumps(self.last_gripper_verification))



class PrecisionSteps:
    def __init__(self, root, *, executor_factory=PortExecutor):
        self.root = Path(root)
        scripts = str(self.root / 'vision_assembly/scripts')
        if scripts not in sys.path: sys.path.insert(0, scripts)
        self.executor_factory = executor_factory
        self.units = {}; self.sources = {}; self.held_plan = None; self.verified_pick = None
        # A restart never silently reconstructs consumed tray cells from images.
        self.previous_jobs = set()
        for path in (self.root / 'runtime/robot_step_evidence').glob('*.json'):
            row = json.loads(path.read_text())
            if row.get('source_cycle_id'):
                self.sources[row['source_cycle_id']] = row['job_id']
                self.previous_jobs.add(row['job_id'])
        for path in (self.root / 'runtime/robot_operations').glob('*.json'):
            row = json.loads(path.read_text())
            if row.get('request', {}).get('action') in ('robot.pick', 'robot.place'):
                self.previous_jobs.add(row['request']['job_id'])

    def execute_camera(self, backend, operation):
        """One explicitly requested camera endpoint, using its taught safe route."""
        from cycle_camera_stage import camera_route, finite_pose
        from execute_full_fixed_cycle import preflight_route, move_preflighted, pose_error
        from execute_cached_hbm_remaining import atomic_write
        if backend.held_part is not None:
            raise BackendFailure('GRIPPER_FAILED', 'camera reposition requires no held candidate')
        node = self.executor_factory(backend, operation)
        baseline = json.loads((self.root/'vision_assembly/checkpoints/full_cycle_success_20260906/runtime.json').read_text())
        tcp = node.response_values(node.service('GetTCPOffset(1)'), 6, 'Tool1 offset')
        if not np.allclose(tcp, baseline['active_tcp_offset'], atol=.1, rtol=0):
            raise BackendFailure('SAFETY_STOP', 'Tool1 offset changed')
        name = operation.point_name
        if name == 'SMDView':
            target = finite_pose(json.loads((self.root/'vision_assembly/config/smd_section_view.json').read_text())['reference_tcp_base'])
        else:
            taught = node.response_values(node.service(f'GetRobotTeachingPoint({name})'),14,name)
            if tuple(taught[12:14]) != (1.,0.):
                raise BackendFailure('SAFETY_STOP', 'camera teaching point requires Tool1/User0')
            target = finite_pose(taught[:6])
            p,a = pose_error(list(target), baseline['teaching_points'][name][:6])
            if p > 1 or a > 1:
                raise BackendFailure('SAFETY_STOP', 'camera teaching point changed from success baseline')
        state = node.spin_state()
        route = camera_route(node.state_tcp(state), target, name)
        planned, summary = preflight_route(node,route,node.state_joints(state),
                                           dict(travel=25,combined_rotation=25,vertical=10))
        if not planned or max(abs(a-b) for a,b in zip(planned[-1].target_joints,operation.joint_point)) > 1.0:
            raise BackendFailure('INVALID_REQUEST', 'requested camera endpoint differs from current referenced route')
        # move_joint still ends at its requested joint target. Reject alternate
        # branches; retain linear vertical segments inside this named safe route.
        record = dict(job_id=operation.job_id,operation_id=operation.operation_id,
                      point_name=name,preflight=summary,phases=[])
        directory=self.root/'runtime/robot_step_evidence';directory.mkdir(parents=True,exist_ok=True)
        path=directory/(operation.operation_id+'.json')
        node.service('SetSpeed(20)')
        touched=False
        try:
            for index,w in enumerate(planned):
                backend._assert_phase_ready()
                phase=f'{index+1:02d}_{w.label}';node.waypoint=w;node.phase=phase
                backend._phase_event(operation,phase,Event.PHASE_STARTED)
                entry=dict(phase=phase,target_tcp=list(w.tcp),target_joints=list(w.target_joints),status='intent')
                record['phases'].append(entry);atomic_write(path,record)
                touched=True
                actual=move_preflighted(node,w)
                entry.update(status='verified',actual_tcp=actual);atomic_write(path,record)
                backend._phase_event(operation,phase,Event.PHASE_COMPLETED)
            record.update(status='completed',exit_tcp=actual);atomic_write(path,record)
            backend._completion_message=json.dumps(dict(exit_pose=name,exit_tcp_mm_deg=actual,physical_placement_verified=False))
            return phase
        except Exception:
            if touched:backend._recovery_required=True
            raise

    def execute(self, backend, operation):
        from execute_full_fixed_cycle import preflight_route, move_preflighted, validate_plan
        from tray_home_gate import wait_inventory
        pick = operation.action is Action.PICK
        expected = HeldPart(operation.job_id, operation.part_id, operation.slot_code,
                            operation.order, operation.source_index)
        if pick and backend.held_part is not None:
            raise BackendFailure('GRIPPER_FAILED', 'previous held candidate has not been placed')
        if not pick and (backend.held_part != expected or self.verified_pick != expected):
            raise BackendFailure('GRIPPER_FAILED', 'Place requires matching completed Pick/removal inspection')
        if operation.job_id in self.previous_jobs:
            raise BackendFailure('SAFETY_STOP', 'Unit existed before restart; reconcile scene and prepare a new Unit')
        if operation.approach_dz_mm != 100 or operation.retract_dz_mm != 100:
            raise BackendFailure('INVALID_REQUEST', 'tested precision profile requires approach/retract=100 mm')
        if operation.source_index is None:
            raise BackendFailure('INVALID_REQUEST', 'source_index is required for precision steps')
        payload = (backend._vision.precision_snapshot(operation) if pick
                   else deepcopy(self.held_plan))
        if not isinstance(payload, dict):
            raise BackendFailure('CAMERA_NOT_READY', 'backend precision plan is missing')
        plan = payload.get('precision_plan')
        if not isinstance(plan, dict) or digest(plan) != payload.get('plan_sha256'):
            raise BackendFailure('CAMERA_NOT_READY', 'precision plan missing or hash mismatch')
        age_limit = 1800. if payload.get('target_mode') == 'frozen_unit' else 2.5
        def check_age():
            stamp = float(payload['timestamp_ros_ns']) / 1e9
            if not 0 <= time.time() - stamp <= age_limit:
                raise BackendFailure('CAMERA_NOT_READY', 'original frozen/source observations expired')
        check_age()
        selection = plan.get('plan_selection', {})
        kwargs = {}
        if selection.get('mode') == 'explicit_slots': kwargs['requested_selected_slots'] = selection['selected_slots']
        if selection.get('mode') == 'single_slot': kwargs['requested_only_slot'] = selection['requested_only_slot']
        items = validate_plan(plan, age_limit, **kwargs)
        matches = [i for i in items if i['slot_code'] == operation.slot_code]
        if len(matches) != 1: raise BackendFailure('INVALID_REQUEST', 'slot absent/ambiguous in precision plan')
        item = matches[0]
        from .real_vision_adapter import PART_TYPES
        if item['part_type'] != PART_TYPES[operation.part_id] or item['tray_instance_index'] != operation.source_index:
            raise BackendFailure('INVALID_REQUEST', 'precision item/source correlation mismatch')
        row = next((r for r in payload['parts'] if r['slot_code'] == operation.slot_code), None)
        if row is None or any(row.get(k) != getattr(operation, k) for k in
                ('job_id', 'part_id', 'slot_code', 'order', 'source_index')):
            raise BackendFailure('INVALID_REQUEST', 'resolved recipe correlation mismatch')
        for field, key in [('pregrasp_opening_percent','tray_open_position'), ('grasp_opening_percent','grip_position'), ('release_opening_percent','release_position')]:
            if row['expected_gripper'].get(field) != item[key]:
                raise BackendFailure('INVALID_REQUEST', 'profile and precision plan disagree')
        fields = ('pregrasp_opening_percent', 'grasp_opening_percent', 'release_opening_percent') if pick else ('release_opening_percent',)
        for field in fields:
            if getattr(operation, field) != row['expected_gripper'][field]:
                raise BackendFailure('INVALID_REQUEST', f'{field} differs from calibrated recipe')
        backend.event_context.bind(operation, payload, row)
        profiles = row['gripper_profiles']
        for profile in profiles.values():
            if any(isinstance(profile.get(k), bool) or not isinstance(profile.get(k), (int, float))
                   or not math.isfinite(profile[k]) or not 0 <= profile[k] <= 100
                   for k in ('velocity_percent', 'force_percent')):
                raise BackendFailure('INVALID_REQUEST', 'invalid gripper profile')
        if set(profiles) != {'PREOPEN', 'GRASP', 'RELEASE'}:
            raise BackendFailure('INVALID_REQUEST', 'missing gripper profile')
        for name, relative in [('recipes', 'vision_assembly/config/part_gripper_recipes.json'), ('slots', 'vision_assembly/config/assembly_slots_r1.json')]:
            if digest(json.loads((self.root / relative).read_text())) != payload.get('calibration_digests', {}).get(name):
                raise BackendFailure('CAMERA_NOT_READY', 'calibration changed since target preparation')
        calibration = self.root / 'calibration/data/handeye_result.json'
        reference = payload.get('tray_inspection_reference', plan.get('tray_inspection_reference'))
        if not isinstance(reference, dict) or reference.get('handeye_sha256') != hashlib.sha256(calibration.read_bytes()).hexdigest():
            raise BackendFailure('CAMERA_NOT_READY', 'TrayHome reference/calibration mismatch')
        bindings = [b for b in reference.get('bindings', []) if b['part_type'] == item['part_type']
                    and b['physical_index'] == operation.source_index]
        if len(bindings) != 1 or np.asarray(bindings[0]['reference_center_pixel']).shape != (2,) or not np.isfinite(bindings[0]['reference_center_pixel']).all():
            raise BackendFailure('CAMERA_NOT_READY', 'picked cell has no unique TrayHome reference')
        source = payload.get('source_cycle_id')
        if not source:
            raise BackendFailure('INVALID_REQUEST', 'fixed scene identity missing')
        owner = self.sources.setdefault(source, operation.job_id)
        if owner != operation.job_id:
            raise BackendFailure('INVALID_REQUEST', 'same tray capture cannot be reused for a new Unit')
        unit = self.units.setdefault(operation.job_id, dict(plan_sha256=payload['plan_sha256'], removed=set(),
            scope={i['slot_code'] for i in items}, mode=selection.get('mode'), placed=set()))
        if unit['plan_sha256'] != payload['plan_sha256']:
            # Existing launcher measures SMD only after all ordinary parts.
            # Append exactly that disjoint phase; never replace prior targets.
            incoming={i['slot_code'] for i in items}
            if (unit['mode']!='non-smd' or selection.get('mode')!='smd'
                    or unit['placed']!=unit['scope'] or unit['scope'] & incoming
                    or backend.held_part is not None):
                raise BackendFailure('INVALID_REQUEST', 'fixed Unit plan changed outside completed non-SMD to SMD transition')
            unit.update(plan_sha256=payload['plan_sha256'],scope=incoming,mode='smd',placed=set())
        if pick and operation.slot_code in unit['removed']:
            raise BackendFailure('INVALID_REQUEST', 'source cell already consumed in this Unit')
        node = self.executor_factory(backend, operation)
        def validate_resume():
            check_age()
            for name, relative in [('recipes', 'vision_assembly/config/part_gripper_recipes.json'),
                                   ('slots', 'vision_assembly/config/assembly_slots_r1.json')]:
                if digest(json.loads((self.root / relative).read_text())) != payload['calibration_digests'][name]:
                    raise BackendFailure('SAFETY_STOP', 'configuration changed during pause')
            if backend._recovery_required or backend._paused.is_set():
                raise BackendFailure('SAFETY_STOP', 'failed/cancelled operation cannot resume')
            if backend.held_part is not None and backend.held_part != expected:
                raise BackendFailure('GRIPPER_FAILED', 'held identity changed during pause')
        backend.control.register(operation, validate_resume)
        state = node.spin_state(); start = node.state_tcp(state)
        if not bool(state.gripper_feedback_valid):
            raise BackendFailure('GRIPPER_FAILED', 'gripper feedback unavailable')
        if not pick and float(state.gripper_position) != float(item['grip_position']):
            raise BackendFailure('GRIPPER_FAILED', 'gripper changed since completed Pick')
        route = single_route(item, start, plan['transfer_z_mm'], operation.action)
        planned, summary = preflight_route(node, route, node.state_joints(state), plan['speeds_percent'])
        node.service('SetSpeed(40)')
        record = dict(job_id=operation.job_id, operation_id=operation.operation_id,
                      slot=operation.slot_code, action=operation.action.value,
                      plan_sha256=payload['plan_sha256'], source_cycle_id=payload['source_cycle_id'], preflight=summary, phases=[])
        record_dir = self.root / 'runtime/robot_step_evidence'; record_dir.mkdir(parents=True, exist_ok=True)
        path = record_dir / (operation.operation_id + '.json')
        from execute_cached_hbm_remaining import atomic_write
        touched = False
        try:
            skip_until = 0
            for index, w in enumerate(planned):
                if index < skip_until: continue
                if getattr(backend, 'continuous_transfer_enabled', False):
                    from .continuous_transfer import transfer_group, execute_transfer
                    group = transfer_group(planned, index)
                    if group:
                        check_age(); backend._assert_phase_ready()
                        phase = f'{index+1:02d}_CONTINUOUS_TRANSFER'
                        node.phase = phase
                        entry = dict(phase=phase, status='intent',
                            waypoints=[dict(label=q.label, tcp=list(q.tcp), joints=list(q.target_joints)) for q in group])
                        record['phases'].append(entry); atomic_write(path, record)
                        backend._phase_event(operation, phase, Event.PHASE_STARTED)
                        touched = True
                        actual, accepted = execute_transfer(node, group, check_age)
                        entry.update(status='verified', actual_tcp=actual, accepted=accepted,
                                     feedback=node.last_pose_verification)
                        atomic_write(path, record)
                        backend._phase_event(operation, phase, Event.PHASE_COMPLETED, feedback=node.last_pose_verification)
                        skip_until = index + len(group)
                        continue
                check_age(); backend._assert_phase_ready()
                phase = f'{index + 1:02d}_{w.label}'  # repeated midpoint labels need distinct IDs
                node.waypoint = w; node.phase = phase
                backend._phase_event(operation, phase, Event.PHASE_STARTED)
                entry = dict(phase=phase, target_tcp=list(w.tcp), target_joints=list(w.target_joints), status='intent')
                record['phases'].append(entry); atomic_write(path, record)
                touched = True
                actual = move_preflighted(node, w)
                entry.update(status='verified', actual_tcp=actual, feedback=node.last_pose_verification)
                atomic_write(path, record)
                backend._phase_event(operation, phase, Event.PHASE_COMPLETED, feedback=node.last_pose_verification)
                gripper = {'pick_hover_100mm_vertical': ('PREOPEN', operation.pregrasp_opening_percent),
                           'pick_final_50mm_vertical': ('GRASP', operation.grasp_opening_percent),
                           'place_final_50mm_vertical': ('RELEASE', operation.release_opening_percent)}.get(w.label)
                if gripper:
                    name, position = gripper
                    backend._phase_event(operation, name, Event.PHASE_STARTED)
                    record['gripper'] = dict(phase=name, position=position, status='intent'); atomic_write(path, record)
                    # Conservatively retain candidate even if RPC/feedback fails.
                    if name == 'GRASP':
                        with backend._state_lock: backend._held = expected
                    node.gripper_phase = name
                    try:
                        node.gripper(position, profiles[name])
                    except Exception as error:
                        record['gripper'].update(status='failed', error=str(error),
                            feedback=getattr(node, 'last_gripper_verification', None))
                        atomic_write(path, record)
                        raise
                    record['gripper']['feedback'] = getattr(node, 'last_gripper_verification', None)
                    if name == 'RELEASE':
                        with backend._state_lock: backend._held = None
                    record['gripper']['status'] = 'feedback_verified'; atomic_write(path, record)
                    backend._phase_event(operation, name, Event.PHASE_COMPLETED,
                        feedback=getattr(node, 'last_gripper_verification', None))
            if pick:
                backend._phase_event(operation, 'TRAY_REMOVAL_INSPECTION', Event.PHASE_STARTED)
                removed = unit['removed'] | {operation.slot_code}
                state = node.spin_state()
                if float(state.gripper_position) != float(item['grip_position']):
                    raise BackendFailure('GRIPPER_FAILED', 'gripper changed before removal inspection')
                evidence = wait_inventory(node, self.root / 'vision_assembly/data/tray_detections_last.json',
                    reference, removed, {}, picked_slot=operation.slot_code)
                state = node.spin_state()
                from execute_full_fixed_cycle import pose_error
                from tray_home_gate import HOME
                p, a = pose_error(node.state_tcp(state), list(HOME))
                if p > 1 or a > 1 or float(state.gripper_position) != float(item['grip_position']):
                    raise BackendFailure('GRIPPER_FAILED', 'inspection exit pose/gripper changed')
                actual = node.state_tcp(state)
                self.verified_pick = expected; self.held_plan = deepcopy(payload)
                unit['removed'] = removed
                backend._phase_event(operation, 'TRAY_REMOVAL_INSPECTION', Event.PHASE_COMPLETED)
                phase = 'TRAY_REMOVAL_INSPECTION'
            else:
                evidence = dict(evidence='release_and_retract_feedback_not_precision_placement_proof')
                self.verified_pick = None; self.held_plan = None
                unit['placed'].add(operation.slot_code)
                phase = node.phase
            record.update(status='completed', evidence=evidence, exit_tcp=actual)
            atomic_write(path, record)
            backend._completion_message = json.dumps(dict(evidence=evidence, exit_tcp_mm_deg=actual,
                exit_pose='TrayHome' if pick else 'slot_retract_100mm', physical_holding_verified=False,
                precision_placement_verified=False), allow_nan=False)
            return phase
        except Exception:
            if touched: backend._recovery_required = True
            raise
