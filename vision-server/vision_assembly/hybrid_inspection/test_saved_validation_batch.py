import hashlib
import pytest
import subprocess
import os
import signal
import sys
import selectors
from pathlib import Path
from unittest.mock import Mock
import run_saved_validation_batch as batch
from run_saved_validation_batch import validate_cases


def case(tmp_path):
    image=tmp_path/'capture.png';image.write_bytes(b'original')
    return dict(image='capture.png',sha256=hashlib.sha256(b'original').hexdigest())


def test_hash_guard(tmp_path):
    c=case(tmp_path)
    assert len(validate_cases(dict(cases=[c]),tmp_path))==1
    (tmp_path/'capture.png').write_bytes(b'changed')
    with pytest.raises(ValueError,match='hash'):validate_cases(dict(cases=[c]),tmp_path)


def test_duplicate_not_independent(tmp_path):
    c=case(tmp_path)
    with pytest.raises(ValueError,match='Duplicate'):validate_cases(dict(cases=[c,c]),tmp_path)


def test_empty_is_not_completed():
    with pytest.raises(ValueError):validate_cases(dict(cases=[]))


def test_unspecified_split_not_assumed_independent(tmp_path):
    r=validate_cases(dict(cases=[case(tmp_path)]),tmp_path)[0]
    assert r['split']=='UNSPECIFIED_NOT_INDEPENDENT'


def test_latest_alias_is_not_frozen_capture(tmp_path):
    c=case(tmp_path)
    (tmp_path/'latest.png').symlink_to(tmp_path/'capture.png')
    c['image']='latest.png'
    with pytest.raises(ValueError,match='Mutable'):validate_cases(dict(cases=[c]),tmp_path)


def test_timeout_cleans_owned_group(monkeypatch):
    proc=Mock(pid=12345)
    proc.wait.side_effect=[subprocess.TimeoutExpired('owned',1),0,0]
    create=Mock(return_value=proc)
    kill=Mock()
    monkeypatch.setattr(batch.subprocess,'Popen',create)
    monkeypatch.setattr(batch.os,'killpg',kill)
    with pytest.raises(subprocess.TimeoutExpired):batch.execute_owned(['owned'],None,1)
    assert create.call_args.kwargs['start_new_session'] is True
    assert all(call.args[0]==12345 for call in kill.call_args_list)
    assert kill.call_count==2


def test_parent_sigterm_reaps_inference_process():
    script = '''
import signal,sys
from run_saved_validation_batch import execute_owned,handle_termination,BatchCancelled
signal.signal(signal.SIGTERM,handle_termination)
try:
    execute_owned([sys.executable,'-c','import os,time; print(os.getpid(),flush=True); time.sleep(30)'],sys.stdout,20)
except BatchCancelled:
    sys.exit(143)
'''
    parent=subprocess.Popen([sys.executable,'-c',script],cwd=Path(batch.__file__).parent,
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    child=None
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(parent.stdout,selectors.EVENT_READ)
            assert selector.select(timeout=5), 'child did not start'
        child=int(parent.stdout.readline().strip())
        parent.terminate()
        assert parent.wait(timeout=5)==143
        with pytest.raises(ProcessLookupError):os.kill(child,0)
    finally:
        if parent.poll() is None:
            parent.kill()
        parent.wait()
        if child is not None:
            try:os.kill(child,signal.SIGKILL)
            except ProcessLookupError:pass
