import json
import pytest
import cycle_pause


def test_pause_excludes_elapsed_time_without_replaying_steps(tmp_path,monkeypatch):
    path=tmp_path/'control.json';now=[100.]
    monkeypatch.setenv('FR5_ASSEMBLY_CONTROL_RECORD',str(path))
    monkeypatch.setenv('FR5_ASSEMBLY_EXECUTION_ID','unit')
    monkeypatch.setattr(cycle_pause.time,'monotonic',lambda:now[0])
    def write(**data):path.write_text(json.dumps(dict(operation_id='unit',**data)))
    write(status='running');assert cycle_pause.clock()==100.
    now[0]=130.;write(status='paused',pause_started_monotonic=100.)
    assert cycle_pause.clock()==100.
    now[0]=131.;write(status='running',paused_seconds=30.)
    assert cycle_pause.clock()==101.
    cycle_pause.checkpoint()
    write(status='recovery_required')
    with pytest.raises(RuntimeError,match='stopped or lost'):cycle_pause.checkpoint()


def test_worker_loss_and_foreign_identity_cannot_resume(tmp_path,monkeypatch):
    path=tmp_path/'control.json'
    monkeypatch.setenv('FR5_ASSEMBLY_CONTROL_RECORD',str(path))
    monkeypatch.setenv('FR5_ASSEMBLY_EXECUTION_ID','unit')
    path.write_text(json.dumps(dict(operation_id='other',status='running')))
    with pytest.raises(RuntimeError,match='identity'):cycle_pause.checkpoint()
    path.write_text(json.dumps(dict(operation_id='unit',status='paused',server_pid=0,server_process_start='0')))
    with pytest.raises(RuntimeError,match='owner lost'):cycle_pause.checkpoint()
