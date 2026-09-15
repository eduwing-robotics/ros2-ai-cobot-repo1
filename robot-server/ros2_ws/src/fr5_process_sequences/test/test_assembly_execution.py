import copy
from uuid import uuid4
import pytest

from test_assembly_cycle_api import controller
from fr5_process_sequences.assembly_cycle_api import SLOTS
from fr5_process_sequences.assembly_execution import AssemblyExecutionContract, SCHEMA
from fr5_process_sequences.real_backend import BackendFailure


@pytest.fixture
def production(controller):
    c,p,calls=controller
    c.allow_batch_start=False;c.allow_production_start=True
    binding=dict(product_id='fixture-test',production_recipe_version='test-r1',
                 robot_recipe_revision='reviewed',expected_slots=list(SLOTS['full']))
    contract=AssemblyExecutionContract(c,[binding],clock=lambda:1000.)
    execution_id=str(uuid4())
    request=dict(schema=SCHEMA,action='assembly.start',execution_id=execution_id,
        production_job_id='job-test',unit_id=1,product_id='fixture-test',
        production_recipe_version='test-r1',robot_recipe_revision='reviewed',
        scene_confirmation=dict(operator_id='test-operator',execution_id=execution_id,
            confirmed_unix=990.,scope='empty_gripper_empty_pcb_full_tray_fixed_fixture'))
    return contract,request,p,calls


def test_one_unit_retransmission_persists_identity_without_relaunch(production):
    contract,data,p,calls=production
    first=contract.command(data)
    assert first['execution_id']==data['execution_id'] and first['status']=='running'
    assert first['execution_kind']=='production' and first['unit_id']==1
    assert len(calls)==1 and '--execute' in calls[0][0][0]
    contract.clock=lambda:5000.
    assert contract.command(data)['execution_id']==data['execution_id']
    assert len(calls)==1
    with pytest.raises(BackendFailure,match='different content'):
        contract.command(dict(data,unit_id=2))
    assert len(calls)==1


@pytest.mark.parametrize('change',[{'unit_id':True},{'unit_id':0},{'tcp':[0]*6},
    {'production_recipe_version':'unknown'},{'scene_confirmation':True}])
def test_reject_invalid_start_without_dispatch(production,change):
    contract,data,p,calls=production
    with pytest.raises((BackendFailure,ValueError)):
        contract.command(dict(data,**change))
    assert not calls


def test_expired_confirmation_and_mismatched_unit_are_rejected(production):
    contract,data,p,calls=production
    for change in ({'confirmed_unix':0.},{'execution_id':str(uuid4())}):
        request=copy.deepcopy(data);request['scene_confirmation'].update(change)
        with pytest.raises(ValueError):contract.command(request)
    assert not calls


def test_diagnostic_status_is_not_production_completion(production):
    contract,data,p,calls=production
    contract.controller.state=dict(status='check_completed')
    result=contract.command(dict(schema=SCHEMA,action='assembly.status'))
    assert result['status']=='idle' and result['execution_id'] is None
    assert result['inspection_pass'] is None
    assert not calls


def test_query_unknown_does_not_start_or_change_state(production):
    contract,data,p,calls=production
    before=copy.deepcopy(contract.controller.state)
    result=contract.command(dict(schema=SCHEMA,action='assembly.status',execution_id=str(uuid4())))
    assert result['status']=='not_found' and contract.controller.state==before and not calls


def test_pause_resume_explicitly_unsupported_no_cancel(production):
    contract,data,p,calls=production;contract.command(data)
    for action in ('assembly.pause','assembly.resume'):
        with pytest.raises(BackendFailure,match='not commissioned'):
            contract.command(dict(schema=SCHEMA,action=action,execution_id=data['execution_id']))
    assert not p.signals and len(calls)==1 and not contract.capabilities()['resume']


def test_production_opt_in_does_not_enable_legacy_start(production):
    contract,data,p,calls=production
    from test_assembly_cycle_api import request
    with pytest.raises(BackendFailure):contract.controller.command(request())
    assert not calls


def test_restart_retains_execution_and_never_replays(production):
    contract,data,p,calls=production;contract.command(data)
    from fr5_process_sequences.assembly_cycle_api import AssemblyCycleController
    recovered=AssemblyCycleController(contract.controller.root,lambda:None,lambda _:None,
        contract.controller.popen,allow_batch_start=False)
    new=AssemblyExecutionContract(recovered,contract.bindings)
    assert new.command(data)['status']=='recovery_required' and len(calls)==1


