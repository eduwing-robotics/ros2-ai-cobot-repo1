import json
from uuid import uuid4
import pytest
from fr5_process_sequences.sequencer_robot_client import SequencerRobotClient
from test_real_backend import JOB


def rig():
    sent=[];controls=[]
    client=SequencerRobotClient(job_id=JOB,send_command=sent.append,send_pause=lambda x:None,send_control=controls.append)
    future=client.moveJoint('home',[0]*6)
    return client,future,sent,controls


def reply(request,kind,**data):
    return dict(job_id=JOB,operation_id=request['operation_id'],action='robot.move_joint',event=kind,
        message=json.dumps(dict(control_id=request['control_id'],control_sequence=request['control_sequence'],
            control_action=request['command'],**data)))


def test_complete_during_pause_does_not_advance_until_matching_resume():
    c,op,sent,controls=rig();pause=c.control('pause')
    c.on_event(dict(job_id=JOB,operation_id=sent[0]['operation_id'],action='robot.move_joint',event='OPERATION_COMPLETED'))
    assert op.done() and not pause.done()
    with pytest.raises(RuntimeError,match='blocks'):c.moveJoint('home',[0]*6)
    assert c.on_event(reply(controls[0],'PAUSE_CONFIRMED',stop_verified=True))
    resume=c.control('resume')
    assert c.on_event(reply(controls[-1],'RESUME_CONFIRMED',resume_applied=True))
    assert resume.done()
    c.moveJoint('home',[0]*6)
    assert len(sent)==2


def test_late_confirmation_after_timeout_never_unblocks():
    c,_,_,controls=rig();f=c.control('pause');cid=controls[0]['control_id']
    c._controls[cid]['deadline']=0;c.check_control_timeouts()
    with pytest.raises(TimeoutError):f.result()
    assert not c.on_event(reply(controls[0],'PAUSE_CONFIRMED',stop_verified=True))
    assert c._dispatch_blocked
    with pytest.raises(RuntimeError,match='confirmed'):c.control('resume')


def test_control_wait_registered_before_synchronous_response():
    c,_,_,_=rig()
    def send(command):c.on_event(reply(command,'PAUSE_CONFIRMED',stop_verified=True))
    c._send_control=send
    assert c.control('pause').done()


def test_wrong_control_identity_and_phase_do_not_complete_wait():
    c,op,_,controls=rig();f=c.control('pause')
    wrong=reply(controls[0],'PAUSE_CONFIRMED',stop_verified=True)
    wrong['operation_id']=str(uuid4())
    assert not c.on_event(wrong) and not f.done() and not op.done()
    assert not c.on_event(reply(controls[0],'RESUME_CONFIRMED',resume_applied=True))
    assert not f.done()
