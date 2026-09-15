from concurrent.futures import Future
from types import SimpleNamespace as NS
import threading
from uuid import uuid4
import pytest

from test_assembly_cycle_api import controller
from test_assembly_execution import complete_evidence
from fr5_process_sequences.assembly_cycle_api import SLOTS
from fr5_process_sequences.assembly_execution import AssemblyExecutionContract,SCHEMA
from fr5_process_sequences.assembly_execution_control import AssemblyExecutionControl

client_module=pytest.importorskip('assembly_sequencer.assembly_execution_client')


def test_sequencer_robot_start_pause_resume_complete_same_unit(controller,tmp_path):
    c,process,launches=controller;c.allow_batch_start=False;c.allow_production_start=True
    binding=dict(product_id='product',production_recipe_version='r1',robot_recipe_revision='reviewed',
                 expected_slots=list(SLOTS['full']))
    server=AssemblyExecutionContract(c,[binding],clock=lambda:1000.)
    moves=[]
    state=NS(robot_motion_done=1,gripper_feedback_valid=True,gripperfaultnum=0,grippererro=0,
        grip_motion_done=2,gripper_position=17.,**{'cart_'+a+'_cur_pos':0. for a in 'xyzabc'})
    robot=NS(_fresh_state=lambda:state,_assert_health=lambda _:None,pause_motion=lambda:moves.append('pause'),
        observe_stopped=lambda:'fresh_feedback_verified_stopped',
        resume_motion=lambda:moves.append('resume') or 'fresh_feedback_resume_applied')
    backend=NS(_robot=robot,_active=None,_paused=threading.Event(),_recovery_required=False,
               held_part=None,control=NS(checks={}),continuous_transfer_enabled=True)
    server.control=AssemblyExecutionControl(c,backend,enabled=True,buffered_verified=True)
    sent=[]
    def send(request):
        sent.append(request)
        client.on_event(server.command(request))
    client=client_module.AssemblyExecutionClient(send,Future,tmp_path/'client',SLOTS['full'])
    c.publish=lambda payload:client.on_event(server.snapshot(payload["operation_id"])
        if payload.get("execution_context") else payload)
    job=str(uuid4());identity=client_module.execution_id(job,22)
    request=dict(schema=SCHEMA,action='assembly.start',execution_id=identity,production_job_id=job,
        unit_id=22,product_id='product',production_recipe_version='r1',robot_recipe_revision='reviewed',
        scene_confirmation=dict(operator_id='operator',execution_id=identity,confirmed_unix=990.,
            scope='empty_gripper_empty_pcb_full_tray_fixed_fixture'))
    result=client.start(request)
    assert not result.done() and len(launches)==1
    paused=client.control(identity,True);assert not paused.done()
    server.control._apply(sent[-1]);assert paused.result(timeout=1)['stop_verified']
    resumed=client.control(identity,False);assert not resumed.done()
    server.control._apply(sent[-1]);assert resumed.result(timeout=1)['resume_applied']
    complete_evidence(server);process.code=0;c._monitor()
    assert result.result(timeout=1)['execution_id']==identity
    assert result.result(timeout=1)['inspection_pass'] is None
    assert len(launches)==1 and moves==['pause','resume'] and process.signals==[]
    assert client.start(request).result(timeout=1)==result.result(timeout=1)
    assert sum(r['action']=='assembly.start' for r in sent)==1