def complete_evidence(contract):
    import hashlib,json,time
    c=contract.controller;directory=c.root/'runtime/assembly_cycles'/c.state['operation_id']
    directory.mkdir(parents=True);(directory/'after').mkdir()
    def write(name,value):(directory/name).write_text(json.dumps(value))
    write('cycle.json',dict(status='motion_complete_awaiting_physical_verification',steps=[]))
    for phase,slots in [('non-smd',SLOTS['full'][:-5]),('smd',SLOTS['SMD'])]:
        write(phase+'_plan.json',{'test_plan':phase})
        digest=hashlib.sha256((directory/(phase+'_plan.json')).read_bytes()).hexdigest()
        write(phase+'_run.json',dict(job_id=c.state['operation_id'],plan_sha256=digest,
            selected_slots=slots,motion_completed_slots=slots,part_held_candidate=False,
            status='motion_complete_awaiting_physical_verification'))
    write('after/PlaceCamera_camera_stage.json',dict(status='captured',execution_backend='single_step_api',
        finished_unix=time.time(),target=[0]*6))
    write('api_release_check.json',dict(returncode=0,stdout=json.dumps(dict(
        state_fresh=True,robot_health_clear=True,robot_motion_done=1,gripper_feedback_valid=True,
        active_operation=None,held_candidate=None,recovery_required=False,observed_unix=time.time()))))
    c.attachment_snapshot=lambda:dict(attachments=[dict(job_id=c.state['operation_id'],
        slot_code=slot,state='placed',uncertain=False,attachment_binding_valid=True) for slot in SLOTS['full']])
    return directory


def test_production_completion_requires_all_evidence_and_is_not_pass(production):
    contract,data,p,calls=production;contract.command(data);complete_evidence(contract)
    p.code=0;contract.controller._monitor()
    result=contract.snapshot(data['execution_id'])
    assert result['event']=='EXECUTION_COMPLETED' and result['stop_verified']
    assert result['plan_complete'] and result['inspection_pass'] is None
    assert result['physical_placement_verified'] is False


@pytest.mark.parametrize('missing',['api_release_check.json','after/PlaceCamera_camera_stage.json','smd_plan.json'])
def test_slot_count_and_exit_zero_are_not_enough(production,missing):
    contract,data,p,calls=production;contract.command(data);directory=complete_evidence(contract)
    (directory/missing).unlink();p.code=0;contract.controller._monitor()
    result=contract.snapshot(data['execution_id'])
    assert result['status']=='recovery_required' and not result['stop_verified']


def test_frozen_plan_change_cannot_complete(production):
    contract,data,p,calls=production;contract.command(data);directory=complete_evidence(contract)
    c=contract.controller;c.state.update(c._progress());c._save()
    (directory/'smd_plan.json').write_text('{}');p.code=0;c._monitor()
    assert c.state['status']=='recovery_required'
    assert 'plan changed' in c.state['evidence_error']


def test_unresolved_production_blocks_individual_guard_without_lease(production):
    contract,data,p,calls=production;contract.command(data)
    from fr5_process_sequences.assembly_cycle_api import robot_execution_guard
    with pytest.raises(BackendFailure,match='unresolved production'):
        with robot_execution_guard(contract.controller.root):
            pytest.fail('guard must not yield')


def test_robot_event_replay_and_foreign_identity_cannot_replace_snapshot(production):
    import json
    contract,data,p,calls=production;contract.command(data)
    snapshot=dict(server_instance_id='epoch',attachments=[])
    metadata=dict(server_instance_id='epoch',event_sequence=2,slot_code='CAP-01')
    event=dict(job_id=data['execution_id'],operation_id=str(uuid4()),event='PHASE_COMPLETED',
               phase='GRASP',message=json.dumps(metadata))
    result=contract.observe_robot_event(event,snapshot)
    assert result['event']=='ROBOT_EVENT' and result['robot_event_kind']=='PHASE_COMPLETED'
    assert result['stage_id']=='GRASP'
    previous=copy.deepcopy(contract.controller.state)
    assert contract.observe_robot_event(event,snapshot) is None
    foreign=dict(event,job_id=str(uuid4()))
    assert contract.observe_robot_event(foreign,snapshot) is None
    assert contract.controller.state==previous


