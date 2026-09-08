import pytest

from fr5_process_sequences.real_backend import (
    BackendFailure,
    CartesianTarget,
    RealRobotBackend,
    TransferTarget,
)


JOB = "11111111-1111-4111-8111-111111111111"
PICK_OP = "22222222-2222-4222-8222-222222222222"
PLACE_OP = "33333333-3333-4333-8333-333333333333"


def target(x=100.0, y=200.0, z=10.0):
    return CartesianTarget("base_link", x, y, z, 180.0, 0.0, 90.0)


def pick(operation_id=PICK_OP):
    return {
        "job_id": JOB,
        "operation_id": operation_id,
        "action": "robot.pick",
        "order": 1,
        "part_id": "HBM",
        "slot_code": "HBM-01",
        "approach_dz_mm": 100.0,
        "retract_dz_mm": 100.0,
        "grasp_opening_percent": 18.0,
        "release_opening_percent": 25.0,
    }


def place():
    return {
        "job_id": JOB,
        "operation_id": PLACE_OP,
        "action": "robot.place",
        "order": 1,
        "part_id": "HBM",
        "slot_code": "HBM-01",
        "approach_dz_mm": 100.0,
        "retract_dz_mm": 100.0,
        "release_opening_percent": 25.0,
    }


class FakeVision:
    def __init__(self):
        self.calls = []
        self.failure = None

    def locate_part(self, part_id, order):
        self.calls.append(("part", part_id, order))
        if self.failure:
            raise self.failure
        return target()

    def locate_slot(self, part_id, slot_code, order):
        self.calls.append(("slot", part_id, slot_code, order))
        if self.failure:
            raise self.failure
        return target(300.0, -200.0, 20.0)

    def locate_transfer(self, object_id):
        self.calls.append(("transfer", object_id))
        if self.failure:
            raise self.failure
        return TransferTarget(target(), target(500.0, 100.0, 30.0))


class FakeRobot:
    def __init__(self):
        self.log = []
        self.ik_calls = 0
        self.fail_ik_at = None

    def assert_ready(self):
        self.log.append(("ready",))

    def current_joints_deg(self):
        self.log.append(("current",))
        return (0.0,) * 6

    def validate_joint_target(self, joints):
        self.log.append(("validate", tuple(joints)))

    def inverse_kinematics(self, cartesian, reference):
        self.ik_calls += 1
        self.log.append(("ik", cartesian.z_mm, tuple(reference)))
        if self.fail_ik_at == self.ik_calls:
            raise BackendFailure("IK_FAILED", "no solution")
        return (float(self.ik_calls),) * 6

    def move_joint(self, joints):
        self.log.append(("move_joint", tuple(joints)))

    def move_cartesian(self, cartesian, joints, *, linear):
        self.log.append(("move_cartesian", cartesian.z_mm, tuple(joints), linear))

    def move_gripper(self, opening):
        self.log.append(("gripper", opening))

    def wait_arm_complete(self, cartesian, joints, timeout):
        self.log.append(("wait_arm", None if cartesian is None else cartesian.z_mm))

    def wait_gripper_complete(self, opening, timeout):
        self.log.append(("wait_gripper", opening))

    def stop_motion(self):
        self.log.append(("stop",))

    def pause_motion(self):
        self.log.append(("pause",))


class FakeGhost:
    def __init__(self):
        self.targets = []

    def publish_joint_target(self, joints):
        self.targets.append(tuple(joints))
        return True


def backend():
    vision = FakeVision()
    robot = FakeRobot()
    ghost = FakeGhost()
    events = []
    real = RealRobotBackend(
        vision=vision, robot=robot, ghost=ghost, event_sink=events.append
    )
    return real, vision, robot, ghost, events


def test_pick_preflights_all_ik_before_motion_and_publishes_arm_targets_only():
    real, _, robot, ghost, events = backend()
    terminal = real.execute(pick())

    assert terminal.event.value == "OPERATION_COMPLETED"
    assert terminal.phase == "RETRACT"
    assert real.held_part.slot_code == "HBM-01"
    ik_indices = [index for index, item in enumerate(robot.log) if item[0] == "ik"]
    move_indices = [index for index, item in enumerate(robot.log) if item[0].startswith("move_")]
    assert len(ik_indices) == 3
    assert max(ik_indices) < min(move_indices)
    assert len(ghost.targets) == 3
    assert [item[0] for item in robot.log].count("gripper") == 2
    assert events[-1].event.value == "OPERATION_COMPLETED"


