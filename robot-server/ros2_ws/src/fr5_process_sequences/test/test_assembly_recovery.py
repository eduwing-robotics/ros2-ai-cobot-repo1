import copy
import fcntl
import time
from uuid import uuid4
import pytest
from test_assembly_cycle_api import controller, request
from fr5_process_sequences.assembly_cycle_api import AssemblyCycleController, SCHEMA
from fr5_process_sequences.assembly_execution import AssemblyExecutionContract, SCHEMA as PRODUCTION
from fr5_process_sequences.real_backend import BackendFailure


def ended(controller, status='recovery_required'):
    c, p, calls = controller
    data = request(); c.command(data); p.code = 1
    c.state.update(status=status, finished_unix=time.time(), failure={'code':'TEST_FAILURE','message':'preserved'})
    c._save()
    confirmation = dict(operator_id='test-operator', execution_id=data['operation_id'],
        confirmed_unix=time.time(), scope='empty_gripper_empty_pcb_full_tray_fixed_fixture')
    return c, p, calls, data, confirmation


def test_recover_preserves_failure_replay_and_enables_new_execution(controller):
    c, p, calls, data, confirmation = ended(controller)
    response = c.command(dict(schema=SCHEMA, action='assembly.recover',
        operation_id=data['operation_id'], scene_confirmation=confirmation))
    assert response['recovery_applied'] and not response['recovery_required']
    assert response['status'] == 'failed_recovered'
    assert response['failure']['message'] == 'preserved'
    assert not response['physical_placement_verified']
    assert len(calls) == 1 and not p.signals
    assert c.command(data)['status'] == 'failed_recovered'
    restored = AssemblyCycleController(c.root, lambda:None, lambda _:None, c.popen)
    assert restored.state['status'] == 'failed_recovered'
    restored.command(request()); assert len(calls) == 2


@pytest.mark.parametrize('status', ['motion_complete_awaiting_physical_verification','failed_before_motion','failed_recovered','check_failed','check_completed'])
def test_terminal_result_retained(controller, status):
    c,p,calls,data,confirmation=ended(controller,status)
    assert c.recover(data['operation_id'],confirmation)['status'] == status
    assert len(calls)==1


@pytest.mark.parametrize('condition', ['active','worker','lease','lock','robot','other','wrong_id','stale','false_scope'])
def test_recovery_refuses_unresolved_conditions_without_mutating(controller, condition):
    c,p,calls,data,confirmation=ended(controller)
    runtime=c.root/'runtime/assembly_cycles';lock=None
    if condition=='active':c.state['status']='running'
    if condition=='worker':p.code=None
    if condition=='lease':(runtime/'step_api_owner.json').write_text('{}')
    if condition=='lock':
        lock=(runtime/'step_operation.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if condition=='robot':
        def fail():raise BackendFailure('GRIPPER_FAILED','held part')
        c.recovery_ready=fail
    if condition=='other':
        import json
        (c.directory/(str(uuid4())+'.json')).write_text(json.dumps({'operation_id':str(uuid4()),'status':'recovery_required'}))
    if condition=='wrong_id':data['operation_id']=str(uuid4());confirmation['execution_id']=data['operation_id']
    if condition=='stale':confirmation['confirmed_unix']-=121
    if condition=='false_scope':confirmation['scope']='anything'
    before=copy.deepcopy(c.state)
    try:
        with pytest.raises((ValueError,BackendFailure)):c.recover(data['operation_id'],confirmation)
    finally:
        if lock:lock.close()
    assert c.state==before and len(calls)==1 and not p.signals


def test_production_routes_same_recovery(controller):
    c,p,calls,data,confirmation=ended(controller)
    contract=AssemblyExecutionContract(c)
    # Routing is common even for a prior locally started cycle.
    result=contract.command(dict(schema=PRODUCTION,action='assembly.recover',
        execution_id=data['operation_id'],scene_confirmation=confirmation))
    assert result['recovery_applied'] and result['retry_requires_new_execution_id']
    assert c.state['status']=='failed_recovered' and len(calls)==1
