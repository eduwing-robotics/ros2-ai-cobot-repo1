import importlib.util
from pathlib import Path
import threading
import uuid
import pytest

spec = importlib.util.spec_from_file_location('inspection_api', Path(__file__).with_name('inspection_api.py'))
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)

def request():
    return dict(inspection_id=str(uuid.uuid4()), job_id=str(uuid.uuid4()), unit_id=1)

def test_idempotent_unknown_and_restart(tmp_path):
    calls = []
    def run(req, directory):
        calls.append(req)
        return {'decision': 'UNKNOWN'}, {'ready': False}
    store = api.Store(tmp_path, lambda: True, run)
    req = request()
    store.submit(req, req['inspection_id'])
    store.thread.join()
    assert store.get(req['inspection_id'])['result']['decision'] == 'UNKNOWN'
    store = api.Store(tmp_path, lambda: False, run)
    assert store.submit(req, req['inspection_id'])['status'] == 'COMPLETED'
    assert len(calls) == 1
    with pytest.raises(api.ApiError) as error:
        store.submit(dict(req, unit_id=2), req['inspection_id'])
    assert error.value.status == 409

def test_busy_and_not_ready(tmp_path):
    gate = threading.Event()
    store = api.Store(tmp_path, lambda: True,
        lambda *args: (gate.wait(2) and {'decision': 'PASS'}, {'ready': False}))
    req = request()
    store.submit(req, req['inspection_id'])
    other = request()
    try:
        with pytest.raises(api.ApiError) as error:
            store.submit(other, other['inspection_id'])
        assert error.value.code == 'inspection_busy'
    finally:
        gate.set()
        store.thread.join()
    store.ready = lambda: False
    with pytest.raises(api.ApiError) as error:
        store.submit(other, other['inspection_id'])
    assert error.value.status == 503

def test_interrupted_never_recaptures(tmp_path):
    store = api.Store(tmp_path, lambda: True, None)
    req = request()
    store.save(dict(req, status='RUNNING', evidence={'ready': False}))
    store = api.Store(tmp_path, lambda: True, None)
    assert store.submit(req, req['inspection_id'])['status'] == 'FAILED'

def test_station_freshness(monkeypatch):
    now = [100.]
    monkeypatch.setattr(api.time, 'monotonic', lambda: now[0])
    station = api.Station()
    assert not station.ready()
    station.update('arrived', True)
    station.update('moving', False)
    assert not station.ready()
    now[0] += .4
    assert station.ready()
    now[0] += 1
    assert not station.ready()

@pytest.mark.parametrize('unit', [True, 0, -1, '42'])
def test_bad_identity(unit):
    with pytest.raises(api.ApiError):
        api.identity(dict(request(), unit_id=unit))


def test_http_roundtrip(tmp_path):
    import hashlib
    import json
    import urllib.request
    import urllib.error
    token = 'test-token-' * 4
    blob = b'\x89PNG\r\n\x1a\nmocked immutable PNG bytes'
    def run(req, directory):
        (directory/api.IMAGE_NAME).write_bytes(blob)
        return {'decision': 'UNKNOWN'}, {'ready': True,
            'sha256': hashlib.sha256(blob).hexdigest()}
    store = api.Store(tmp_path, lambda: True, run)
    server = api.ThreadingHTTPServer(('127.0.0.1', 0), api.handler(store, token))
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}/api/v1/inspections'
    req = request()
    headers = {'Authorization': 'Bearer '+token,
        'Idempotency-Key': req['inspection_id'], 'Content-Type': 'application/json'}
    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(base+'/'+req['inspection_id'])
        assert error.value.code == 401
        with urllib.request.urlopen(urllib.request.Request(base,
                json.dumps(req).encode(), headers)) as response:
            assert response.status == 202
        store.thread.join()
        with urllib.request.urlopen(urllib.request.Request(base+'/'+req['inspection_id'],
                headers=headers)) as response:
            assert json.load(response)['data']['result']['decision'] == 'UNKNOWN'
        with urllib.request.urlopen(urllib.request.Request(base+'/'+req['inspection_id']+'/image',
                headers=headers)) as response:
            assert response.read() == blob
            assert response.headers['Content-Type'] == 'image/png'
            assert response.headers['X-Content-SHA256'] == hashlib.sha256(blob).hexdigest()
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(urllib.request.Request(base+'/'+req['inspection_id']+'/evidence', headers=headers))
        assert error.value.code == 404
        (tmp_path/req['inspection_id']/api.IMAGE_NAME).write_bytes(b'corrupt')
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(urllib.request.Request(base+'/'+req['inspection_id']+'/image', headers=headers))
        assert error.value.code == 409
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_prepare_json_png_no_archive(tmp_path):
    import json
    from test_export_inspection_result import _report, _config
    report = _report(tmp_path)
    raw = json.loads(report.read_text())
    raw['capture_quality'] = dict(status='NO_GROSS_ISSUE_DETECTED', blocks_decision=False)
    raw['evidence_audit'] = dict(raw_fail_count=1, undisplayed_count=1, items=[])
    report.write_text(json.dumps(raw))
    image = Path(raw['visualization']['report'])
    image.write_bytes(b'\x89PNG\r\n\x1a\nfixture')
    req = request()
    directory = tmp_path/'request'
    directory.mkdir()
    result, info = api.prepare_result(report, directory, req, _config(tmp_path))
    assert result['decision'] == 'UNKNOWN'
    assert result['diagnostics']['capture_quality'] == raw['capture_quality']
    assert result['diagnostics']['evidence_audit'] == raw['evidence_audit']
    assert len(result['slots']) == 25
    assert result['findings'] and result['defects'] == []
    assert all(not f['confirmed_defect'] for f in result['findings'])
    assert 'evidence_image_roles' not in str(result)
    assert info['path'].endswith('/image')
    assert (directory/api.IMAGE_NAME).read_bytes() == image.read_bytes()
    assert not list(directory.rglob('*.zip'))
    assert list(directory.rglob('hybrid_report.json'))
    # Reuse must not create an archive either.
    assert api.prepare_result(report, directory, req, _config(tmp_path)) == (result, info)


