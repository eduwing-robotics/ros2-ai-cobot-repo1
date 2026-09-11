from concurrent.futures import Future
from pathlib import Path
import sys
import pytest
from std_srvs.srv import Trigger
from fairino_msgs.srv import RemoteCmdInterface
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import startup_service_client as rpc

class Client:
    srv_name='/real/robot/status'
    def __init__(self,futures):self.futures=futures;self.sent=[];self.removed=[]
    def wait_for_service(self,timeout_sec):return True
    def call_async(self,request):
        self.sent.append(request);return self.futures[len(self.sent)-1]
    def remove_pending_request(self,f):self.removed.append(f)

def ready(value):
    f=Future();f.set_result(value);return f

def test_only_readonly_timeout_is_retried_and_late_response_is_discarded(monkeypatch):
    monkeypatch.setattr(rpc.rclpy,'spin_until_future_complete',lambda *a,**k:None)
    lost=Future();response=Trigger.Response(success=True,message='ok')
    c=Client([lost,ready(response)])
    assert rpc.call_readonly_service(None,c,Trigger.Request()) is response
    assert len(c.sent)==2 and c.removed==[lost] and lost.cancelled()

def test_readonly_retries_are_bounded(monkeypatch):
    monkeypatch.setattr(rpc.rclpy,'spin_until_future_complete',lambda *a,**k:None)
    c=Client([Future(),Future(),Future()])
    with pytest.raises(rpc.StartupServiceError):rpc.call_readonly_service(None,c,Trigger.Request())
    assert len(c.sent)==3 and len(c.removed)==3

def test_semantic_status_failure_is_not_retried(monkeypatch):
    monkeypatch.setattr(rpc.rclpy,'spin_until_future_complete',lambda *a,**k:None)
    response=Trigger.Response(success=False,message='fault')
    c=Client([ready(response)])
    assert rpc.call_readonly_service(None,c,Trigger.Request()) is response
    assert len(c.sent)==1

@pytest.mark.parametrize('command',['ActGripper(1,1)','MoveJ(1)','StopMotion'])
def test_actuator_commands_never_enter_retry_policy(command):
    c=Client([]);c.srv_name='/fairino_remote_command_service'
    with pytest.raises(ValueError):
        rpc.call_readonly_service(None,c,RemoteCmdInterface.Request(cmd_str=command))
    assert not c.sent

def test_expired_budget_never_sends():
    c=Client([])
    with pytest.raises(rpc.StartupServiceError):
        rpc.call_readonly_service(None,c,Trigger.Request(),deadline=0)
    assert not c.sent
