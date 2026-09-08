import json
from contextlib import contextmanager
from uuid import uuid4
import pytest
from fr5_process_sequences.assembly_cycle_api import AssemblyCycleController, robot_execution_guard, SCHEMA
from fr5_process_sequences.real_backend import BackendFailure
from test_real_backend import backend, pick


class Process:
    pid=12345
    def __init__(self):self.code=None;self.signals=[]
    def poll(self):return self.code
    def send_signal(self, signum):self.signals.append(signum)


@pytest.fixture
def controller(tmp_path, monkeypatch):
    path=tmp_path/'vision_assembly/config';path.mkdir(parents=True)
    (path/'assembly_launcher_revision.json').write_text(json.dumps({'revision':'reviewed'}))
    process=Process();calls=[]
    def popen(*args,**kwargs):calls.append((args,kwargs));return process
    c=AssemblyCycleController(tmp_path,lambda:None,lambda _:None,popen)
    # Tests drive monitoring explicitly: no ROS, no subprocess and no hardware.
    monkeypatch.setattr('fr5_process_sequences.assembly_cycle_api.threading.Thread.start',lambda _:None)
    return c,process,calls


def request():
    return dict(schema=SCHEMA,action='assembly.start',job_id=str(uuid4()),operation_id=str(uuid4()),
                recipe_revision='reviewed',confirm_scene_ready=True)


def test_requires_explicit_ready_revision_and_rejects_coordinates(controller):
    c,_,calls=controller
    for change in [dict(confirm_scene_ready=False),dict(recipe_revision='old'),dict(tcp=[0]*6)]:
        data=request();data.update(change)
        with pytest.raises(ValueError):c.command(data)
    assert not calls


def test_identical_retransmission_launches_once_conflict_rejected(controller):
    c,_,calls=controller;data=request()
    c.command(data);c.command(data)
    assert len(calls)==1
    assert calls[0][0][0][-2:]==['--run-id',data['operation_id']]
    assert calls[0][1]['env']['FASTDDS_BUILTIN_TRANSPORTS']=='UDPv4'
    with pytest.raises(ValueError):c.command(dict(data,job_id=str(uuid4())))
    with pytest.raises(BackendFailure):c.command(request())


def test_restart_never_reexecutes_unresolved_request(controller):
    c,_,calls=controller;data=request();c.command(data)
    recovered=AssemblyCycleController(c.root,lambda:None,lambda _:None,c.popen)
    assert recovered.snapshot()['status']=='recovery_required'
    assert recovered.command(data)['status']=='recovery_required'
    with pytest.raises(BackendFailure):recovered.command(request())
    assert len(calls)==1


def test_shared_execution_guard_blocks_without_hardware_stop(controller):
    c,_,calls=controller
    real,vision,robot,ghost,events=backend()
    real._execution_guard=lambda:robot_execution_guard(c.root)
    with robot_execution_guard(c.root):
        with pytest.raises(BackendFailure):c.command(request())
        result=real.execute(pick())
    assert result.error_code=='ROBOT_BUSY'
    assert not calls
    # A rejected individual request must not stop the owner of the lock.
    assert not robot.log


def test_stop_is_correlated_and_not_reported_as_completed(controller):
    c,p,_=controller;data=request();c.command(data)
    stop=dict(schema=SCHEMA,action='assembly.stop',job_id=data['job_id'],operation_id=data['operation_id'])
    with pytest.raises(ValueError):c.command(dict(stop,job_id=str(uuid4())))
    c.command(stop)
    assert p.signals and c.snapshot()['status']=='stop_requested'
    p.code=1;c._monitor()
    assert c.snapshot()['status']=='recovery_required'
    assert c.snapshot()['physical_placement_verified'] is False


def test_zero_exit_without_completion_evidence_is_not_success(controller):
    c,p,_=controller;c.command(request());p.code=0;c._monitor()
    assert c.snapshot()['status']=='recovery_required'


def test_completed_cycle_is_motion_only_and_replays_after_restart(controller):
    c,p,calls=controller;data=request();c.command(data)
    from pathlib import Path
    d=Path(c.snapshot()['run_directory']);d.mkdir(parents=True)
    (d/'cycle.json').write_text(json.dumps({'status':'motion_complete_awaiting_physical_verification','steps':[]}))
    slots=['GPU-01']+[f'HBM-{i:02}' for i in range(1,9)]+[f'PM-{i:02}' for i in range(1,5)]+[f'VRM-{i:02}' for i in range(1,6)]+['IND-01','IND-02']
    for phase,items in [('non-smd',slots),('smd',[f'CAP-{i:02}' for i in range(1,6)])]:
        (d/f'{phase}_run.json').write_text(json.dumps({'motion_completed_slots':items}))
    p.code=0;c._monitor()
    assert c.snapshot()['status']=='motion_complete_awaiting_physical_verification'
    assert not c.snapshot()['physical_placement_verified']
    new=AssemblyCycleController(c.root,lambda:None,lambda _:None,c.popen)
    assert new.command(data)['status']=='motion_complete_awaiting_physical_verification'
    assert len(calls)==1


def test_check_uses_internal_worker_without_motion_or_scene_confirmation(controller):
    c,p,calls=controller
    c.ready=lambda: (_ for _ in ()).throw(AssertionError('check must not arm motion'))
    data=request();data.update(action='assembly.check',confirm_scene_ready=False)
    c.command(data)
    argv=calls[0][0][0]
    assert argv[1].endswith('/scripts/run_assembly_cycle_worker.sh')
    assert '--check' in argv and '--execute' not in argv
    p.code=0;c._monitor()
    assert c.snapshot()['status']=='check_completed'


@pytest.mark.parametrize('profile',['GPU','HBM','PM','VRM','IND','SMD'])
def test_group_is_fixed_profile_not_arbitrary_script(controller,profile):
    c,p,calls=controller;c.command(dict(request(),profile=profile))
    argv=calls[0][0][0]
    assert argv[argv.index('--profile')+1]==profile
    assert 'run_fr5_cycle.sh' not in argv[1]


def test_unknown_profile_is_rejected_before_launch(controller):
    c,p,calls=controller
    with pytest.raises(ValueError):c.command(dict(request(),profile='../../script.py'))
    assert not calls
