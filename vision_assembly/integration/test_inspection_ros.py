"""ROS transport contract tests using an inert runner; no equipment or sockets."""
import hashlib
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace as NS
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import inspection_ros as ros
from inspection_ros_client import download_image


def request(**kwargs):
    return NS(**dict(dict(inspection_id=str(uuid.uuid4()), job_id=str(uuid.uuid4()),
                         unit_id=1), **kwargs))


def seeded(tmp_path):
    blob = b'\x89PNG\r\n\x1a\n' + bytes(range(256)) * 700
    req = request()
    info = dict(ready=True, filename=ros.IMAGE_NAME, mime_type='image/png',
                sha256=hashlib.sha256(blob).hexdigest(), size_bytes=len(blob),
                path='/api/v1/inspections/old/image')
    view = dict(info, slot_code='ALL', filename='countermeasure.png')
    info['countermeasure_views'] = [view]
    store = ros.Store(tmp_path, lambda: False, None)
    record = dict(vars(req), status='COMPLETED', result={'decision': 'UNKNOWN'}, image=info)
    store.save(record)
    directory = tmp_path / req.inspection_id
    (directory / ros.IMAGE_NAME).write_bytes(blob)
    (directory / view['filename']).write_bytes(blob)
    return ros.Store(tmp_path, lambda: False, None), req, blob


def test_durable_get_unknown_and_no_http_links(tmp_path):
    store, req, _ = seeded(tmp_path)
    record = ros.Transport(store).get(req)
    assert record['result']['decision'] == 'UNKNOWN'
    assert '/api/' not in json.dumps(record)
    assert record['image']['service'] == '/vision/inspection/get_image'
    assert store.get(req.inspection_id)['image']['path'].startswith('/api/')


def test_submit_idempotency_busy_conflict_and_restart(tmp_path):
    calls, gate = [], threading.Event()
    def run(req, directory):
        calls.append(req)
        gate.wait(3)
        return {'decision': 'UNKNOWN'}, {'ready': False}
    store = ros.Store(tmp_path, lambda: True, run)
    transport, req = ros.Transport(store), request()
    try:
        assert transport.submit(req)['status'] in ('ACCEPTED', 'RUNNING')
        transport.submit(req)
        with pytest.raises(ros.ApiError, match='') as error:
            transport.submit(request())
        assert error.value.code == 'inspection_busy'
        with pytest.raises(ros.ApiError) as error:
            transport.submit(request(inspection_id=req.inspection_id, job_id=req.job_id, unit_id=2))
        assert error.value.code == 'inspection_conflict'
    finally:
        gate.set()
        store.thread.join(3)
    restarted = ros.Transport(ros.Store(tmp_path, lambda: False, None))
    assert restarted.submit(req)['result']['decision'] == 'UNKNOWN'
    assert len(calls) == 1


def test_admission_and_error_response(tmp_path):
    store = ros.Store(tmp_path, lambda: False, lambda *_: pytest.fail('capture'))
    transport = ros.Transport(store)
    response = ros.callback(transport.submit)(request(), NS())
    assert not response.success and response.error_code == 'station_not_ready'
    response = ros.callback(transport.get)(request(inspection_id='../escape'), NS())
    assert not response.success and response.error_code == 'invalid_identity'
    response = ros.callback(transport.get)(request(), NS())
    assert not response.success and response.error_code == 'inspection_not_found'


@pytest.mark.parametrize('slot', ['', 'ALL'])
def test_chunk_download_complete_and_digest(tmp_path, slot):
    store, req, blob = seeded(tmp_path / 'store')
    transport = ros.Transport(store)
    record = transport.get(req)
    info = record['image'] if not slot else record['image']['countermeasure_views'][0]
    offsets = []
    def fetch(iid, slot, offset, count):
        offsets.append(offset)
        return ros.callback(transport.image, image=True)(NS(inspection_id=iid,
            slot_code=slot, offset=offset, max_bytes=count), NS())
    target = tmp_path / 'result.png'
    download_image(fetch, req.inspection_id, slot, target, info)
    assert target.read_bytes() == blob
    assert offsets == [0, 65536, 131072]
    assert not target.with_suffix('.png.part').exists()


@pytest.mark.parametrize('changes,code', [
    ({'max_bytes': 0}, 'invalid_image_range'),
    ({'max_bytes': 65537}, 'invalid_image_range'),
    ({'offset': 999999}, 'invalid_image_range'),
    ({'slot_code': '../other'}, 'countermeasure_image_unavailable'),
])
def test_bad_image_requests(tmp_path, changes, code):
    store, req, _ = seeded(tmp_path)
    query = dict(inspection_id=req.inspection_id, slot_code='', offset=0, max_bytes=65536)
    query.update(changes)
    with pytest.raises(ros.ApiError) as error:
        ros.Transport(store).image(NS(**query))
    assert error.value.code == code


@pytest.mark.parametrize('mode', ['corrupt', 'traversal', 'symlink', 'unready'])
def test_image_fail_closed(tmp_path, mode):
    store, req, _ = seeded(tmp_path / 'store')
    record = store.records[req.inspection_id]
    path = store.root / req.inspection_id / ros.IMAGE_NAME
    if mode == 'corrupt':
        path.write_bytes(b'corrupt')
    elif mode == 'traversal':
        record['image']['filename'] = '../other.png'
    elif mode == 'symlink':
        other = tmp_path / 'other.png'
        path.rename(other)
        path.symlink_to(other)
    else:
        record['image']['ready'] = False
    result = ros.callback(ros.Transport(store).image, image=True)(
        NS(inspection_id=req.inspection_id, slot_code='', offset=0, max_bytes=65536), NS())
    assert not result.success
    assert result.error_code == ('image_not_ready' if mode == 'unready' else 'image_integrity_error')


@pytest.mark.parametrize('mode', ['wrong_id', 'corrupt_chunk', 'short_chunk', 'wrong_hash'])
def test_client_never_replaces_good_file_with_bad_image(tmp_path, mode):
    store, req, _ = seeded(tmp_path / 'store')
    transport = ros.Transport(store)
    def fetch(iid, slot, offset, count):
        data = transport.image(NS(inspection_id=iid, slot_code=slot, offset=offset, max_bytes=count))
        if mode == 'wrong_id':
            data['inspection_id'] = str(uuid.uuid4())
        elif mode == 'corrupt_chunk':
            data['data'] = b'X' + data['data'][1:]
        elif mode == 'short_chunk':
            data['data'], data['eof'] = b'', False
        else:
            data['sha256'] = '0' * 64
        return NS(success=True, **data)
    target = tmp_path / 'existing.png'
    target.write_bytes(b'preserved')
    with pytest.raises(RuntimeError):
        download_image(fetch, req.inspection_id, '', target, transport.get(req)['image'])
    assert target.read_bytes() == b'preserved'
    assert not target.with_suffix('.png.part').exists()
