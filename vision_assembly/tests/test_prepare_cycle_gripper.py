from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_cycle_gripper import prepare


def run(active=False, failure=None):
    calls=[]
    now=[0.]
    state=dict(api_capabilities_revision='step-cycle-20260908',
        hardware_execution_enabled=True,state_fresh=True,robot_health_clear=True,
        robot_motion_done=1,robot_mode=0,tool_num=1,work_num=0,
        held_candidate=None,gripper_feedback_valid=active)
    if failure=='unsafe':state['robot_mode']=1
    if failure=='fault':state['grippererro']=1
    def command(cmd):
        nonlocal active
        calls.append(cmd)
        if cmd=='GetGripperActivateStatus()':return '0,0,'+str(int(active))
        assert cmd=='ActGripper(1,1)'
        if failure=='command':return '1'
        active=True
        state['gripper_feedback_valid']=failure!='timeout'
        return '0'
    def sleep(t):now[0]+=t
    return lambda:prepare(lambda:dict(state),command,lambda:now[0],sleep),calls,now


@pytest.mark.parametrize('active', [False,True])
def test_activation_only_when_needed_and_feedback_settles(active):
    execute,calls,now=run(active)
    assert execute()==dict(activation_sent=not active,feedback_verified=True)
    assert calls.count('ActGripper(1,1)')==int(not active)
    assert now[0]>=1


@pytest.mark.parametrize('failure', ['unsafe','fault','command','timeout'])
def test_failed_startup_never_retries_or_proceeds(failure):
    execute,calls,now=run(failure=failure)
    with pytest.raises(RuntimeError):execute()
    assert calls.count('ActGripper(1,1)') <= 1
    if failure in ('unsafe','fault'):assert not calls


class DiscoveryClient:
    def __init__(self, name, now, ready_at):
        self.srv_name, self.now, self.ready_at = name, now, ready_at
        self.sent = []
        self.future = None

    def wait_for_service(self, timeout_sec):
        delay = max(0, self.ready_at - self.now[0])
        self.now[0] += min(delay, timeout_sec)
        return delay <= timeout_sec

    def call_async(self, request):
        self.sent.append(request)
        return self.future


def test_delayed_discovery_over_three_seconds_is_accepted_without_commands():
    from prepare_cycle_gripper import wait_for_startup_services
    now = [0.0]
    clients = [DiscoveryClient('/real/robot/status', now, 3.253),
               DiscoveryClient('/fairino_remote_command_service', now, 4.0)]
    wait_for_startup_services(clients, clock=lambda: now[0])
    assert now[0] == 4.0
    assert all(not c.sent for c in clients)


def test_discovery_has_shared_deadline_and_names_missing_service():
    from prepare_cycle_gripper import wait_for_startup_services
    now = [0.0]
    clients = [DiscoveryClient('/real/robot/status', now, 12),
               DiscoveryClient('/fairino_remote_command_service', now, 20)]
    with pytest.raises(RuntimeError, match='/fairino_remote_command_service.*15s.*no request sent'):
        wait_for_startup_services(clients, clock=lambda: now[0])
    assert now[0] == 15
    assert all(not c.sent for c in clients)


def test_unavailable_service_does_not_mark_activation_or_send():
    from prepare_cycle_gripper import call_startup_service
    client = DiscoveryClient('/fairino_remote_command_service', [0.0], 20)
    markers = []
    with pytest.raises(RuntimeError, match='/fairino_remote_command_service.*no request sent'):
        call_startup_service(None, client, object(), lambda: markers.append(True))
    assert not markers and not client.sent


def test_response_timeout_marks_dispatch_once_and_never_retries(monkeypatch):
    from concurrent.futures import Future
    import prepare_cycle_gripper as module
    monkeypatch.setattr(module.rclpy, 'spin_until_future_complete', lambda *a, **kw: None)
    client = DiscoveryClient('/fairino_remote_command_service', [0.0], 0)
    client.future = Future()
    markers = []
    def mark():
        assert not client.sent
        markers.append(True)
    with pytest.raises(RuntimeError, match='response timeout.*fairino_remote_command_service.*outcome unknown'):
        module.call_startup_service(None, client, object(), mark)
    assert markers == [True] and len(client.sent) == 1


def test_successful_status_response_is_returned(monkeypatch):
    from concurrent.futures import Future
    import prepare_cycle_gripper as module
    monkeypatch.setattr(module.rclpy, 'spin_until_future_complete', lambda *a, **kw: None)
    client = DiscoveryClient('/real/robot/status', [0.0], 0)
    client.future = Future()
    expected = object()
    client.future.set_result(expected)
    assert module.call_startup_service(None, client, object()) is expected
    assert len(client.sent) == 1