def test_missing_visual_event_does_not_lose_authoritative_final_attachments(production):
    contract,data,p,calls=production;contract.command(data);complete_evidence(contract)
    assert 'attachments' not in contract.controller.state
    p.code=0;contract.controller._monitor()
    result=contract.snapshot(data['execution_id'])
    assert result['event']=='EXECUTION_COMPLETED' and len(result['attachments'])==25


def test_uncertain_final_bindings_do_not_claim_complete(production):
    contract,data,p,calls=production;contract.command(data);complete_evidence(contract)
    contract.controller.attachment_snapshot=lambda:dict(attachments=[])
    p.code=0;contract.controller._monitor()
    assert contract.snapshot(data['execution_id'])['status']=='recovery_required'


def test_failure_callback_and_replay_include_actual_preflight_reason(production):
    import json
    contract,data,p,calls=production
    contract.command(data)
    c=contract.controller
    directory=c.root/'runtime/assembly_cycles'/data['execution_id']
    directory.mkdir(parents=True)
    (directory/'cycle.json').write_text(json.dumps(dict(status='stopped_on_error',
        steps=[dict(name='preflight_non-smd',status='failed')],error='wrapper exit 1')))
    reason='motion plan rejected: joint waypoint 44 changes J1 by 95.163 deg; maximum is 95.000 deg'
    (directory/'preflight_non-smd.log').write_text('Traceback (most recent call last):\nRuntimeError: '+reason+'\n')
    published=[];c.publish=lambda local:published.append(contract.snapshot(local['operation_id']))
    p.code=1;c._monitor()
    for response in (published[-1],contract.command(data),contract.snapshot(data['execution_id'])):
        assert response['event']=='EXECUTION_FAILED'
        assert response['error_code']=='MOTION_PLAN_REJECTED'
        assert response['error_message']==reason
        assert response['failed_stage']=='preflight_non-smd'
        assert response['failure']['returncode']==1
        assert response['failure']['log_path'].endswith('/preflight_non-smd.log')
    assert len(calls)==1
    # A retained failure remains useful even after logs become unavailable.
    (directory/'preflight_non-smd.log').unlink()
    assert contract.snapshot(data['execution_id'])['error_message']==reason


def test_historical_failure_enrichment_is_read_only(production):
    import json
    contract,data,p,calls=production;contract.command(data)
    c=contract.controller;p.code=1;c._monitor()
    c.state.pop('failure',None);c._save()
    path=c.directory/(data['execution_id']+'.json');before=path.read_bytes()
    log=c.directory/(data['execution_id']+'.log')
    log.write_text('x'*20000+'\nRuntimeError: '+'z'*4000+'\n')
    response=contract.command(data)
    assert response['replayed'] is True
    assert response['failed_stage']=='startup'
    assert len(response['error_message'])==2048
    assert path.read_bytes()==before


def test_failure_without_log_still_has_diagnostic_fields(production):
    contract,data,p,calls=production;contract.command(data)
    p.code=1;contract.controller._monitor()
    response=contract.snapshot(data['execution_id'])
    assert response['error_code']=='EXECUTION_PROCESS_FAILED'
    assert response['error_message']
    assert response['failure']['returncode']==1


def test_reconciled_failure_retains_error_and_allows_only_new_execution(production):
    contract,data,p,calls=production;contract.command(data)
    p.code=1;contract.controller._monitor()
    c=contract.controller
    original_error=contract.snapshot(data['execution_id'])['error_message']
    c.state.update(status='failed_recovered',recovery=dict(reason='reviewed_camera_only_preflight_failure'),stop_verified=True)
    c._save()
    replay=contract.command(data)
    assert replay['event']=='EXECUTION_FAILED' and replay['replayed'] is True
    assert replay['recovery_required'] is False and replay['retry_requires_new_execution_id'] is True
    assert replay['error_message']==original_error and replay['stop_verified'] is True
    assert replay['recovery']['reason']=='reviewed_camera_only_preflight_failure'
    assert len(calls)==1
    new=copy.deepcopy(data);new['execution_id']=str(uuid4())
    new['scene_confirmation']['execution_id']=new['execution_id']
    assert contract.command(new)['replayed'] is False
    assert len(calls)==2
