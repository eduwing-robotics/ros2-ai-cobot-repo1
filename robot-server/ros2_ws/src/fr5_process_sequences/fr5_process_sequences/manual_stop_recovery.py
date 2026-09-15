"""Operator-confirmed, stationary recovery; no motion, gripper actuation or replay."""
import copy
import math
from pathlib import Path
import time
from uuid import uuid4
from .assembly_cycle_api import read, persist
from .real_backend import BackendFailure


def check_state(port, state, allow_abnormal=False):
    checked = copy.deepcopy(state)
    if allow_abnormal:
        checked.abnormal_stop = 0
    port._assert_health(checked)
    if (not port._enabled or state.robot_mode != 0 or state.robot_motion_done != 1
            or state.tool_num != 1 or state.work_num != 0):
        raise BackendFailure('RECOVERY_BLOCKED', 'armed AUTO stopped Tool1/User0 required')
    if not state.gripper_feedback_valid or state.gripperfaultnum or state.grippererro:
        raise BackendFailure('GRIPPER_FAILED', 'valid fault-free gripper feedback required')


def verify_stationary(port, allow_abnormal=False, timeout=5):
    deadline = time.monotonic() + timeout
    previous = -1; since = None; anchor = None; count = 0
    while time.monotonic() < deadline:
        state = port._fresh_state()
        check_state(port, state, allow_abnormal)
        with port._lock:
            sequence = port._state_sequence
        if sequence == previous:
            time.sleep(.01)
            continue
        previous = sequence
        pose = [float(getattr(state, 'cart_' + axis + '_cur_pos')) for axis in 'xyzabc']
        if not all(math.isfinite(v) for v in pose):
            raise BackendFailure('ROBOT_FAULT', 'non-finite TCP feedback')
        if anchor is None:
            anchor = pose; since = time.monotonic()
        if (max(abs(pose[i]-anchor[i]) for i in range(3)) > .2
                or max(abs((pose[i]-anchor[i]+180)%360-180) for i in range(3,6)) > .1):
            raise BackendFailure('RECOVERY_BLOCKED', 'robot moved during recovery verification')
        count += 1
        if count >= 5 and time.monotonic()-since >= .5:
            return dict(tcp=pose, samples=count, abnormal_stop=int(state.abnormal_stop))
        time.sleep(.01)
    raise BackendFailure('ROBOT_TIMEOUT', 'fresh stationary feedback not verified')


def reconcile(bridge, execution_id, confirmation):
    """Called with whole-cycle lock and both exclusive actuator file locks."""
    backend = bridge.node._backend; port = bridge.node._robot_port
    root = bridge.controller.root
    if backend._active is not None:
        raise BackendFailure('ROBOT_BUSY', 'individual operation is still running')
    control = bridge.production.control
    if control is not None and control.worker is not None and control.worker.is_alive():
        raise BackendFailure('ROBOT_BUSY', 'motion control worker is still running')
    held = backend.held_part
    if held is not None and held.job_id != execution_id:
        raise BackendFailure('RECOVERY_BLOCKED', 'held part belongs to another execution')
    lease_path = root/'runtime/assembly_cycles/step_api_owner.json'
    lease = read(lease_path) if lease_path.exists() else None
    if lease is not None:
        process = Path('/proc', str(lease['pid']), 'stat')
        if lease['job_id'] != execution_id or (process.exists()
                and process.read_text().split()[21] == lease['process_start']):
            raise BackendFailure('RECOVERY_BLOCKED', 'another or live step owner remains')
    store = backend._operation_store
    if store is None:
        raise BackendFailure('RECOVERY_BLOCKED', 'durable operation journal required')
    paths = sorted(store.directory.glob('*.json'), key=lambda p:p.stat().st_mtime_ns)
    updates = []
    for index, path in enumerate(paths):
        row = read(path)
        needs = (row.get('status') != 'terminal' or row.get('recovery_required')
                 or (index == len(paths)-1 and row.get('held_candidate')))
        if not needs:
            continue
        if row['request']['job_id'] != execution_id or row.get('status') != 'terminal':
            raise BackendFailure('RECOVERY_BLOCKED', 'unknown outcome or other execution journal requires review')
        updates.append((path,row))
    audit_path = root/'runtime/manual_stop_recovery'/f'{execution_id}-{uuid4()}.json'
    audit_path.parent.mkdir(parents=True,exist_ok=True)
    audit = dict(execution_id=execution_id, scene_confirmation=copy.deepcopy(confirmation),
        before=verify_stationary(port, True), original_lease=lease,
        original_operations={str(p):r for p,r in updates}, motion_sent=False, gripper_command_sent=False)
    persist(audit_path,audit)
    if audit['before']['abnormal_stop']:
        audit['reset_response'] = port._service('ResetAllError()', 'ROBOT_FAULT')
        persist(audit_path,audit)
        # Discard pre-reset feedback; require a later healthy sample before verifying stability.
        deadline = time.monotonic()+5
        baseline = port._state_sequence
        while time.monotonic()<deadline:
            state = port._fresh_state()
            check_state(port,state,True)
            if port._state_sequence>baseline and not state.abnormal_stop:
                break
            time.sleep(.02)
        else:
            raise BackendFailure('RECOVERY_BLOCKED','abnormal stop remains after error reset')
    audit['after'] = verify_stationary(port)
    recovery = dict(recovered_unix=time.time(), evidence=str(audit_path),
        operator_confirmed_empty_gripper=True, original_failure_preserved=True)
    # Preserve original terminal events/fingerprints. Same-ID replay remains terminal.
    for path,row in updates:
        if read(path)!=row:
            raise BackendFailure('RECOVERY_BLOCKED','operation journal changed during recovery')
    for path,row in updates:
        store._write(path,dict(row,held_candidate=False,recovery_required=False,recovery=recovery))
    _, unresolved = store.restore()
    if unresolved:
        raise BackendFailure('RECOVERY_BLOCKED','operation journal still unresolved')
    with backend._state_lock:
        backend._held = None
        backend._recovery_required = False
        backend._paused.clear()
    if control is not None:
        control.blocked.clear()
        control.pause_anchor = None
    if lease is not None:
        if read(lease_path)!=lease:
            raise BackendFailure('RECOVERY_BLOCKED','step ownership changed during recovery')
        lease_path.rename(audit_path.with_suffix('.lease.json'))
    audit.update(recovery_applied=True,recovery=recovery)
    persist(audit_path,audit)