def test_matching_place_uses_fresh_slot_vision_and_clears_held_correlation():
    real, vision, _, ghost, _ = backend()
    assert real.execute(pick()).error_code == ""
    terminal = real.execute(place())
    assert terminal.event.value == "OPERATION_COMPLETED"
    assert real.held_part is None
    assert ("slot", "HBM", "HBM-01", 1) in vision.calls
    assert len(ghost.targets) == 6


def test_place_without_matching_pick_is_fail_closed():
    real, _, robot, ghost, _ = backend()
    terminal = real.execute(place())
    assert terminal.event.value == "OPERATION_FAILED"
    assert terminal.error_code == "GRIPPER_FAILED"
    assert not ghost.targets
    assert not any(item[0].startswith("move_") for item in robot.log)


def test_any_ik_failure_prevents_all_arm_and_gripper_motion():
    real, _, robot, ghost, _ = backend()
    robot.fail_ik_at = 2
    terminal = real.execute(pick())
    assert terminal.error_code == "IK_FAILED"
    assert not ghost.targets
    assert not any(item[0].startswith("move_") for item in robot.log)
    assert not any(item[0] == "gripper" for item in robot.log)
    assert ("stop",) in robot.log


def test_camera_failure_preserves_named_error_and_moves_nothing():
    real, vision, robot, ghost, _ = backend()
    vision.failure = BackendFailure("PART_NOT_FOUND", "HBM not found")
    terminal = real.execute(pick())
    assert terminal.error_code == "PART_NOT_FOUND"
    assert not ghost.targets
    assert not any(item[0].startswith("move_") for item in robot.log)


def test_joint_move_uses_direct_yaml_joints_without_ik():
    real, _, robot, ghost, _ = backend()
    command = {
        "job_id": JOB,
        "operation_id": PICK_OP,
        "action": "robot.move_joint",
        "joint_point": [1, 2, 3, 4, 5, 6],
    }
    terminal = real.execute(command)
    assert terminal.event.value == "OPERATION_COMPLETED"
    assert robot.ik_calls == 0
    assert ghost.targets == [(1, 2, 3, 4, 5, 6)]


def test_duplicate_operation_is_replayed_without_repeating_motion():
    real, _, robot, ghost, _ = backend()
    first = real.execute(pick())
    log_count = len(robot.log)
    ghost_count = len(ghost.targets)
    second = real.execute(pick())
    assert second == first
    assert len(robot.log) == log_count
    assert len(ghost.targets) == ghost_count


def test_transfer_preflights_and_executes_six_arm_targets():
    real, _, robot, ghost, _ = backend()
    command = {
        "job_id": JOB,
        "operation_id": PICK_OP,
        "action": "robot.transfer",
        "object_id": "assembled_pcb",
        "approach_dz_mm": 100.0,
        "retract_dz_mm": 100.0,
        "assembled_pcb_drop_approach_dz_mm": 150.0,
        "grasp_opening_percent": 0.0,
        "release_opening_percent": 100.0,
    }
    terminal = real.execute(command)
    assert terminal.phase == "DROP_RETRACT"
    assert robot.ik_calls == 6
    assert len(ghost.targets) == 6
    assert [item[0] for item in robot.log].count("gripper") == 3


