"""End-to-end sequencer/precision backend tests with no physical I/O."""
import fcntl
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4
from copy import deepcopy

import pytest
from fr5_process_sequences.real_contract import Event
from fr5_process_sequences.real_backend import BackendFailure
from fr5_process_sequences.assembly_cycle_api import robot_execution_guard
from fr5_process_sequences.sequencer_robot_client import SequencerRobotClient
from fr5_process_sequences.real_precision_steps import digest
from test_real_precision_steps import plan, setup_real, ROOT
sys.path.insert(0,str(ROOT/'vision_assembly/scripts'))
from assembly_cycle_launcher import api_workflow, frozen_api_recipe, NON_SMD, SMD
from execute_cycle_steps_api import execute_phase


def test_launcher_only_uses_api_for_assembly_and_retains_fresh_smd_stage(tmp_path):
    steps=dict(api_workflow(tmp_path))
    for key in ('assemble_non-smd','assemble_smd'):
        assert Path(steps[key][1]).name=='execute_cycle_steps_api.py'
        assert 'execute_full_fixed_cycle.py' not in ' '.join(steps[key])
    assert list(steps).index('assemble_non-smd')<list(steps).index('capture_smd_view')<list(steps).index('assemble_smd')
    assert list(steps)[-1]=='after_photo'
    recipe=frozen_api_recipe()
    assert [s['slot_code'] for s in recipe['steps']]==NON_SMD+SMD
    assert recipe['workflow']['per_step']==[{'robot.pick':'current_part'},{'robot.place':'current_slot'}]
    assert not recipe['workflow']['after_all']


def test_lease_allows_only_live_owner_and_keeps_lock(tmp_path):
    directory=tmp_path/'runtime/assembly_cycles';directory.mkdir(parents=True)
    stream=(directory/'launcher.lock').open('a');fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
    job=str(uuid4())
    lease=dict(job_id=job,pid=os.getpid(),process_start=Path(f'/proc/{os.getpid()}/stat').read_text().split()[21])
    (directory/'step_api_owner.json').write_text(json.dumps(lease))
    with pytest.raises(BackendFailure):
        with robot_execution_guard(tmp_path,job_id=str(uuid4())):pass
    with robot_execution_guard(tmp_path,job_id=job):
        with pytest.raises(BackendFailure):
            with robot_execution_guard(tmp_path,job_id=job):pass
    stream.close()
    lease['process_start']='wrong';(directory/'step_api_owner.json').write_text(json.dumps(lease))
    with pytest.raises(BackendFailure):
        with robot_execution_guard(tmp_path,job_id=job):pass


def split_plan(plan,phase):
    result=deepcopy(plan)
    result['plan']=[i for i in result['plan'] if i['slot_code'].startswith('CAP-')==(phase=='smd')]
    result['plan_selection']=dict(mode=phase,requested_only_slot=None,selected_slots=[i['slot_code'] for i in result['plan']])
    return result


def populate(payload,plan,recipe):
    payload['precision_plan']=plan;payload['plan_sha256']=digest(plan)
    payload['parts']=[];payload['tray_inspection_reference']['bindings']=[]
    for item in plan['plan']:
        step=next(s for s in recipe['steps'] if s['slot_code']==item['slot_code'])
        payload['parts'].append(dict(job_id=payload['job_id'],**step,source_index=item['tray_instance_index'],
            expected_gripper=recipe['gripper']['parts'][step['part_id']],
            gripper_profiles={p:dict(velocity_percent=20,force_percent=1) for p in ('PREOPEN','GRASP','RELEASE')}))
        payload['tray_inspection_reference']['bindings'].append(dict(part_type=item['part_type'],physical_index=item['tray_instance_index'],reference_center_pixel=[10,20]))


@pytest.mark.parametrize('fail_slot',[None,'GPU-01','HBM-08','CAP-03'])
def test_all25_individual_api_calls_or_stop_at_first_failure(tmp_path,plan,monkeypatch,fail_slot):
    non=split_plan(plan,'non-smd');smd=split_plan(plan,'smd');recipe=frozen_api_recipe()
    real,robot,executor,payload,_,_,events=setup_real(tmp_path,non,monkeypatch,'GPU-01')
    requests=[]
    def send(command):
        requests.append(command)
        client.on_event(real.execute(command).to_dict())
    client=SequencerRobotClient(job_id=payload['job_id'],recipe=recipe,send_command=send,send_pause=lambda _:None)
    session=SimpleNamespace(client=client,call=lambda method,*args:method(*args).result())
    def removal(*args,**kwargs):
        if kwargs['picked_slot']==fail_slot:raise RuntimeError('picked cell still occupied')
        return {'evidence':'picked_cell_absent_not_physical_holding_proof','distinct_consecutive_frames':3}
    monkeypatch.setattr('tray_home_gate.wait_inventory',removal)
    completed=[]
    try:
        for phase,current,slots in [('non-smd',non,NON_SMD),('smd',smd,SMD)]:
            populate(payload,current,recipe)
            record=dict(motion_completed_slots=[],selected_slots=slots)
            execute_phase(session,[s for s in recipe['steps'] if s['slot_code'] in slots],record,tmp_path/(phase+'.json'))
            completed.extend(record['motion_completed_slots'])
    except Exception:
        if fail_slot is None:raise
    if fail_slot is None:
        assert completed==NON_SMD+SMD
        assert len(requests)==50
        assert [r['action'] for r in requests]==['robot.pick','robot.place']*25
        assert real.held_part is None
    else:
        assert requests[-1]['slot_code']==fail_slot and requests[-1]['action']=='robot.pick'
        assert all(r['slot_code'] in (NON_SMD+SMD)[:(NON_SMD+SMD).index(fail_slot)+1] for r in requests)
        assert real._recovery_required


@pytest.mark.parametrize('name',['PlaceCamera','TrayHome','SMDView'])
def test_camera_api_uses_existing_safe_route_and_no_gripper(tmp_path,plan,monkeypatch,name):
    from test_real_precision_steps import SimExecutor
    from tray_home_gate import HOME
    real,robot,executor,payload,_,_,events=setup_real(tmp_path,plan,monkeypatch)
    base=ROOT/'vision_assembly/checkpoints/full_cycle_success_20260906/runtime.json'
    destination=tmp_path/'vision_assembly/checkpoints/full_cycle_success_20260906/runtime.json'
    destination.parent.mkdir(parents=True);destination.write_bytes(base.read_bytes())
    (tmp_path/'vision_assembly/config/smd_section_view.json').write_bytes((ROOT/'vision_assembly/config/smd_section_view.json').read_bytes())
    baseline=json.loads(base.read_text())
    class CameraExecutor(SimExecutor):
        def service(self,command,**kwargs):
            if command.startswith('GetTCPOffset'):return '0,'+','.join(map(str,baseline['active_tcp_offset']))
            if command.startswith('GetRobotTeachingPoint'):
                return '0,'+','.join(map(str,baseline['teaching_points'][name]))
            return super().service(command,**kwargs)
    executor.executor_factory=CameraExecutor
    request=dict(job_id=payload['job_id'],operation_id=str(uuid4()),action='robot.move_joint',point_name=name,joint_point=[0]*6)
    result=real.execute(request)
    assert result.event is Event.OPERATION_COMPLETED,result
    assert not [r for r in robot.log if r[0]=='gripper']
    phases=[r[2] for r in robot.log if r[0]=='arm']
    assert phases and any('combined_xy_abc' in phase for phase in phases)