def test_old_zip_record_not_exposed(tmp_path):
    req = request()
    store = api.Store(tmp_path, lambda: True, None)
    record = dict(req, status='COMPLETED', evidence={'ready': True, 'path': '/old/evidence'})
    store.save(record)
    store = api.Store(tmp_path, lambda: True, None)
    assert 'evidence' not in store.get(req['inspection_id'])
    assert store.get(req['inspection_id'])['image']['ready'] is False


def test_submit_and_runner_results_are_detached_snapshots(tmp_path):
    result = {'decision': 'UNKNOWN', 'diagnostics': {'flags': []}}
    image = {'ready': False}
    store = api.Store(tmp_path, lambda: True, lambda *_: (result, image))
    req = request()
    accepted = store.submit(req, req['inspection_id'])
    store.thread.join(timeout=2)
    accepted['image']['ready'] = True
    result['diagnostics']['flags'].append('mutated')
    image['ready'] = True
    replay = store.submit(req, req['inspection_id'])
    replay['result']['decision'] = 'PASS'
    saved = store.get(req['inspection_id'])
    assert saved['image']['ready'] is False
    assert saved['result'] == {'decision': 'UNKNOWN', 'diagnostics': {'flags': []}}


def test_worker_start_failure_does_not_leave_station_busy(tmp_path, monkeypatch):
    store = api.Store(tmp_path, lambda: True, lambda *_: pytest.fail('unexpected capture'))
    req = request()
    def fail_start(_):
        raise RuntimeError('cannot start thread')
    monkeypatch.setattr(api.threading.Thread, 'start', fail_start)
    with pytest.raises(api.ApiError) as error:
        store.submit(req, req['inspection_id'])
    assert error.value.status == 503
    assert store.active is None
    assert store.submit(req, req['inspection_id'])['status'] == 'FAILED'
    restarted = api.Store(tmp_path, lambda: True, None)
    assert restarted.get(req['inspection_id'])['status'] == 'FAILED'


def test_failed_completion_write_never_exposes_pass_or_image(tmp_path, monkeypatch):
    store = api.Store(tmp_path, lambda: True,
                      lambda *_: ({'decision': 'PASS'}, {'ready': True}))
    save = store.save
    def fail_completion(record):
        if record['status'] == 'COMPLETED':
            raise OSError('mock disk full')
        save(record)
    monkeypatch.setattr(store, 'save', fail_completion)
    req = request()
    store.submit(req, req['inspection_id'])
    store.thread.join(timeout=2)
    failed = store.get(req['inspection_id'])
    assert failed['status'] == 'FAILED'
    assert failed['image']['ready'] is False
    assert 'result' not in failed
    assert store.active is None
    assert api.Store(tmp_path, lambda: True, None).get(req['inspection_id']) == failed


def test_cancelled_runner_does_not_launch_capture(tmp_path, monkeypatch):
    runner = api.Runner(10, -1)
    runner.stop.set()
    monkeypatch.setattr(api.subprocess, 'Popen', lambda *_a, **_k: pytest.fail('capture launched'))
    with pytest.raises(RuntimeError, match='shutdown'):
        runner(request(), tmp_path)


def test_persistent_state_write_failure_closes_admission(tmp_path, monkeypatch):
    store = api.Store(tmp_path, lambda: True, lambda *_: ({'decision': 'PASS'}, {'ready': False}))
    save = store.save
    def broken_disk(record):
        if record['status'] != 'ACCEPTED':
            raise OSError('mock disk failure')
        save(record)
    monkeypatch.setattr(store, 'save', broken_disk)
    req = request()
    store.submit(req, req['inspection_id'])
    store.thread.join(timeout=2)
    assert not store.thread.is_alive()
    assert store.closing and store.active is None
    assert store.get(req['inspection_id'])['status'] == 'FAILED'
    other = request()
    with pytest.raises(api.ApiError) as error:
        store.submit(other, other['inspection_id'])
    assert error.value.code == 'station_not_ready'
    restarted = api.Store(tmp_path, lambda: True, None)
    assert restarted.get(req['inspection_id'])['status'] == 'FAILED'


@pytest.mark.parametrize('post', [False, True])
def test_http_auth_checked_before_store_or_body_without_socket(post):
    from email.message import Message
    from io import BytesIO
    from types import SimpleNamespace
    def forbidden(*_):
        pytest.fail('unauthorized store access')
    handler = api.handler(SimpleNamespace(get=forbidden, submit=forbidden), 'fixture-token')
    instance = handler.__new__(handler)
    instance.headers = Message()
    instance.headers['Authorization'] = 'Bearer incorrect-token'
    instance.path = '/api/v1/inspections'
    instance.rfile = BytesIO(b'body must not be consumed')
    replies = []
    instance.reply = lambda status, body: replies.append((status, body))
    instance.dispatch(post)
    assert replies == [(401, {'error': {'code': 'unauthorized'}})]
    assert instance.rfile.tell() == 0
