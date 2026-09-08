import threading
from fr5_process_sequences.real_ros_node import FairinoRobotPort


class FakeClient:
    def __init__(self):
        self.calls = []

    def wait_for_service(self, timeout_sec):
        self.calls.append(("wait", timeout_sec))
        return True


class FakeNode:
    def __init__(self):
        self.client = FakeClient()

    @staticmethod
    def create_subscription(*args, **kwargs):
        return object()

    def create_client(self, *args, **kwargs):
        return self.client


def test_disarmed_stop_and_pause_make_no_fairino_service_call():
    node = FakeNode()
    port = FairinoRobotPort(
        node,
        enabled=False,
        state_topic="/state",
        command_service="/command",
        travel_speed_percent=25,
        vertical_speed_percent=10,
    )
    port.stop_motion()
    port.pause_motion()
    assert node.client.calls == []


def test_status_reports_cached_state_without_robot_commands():
    from types import SimpleNamespace
    from std_srvs.srv import Trigger
    from fr5_process_sequences.real_ros_node import RealRobotApiNode
    state = SimpleNamespace(robot_mode=0,tool_num=1,work_num=0,robot_motion_done=1,gripper_feedback_valid=True)
    node = SimpleNamespace(_robot_port=SimpleNamespace(_enabled=False,_fresh_state=lambda:state,_assert_health=lambda _:None),
                           _backend=SimpleNamespace(held_part=None,_recovery_required=False,_state_lock=threading.Lock(),_active=None,
                           event_context=SimpleNamespace(snapshot=lambda: {}),
                           control=SimpleNamespace(status=lambda: {})),
                           _vision_port=SimpleNamespace(_lock=threading.Lock(),_payload=None))
    response = RealRobotApiNode._status_callback(node,None,Trigger.Response())
    import json
    status=json.loads(response.message)
    assert response.success and status['state_fresh']
    assert not status['hardware_execution_enabled']


def test_status_remains_available_when_robot_feedback_is_missing():
    from types import SimpleNamespace
    from std_srvs.srv import Trigger
    from fr5_process_sequences.real_ros_node import RealRobotApiNode
    from fr5_process_sequences.real_backend import BackendFailure
    def missing():raise BackendFailure('ROBOT_TIMEOUT','missing state')
    node=SimpleNamespace(_robot_port=SimpleNamespace(_enabled=False,_fresh_state=missing,_assert_health=lambda _:None),
                         _backend=SimpleNamespace(held_part=None,_recovery_required=False,_state_lock=threading.Lock(),_active=None,
                           event_context=SimpleNamespace(snapshot=lambda: {}),
                           control=SimpleNamespace(status=lambda: {})),
                           _vision_port=SimpleNamespace(_lock=threading.Lock(),_payload=None))
    response=RealRobotApiNode._status_callback(node,None,Trigger.Response())
    import json
    status=json.loads(response.message)
    assert response.success and not status['state_fresh']
    assert status['state_error']=='missing state'
