import json
from uuid import uuid4
import pytest
from fr5_process_sequences.real_preview import JointGhostPreview
from fr5_process_sequences.real_ros_node import FairinoRobotPort
from fr5_process_sequences.real_backend import BackendFailure
from fr5_process_sequences.real_ghost import RealGhostTargetPublisher
from test_real_ros_node import FakeNode
from test_real_ghost import FakeNode as GhostNode


def request():
    return dict(job_id=str(uuid4()),operation_id=str(uuid4()),action='robot.move_joint',
                point_name='home',joint_point=[-4.689,-86.951,84.467,-87.516,-90.,-4.688])


def preview():
    port=FairinoRobotPort(FakeNode(),enabled=False,state_topic='/state',command_service='/cmd',
                         travel_speed_percent=25,vertical_speed_percent=10)
    calls=[]
    def service(command, code):
        calls.append(command)
        assert command=='GetJointSoftLimitDeg(1)', 'preview attempted a non-read-only command'
        return '0,'+','.join(map(str,[-180]*6+[180]*6))
    port._service=service
    node=GhostNode()
    handler=JointGhostPreview(validate_joint_target=port.validate_joint_target,
                             ghost=RealGhostTargetPublisher(node,backend='real'))
    return handler,port,calls,node


def test_disarmed_preview_emits_both_ghost_messages_and_no_motion_commands():
    handler,port,calls,node=preview()
    result=handler.execute(request())
    assert result['event']=='PREVIEW_PUBLISHED' and result['preview_only']
    assert not result['robot_motion_authorized'] and not port._enabled
    assert calls==['GetJointSoftLimitDeg(1)']
    assert len(node.publisher.messages)==2
    assert json.loads(node.publisher.messages[0].data)['preview_only'] is True
    assert len(node.publisher.messages[1].position)==6
    with pytest.raises(BackendFailure,match='not armed'):port.assert_ready()


@pytest.mark.parametrize('value',[[0]*5,[0,0,0,0,0,179],[0,0,0,0,0,float('nan')]])
def test_invalid_or_limit_target_emits_no_ghost(value):
    handler,port,calls,node=preview();data=request();data['joint_point']=value
    assert handler.execute(data)['event']=='PREVIEW_FAILED'
    assert not node.publisher.messages


def test_duplicate_replays_result_without_publishing_again_and_conflict_rejects():
    handler,port,calls,node=preview();data=request()
    result=handler.execute(data)
    assert handler.execute(json.dumps(data))==result
    assert len(node.publisher.messages)==2 and len(calls)==1
    data['joint_point'][0]+=1
    assert handler.execute(data)['error_code']=='INVALID_REQUEST'
    assert len(node.publisher.messages)==2


def test_bad_action_and_nonobject_do_not_call_controller():
    handler,port,calls,node=preview();data=request();data['action']='robot.pick'
    assert handler.execute(data)['event']=='PREVIEW_FAILED'
    assert handler.execute('[]')['event']=='PREVIEW_FAILED'
    assert not calls and not node.publisher.messages


def test_publisher_failure_is_not_reported_as_success():
    handler,port,calls,node=preview();node.publisher.fail=True
    assert handler.execute(request())['event']=='PREVIEW_FAILED'
