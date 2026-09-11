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