def test_active_retransmission_has_one_motion_and_one_consistent_terminal():
    import threading
    from fr5_process_sequences.sequencer_robot_client import SequencerRobotClient

    real, _, robot, ghost, events = backend()
    entered, release = threading.Event(), threading.Event()
    original = robot.wait_arm_complete
    def wait(*args):
        entered.set()
        assert release.wait(3)
        original(*args)
    robot.wait_arm_complete = wait
    workers = []
    def send(command):
        worker = threading.Thread(target=real.execute, args=(command,))
        workers.append(worker)
        worker.start()
    client = SequencerRobotClient(job_id=JOB, send_command=send, send_pause=lambda _: None)
    real._event_sink = lambda event: (events.append(event), client.on_event(event.to_dict()))
    fields = pick()
    for key in ('job_id', 'operation_id', 'action', 'part_id', 'slot_code'):
        fields.pop(key)
    future = client.pickItem('HBM', 'HBM-01', operation_id=PICK_OP, **fields)
    try:
        assert entered.wait(2)
        # Client canonicalizes the pre-open default, so use its exact wire payload.
        command = real._active.to_dict()
        replies = []
        duplicates = [threading.Thread(target=lambda: replies.append(real.execute(command))) for _ in range(8)]
        for worker in duplicates:
            worker.start()
        for worker in duplicates:
            worker.join(2)
            assert not worker.is_alive()
        assert len(replies) == 8
        assert all(reply.event.value.startswith('PHASE_') for reply in replies)
        assert not future.done()
        changed = dict(command, grasp_opening_percent=19)
        rejected = real.execute(changed)
        assert rejected.event.value == 'REQUEST_REJECTED'
        assert rejected.error_code == 'INVALID_REQUEST'
        malformed = dict(command, grasp_opening_percent=101)
        assert real.execute(malformed).event.value == 'REQUEST_REJECTED'
        assert not future.done()
        different = real.execute(place())
        assert different.error_code == 'ROBOT_BUSY'
    finally:
        release.set()
        for worker in workers:
            worker.join(3)
            assert not worker.is_alive()
    assert future.result(timeout=1)['event'] == 'OPERATION_COMPLETED'
    terminals = [e for e in events if e.operation_id == PICK_OP and
                 e.event.value in ('OPERATION_FAILED', 'OPERATION_COMPLETED')]
    assert len(terminals) == 1
    assert terminals[0].event.value == 'OPERATION_COMPLETED'
    assert len(ghost.targets) == 3
    assert [entry[0] for entry in robot.log].count('gripper') == 2
    # A rejected different ID retains its own terminal result on retry.
    assert real.execute(place()) == different
    assert real.execute(command) == terminals[0]


def test_completed_id_with_changed_content_still_rejects_without_motion():
    real, _, robot, _, _ = backend()
    real.execute(pick())
    count = len(robot.log)
    result = real.execute(dict(pick(), grasp_opening_percent=19))
    assert result.event.value == 'REQUEST_REJECTED'
    assert result.error_code == 'INVALID_REQUEST'
    assert len(robot.log) == count


@pytest.mark.parametrize('joint_point', [[1]*6, [1]*5])
def test_conflicting_request_cannot_poison_future_before_completed_callback_is_delivered(joint_point):
    import threading
    from fr5_process_sequences.real_contract import Event
    from fr5_process_sequences.sequencer_robot_client import SequencerRobotClient

    real, _, robot, _, _ = backend()
    entered, release = threading.Event(), threading.Event()
    workers, delivered = [], []
    def send(command):
        worker = threading.Thread(target=real.execute, args=(command,))
        workers.append(worker)
        worker.start()
    client = SequencerRobotClient(job_id=JOB, send_command=send, send_pause=lambda _: None)
    def sink(event):
        if event.event is Event.OPERATION_COMPLETED:
            entered.set()
            assert release.wait(3)
        delivered.append(event)
        client.on_event(event.to_dict())
    real._event_sink = sink
    future = client.moveJoint('Home', [0]*6, operation_id=PICK_OP)
    try:
        assert entered.wait(2)
        assert real._active is None
        assert PICK_OP in real._completed
        changed = dict(job_id=JOB, operation_id=PICK_OP, action='robot.move_joint',
                       point_name='Home', joint_point=joint_point)
        rejection = real.execute(changed)
        assert rejection.event is Event.REQUEST_REJECTED
        assert rejection.error_code == 'INVALID_REQUEST'
        assert not future.done()
    finally:
        release.set()
        for worker in workers:
            worker.join(3)
            assert not worker.is_alive()
    assert future.result(timeout=1)['event'] == 'OPERATION_COMPLETED'
    terminals = [event.event for event in delivered
                 if event.event in (Event.OPERATION_COMPLETED, Event.OPERATION_FAILED)]
    assert terminals == [Event.OPERATION_COMPLETED]
    assert [entry[0] for entry in robot.log].count('move_joint') == 1
