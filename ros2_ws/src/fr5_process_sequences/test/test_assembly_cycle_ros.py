import json
from types import SimpleNamespace as NS
from uuid import uuid4
from std_msgs.msg import String
from fr5_process_sequences.assembly_cycle_ros import AssemblyCycleRosBridge
from fr5_process_sequences.assembly_execution import SCHEMA


def test_ros_bridge_versions_queries_without_enabling_hardware(tmp_path):
    config=tmp_path/'vision_assembly/config';config.mkdir(parents=True)
    (config/'assembly_launcher_revision.json').write_text(json.dumps({'revision':'test'}))
    messages=[];subscriptions={};services={}
    ghost=NS(snapshot=lambda:None)
    node=NS(_backend=NS(_ghost=ghost,event_context=NS(snapshot=lambda:dict(attachments=[]))),_vision_port=NS(_payload={}),
        _robot_port=NS(_enabled=False),get_parameter=lambda name:NS(value=False),
        create_publisher=lambda *a:NS(publish=lambda message:messages.append(json.loads(message.data))),
        create_subscription=lambda kind,topic,callback,depth:subscriptions.update({topic:callback}),
        create_service=lambda kind,topic,callback:services.update({topic:callback}),
        create_timer=lambda *a:None)
    node._backend._robot=node._robot_port
    bridge=AssemblyCycleRosBridge(node,tmp_path)
    try:
        subscriptions['/real/assembly/command'](String(data=json.dumps(dict(
            schema=SCHEMA,action='assembly.status',execution_id=str(uuid4())))))
        assert messages[-1]['schema']==SCHEMA and messages[-1]['status']=='not_found'
        response=services['/real/assembly/status'](None,NS())
        payload=json.loads(response.message)
        assert payload['schema']=='fr5.assembly_cycle/v1'
        assert payload['production_contract']['schema']==SCHEMA
        assert payload['production_contract']['capabilities']['start'] is False
        assert payload['hardware_execution_enabled'] is False
        assert bridge.controller.process is None
    finally:
        bridge.instance_lock.close()


import pytest
from fr5_process_sequences.real_backend import BackendFailure


@pytest.mark.parametrize('valid,fault,error', [(False,1,0),(True,1,0),(True,0,1)])
def test_start_readiness_rejects_invalid_gripper(valid, fault, error):
    state=NS(gripper_feedback_valid=valid,gripperfaultnum=fault,grippererro=error)
    bridge=object.__new__(AssemblyCycleRosBridge)
    bridge.node=NS(_backend=NS(held_part=None),
        _robot_port=NS(assert_ready=lambda:None,_fresh_state=lambda:state))
    with pytest.raises(BackendFailure, match='gripper'):
        bridge.ready()


@pytest.mark.parametrize('valid', [False, True])
def test_start_readiness_accepts_gripper_for_worker_initialization(valid):
    state=NS(gripper_feedback_valid=valid,gripperfaultnum=0,grippererro=0)
    bridge=object.__new__(AssemblyCycleRosBridge)
    bridge.node=NS(_backend=NS(held_part=None),
        _robot_port=NS(assert_ready=lambda:None,_fresh_state=lambda:state))
    bridge.ready()
