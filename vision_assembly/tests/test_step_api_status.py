from pathlib import Path
from concurrent.futures import Future
from types import SimpleNamespace as NS
import ast
import json
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import step_api_transport as transport
import startup_service_client as rpc
from step_api_transport import StepApiSession


def healthy():
    return dict(api_capabilities_revision='step-cycle-20260908',hardware_execution_enabled=True,
        state_fresh=True,robot_health_clear=True,robot_motion_done=1,robot_mode=0,
        tool_num=1,work_num=0,gripper_feedback_valid=True,held_candidate=None)


def test_step_status_uses_actual_retry_transport(monkeypatch):
    first=Future();second=Future();second.set_result(NS(success=True,message=json.dumps(healthy())))
    futures=[first,second];sent=[];removed=[]
    client=NS(srv_name='/real/robot/status',wait_for_service=lambda **k:True,
        call_async=lambda request:(sent.append(request),futures[len(sent)-1])[1],
        remove_pending_request=lambda f:removed.append(f))
    monkeypatch.setattr(rpc.rclpy,'spin_until_future_complete',lambda *a,**k:None)
    session=object.__new__(StepApiSession);session.node=None;session.status_client=client
    assert session.status()==healthy()
    assert len(sent)==2 and removed==[first] and first.cancelled()


@pytest.mark.parametrize('fault',[{'robot_health_clear':False},{'robot_mode':1},
    {'held_candidate':{'part':'GPU'}},{'recovery_required':True},{'gripper_feedback_valid':False}])
def test_ready_preserves_safety_checks(monkeypatch,fault):
    session=object.__new__(StepApiSession);session.node=None
    session.spin_until=lambda *a,**k:None
    session.status=lambda:dict(healthy(),**fault)
    monkeypatch.setattr(transport,'cycle_checkpoint',lambda *a:None)
    with pytest.raises(RuntimeError,match='not ready'):session.ready()


def test_plan_ack_checks_execution_and_keeps_shared_deadline(monkeypatch):
    session=object.__new__(StepApiSession);session.node=None;session.job_id='current'
    session.spin_until=lambda *a,**k:None
    sent=[];session.targets=NS(publish=lambda msg:sent.append(msg))
    states=iter([dict(healthy(),vision_plan_sha256='hash',prepared_execution={'job_id':'other'}),
                 dict(healthy(),vision_plan_sha256='hash',prepared_execution={'job_id':'current'})])
    deadlines=[]
    def status(**kw):deadlines.append(kw['deadline']);return next(states)
    session.status=status
    monkeypatch.setattr(transport,'cycle_checkpoint',lambda *a:None)
    monkeypatch.setattr(transport.rclpy,'spin_once',lambda *a,**k:None)
    session.publish_targets({'job_id':'current','plan_sha256':'hash'})
    assert len(sent)==1 and len(deadlines)==2 and deadlines[0]==deadlines[1]
    with pytest.raises(ValueError):session.publish_targets({'job_id':'other','plan_sha256':'hash'})
    assert len(sent)==1


def test_all_production_status_clients_use_shared_readonly_transport():
    root=Path(__file__).resolve().parents[2]
    covered=[]
    for folder in ['vision_assembly/scripts','scripts','calibration']:
        for path in (root/folder).rglob('*.py'):
            if 'tests' in path.parts:continue
            tree=ast.parse(path.read_text());clients=[]
            for item in ast.walk(tree):
                if not isinstance(item,ast.Assign) or not isinstance(item.value,ast.Call):continue
                call=item.value
                if (isinstance(call.func,ast.Attribute) and call.func.attr=='create_client'
                    and len(call.args)>1 and isinstance(call.args[1],ast.Constant)
                    and call.args[1].value in ('/real/robot/status','/real/assembly/status')):
                    clients.extend(ast.unparse(t) for t in item.targets)
            if not clients:continue
            covered.append(path.name)
            assert 'call_readonly_service' in path.read_text(), path
            for item in ast.walk(tree):
                if isinstance(item,ast.Call) and isinstance(item.func,ast.Attribute):
                    assert not (item.func.attr=='call_async' and ast.unparse(item.func.value) in clients),path
    assert set(covered)=={'prepare_cycle_gripper.py','check_step_api.py','step_api_transport.py','assembly_api_client.py'}
