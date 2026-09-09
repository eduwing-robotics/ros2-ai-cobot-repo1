"""No DB/ROS needed: python -m pytest this_file.py (set MAIN_SERVER_SOURCE)."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import sys
import types
from unittest.mock import patch
import pytest


@pytest.fixture
def server():
    path = Path(os.environ.get('MAIN_SERVER_SOURCE', 'MAIN_SERVER/server.py'))
    modules = {name: types.ModuleType(name) for name in ('datasheet', 'queries', 'assembly_gateway')}
    modules['assembly_gateway'].AssemblyGateway = lambda: None
    modules['assembly_gateway'].GatewayUnavailable = type('GatewayUnavailable', (Exception,), {})
    modules['queries'].ResourceNotFound = type('ResourceNotFound', (Exception,), {})
    modules['queries'].DatabaseUnavailable = type('DatabaseUnavailable', (Exception,), {})
    modules['datasheet'].DatasheetIntegrityError = type('DatasheetIntegrityError', (Exception,), {})
    spec = importlib.util.spec_from_file_location('receiver_under_test', path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


def package(changed=False, path_override=None):
    key = 'a' * 64
    raw = b'{"status":"UNKNOWN"}'
    payload = dict(schema_id='ksmc.vision-inspection.v1', idempotency_key=key,
        inspection_id='INSP-20260907-120000-AAAAAAAAAA', overall={'decision':'UNKNOWN'},
        source={'hybrid_report_sha256':hashlib.sha256(raw).hexdigest()}, images=[], job_id=None, unit_id=None)
    fields = {'raw_hybrid_report':raw}
    for role in ('source_roi','annotated_report','candidate_heatmap','candidate_heatmap_overlay'):
        content = b'\x89PNG\r\n\x1a\n' + role.encode()
        payload['images'].append(dict(role=role,file=path_override or f'images/{role}.png',
            size_bytes=len(content),sha256=hashlib.sha256(content).hexdigest(),mime_type='image/png'))
        fields['image_'+role]=content
    if changed:
        payload['board_id']='changed'
    fields['metadata']=json.dumps(payload).encode()
    body=b''.join(b'--test\r\nContent-Disposition: form-data; name="'+name.encode()+
        b'"; filename="ignored"\r\n\r\n'+content+b'\r\n' for name,content in fields.items())+b'--test--\r\n'
    return body, 'multipart/form-data; boundary=test', key


def test_store_duplicate_conflict(server, tmp_path):
    receipt=server.store_vision_files(*package(),tmp_path)
    assert receipt['stored'] and not receipt['production_applied']
    assert receipt['binding_status']=='UNBOUND'
    assert server.store_vision_files(*package(),tmp_path)['duplicate']
    with pytest.raises(server.AssemblyRejected) as exc:
        server.store_vision_files(*package(changed=True),tmp_path)
    assert exc.value.status==409
    assert len(list(tmp_path.iterdir()))==1


def test_traversal_rejected(server, tmp_path):
    with pytest.raises(server.ValidationError):
        server.store_vision_files(*package(path_override='../escape.png'),tmp_path)
    assert not list(tmp_path.iterdir())


def test_hash_and_header_rejected(server, tmp_path):
    body, content_type, key=package()
    with pytest.raises(server.ValidationError):
        server.store_vision_files(body.replace(b'\x89PNG',b'\x88PNG'),content_type,key,tmp_path)
    with pytest.raises(server.ValidationError):
        server.store_vision_files(body,content_type,'b'*64,tmp_path)


def test_http_auth_and_storage(server, tmp_path, monkeypatch):
    import threading
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    monkeypatch.setenv('VISION_INGEST_TOKEN','test-secret')
    monkeypatch.setenv('VISION_INGEST_ROOT',str(tmp_path))
    httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.ApiHandler)
    thread=threading.Thread(target=httpd.serve_forever,daemon=True)
    thread.start()
    try:
        body, content_type, key=package()
        url=f'http://127.0.0.1:{httpd.server_port}/api/v1/vision/inspections'
        headers={'Content-Type':content_type,'Idempotency-Key':key}
        with pytest.raises(HTTPError) as exc:
            urlopen(Request(url,data=body,headers=headers))
        assert exc.value.code==401
        headers['Authorization']='Bearer test-secret'
        with urlopen(Request(url,data=body,headers=headers)) as response:
            assert json.load(response)['data']['stored'] is True
        # In the Vision workspace also exercise its real multipart sender and
        # matching-receipt validation against this HTTP handler.
        exporter_dir=Path(__file__).resolve().parents[2]/'vision_assembly/integration'
        if exporter_dir.is_dir():
            sys.path.insert(0,str(exporter_dir))
            import export_inspection_result as exporter
            from email.parser import BytesParser
            from email.policy import default
            msg=BytesParser(policy=default).parsebytes(
                ('Content-Type: '+content_type+'\r\n\r\n').encode()+body)
            fields={p.get_param('name',header='content-disposition'):p.get_payload(decode=True)
                    for p in msg.iter_parts()}
            payload=json.loads(fields['metadata'])
            outbound=tmp_path/'outbound'
            (outbound/'images').mkdir(parents=True)
            (outbound/'raw').mkdir()
            payload['source']['hybrid_report_file']='raw/hybrid_report.json'
            (outbound/'inspection_result.json').write_text(json.dumps(payload))
            (outbound/'raw/hybrid_report.json').write_bytes(fields['raw_hybrid_report'])
            for item in payload['images']:
                (outbound/item['file']).write_bytes(fields['image_'+item['role']])
            # Different metadata under the same key must conflict first.
            with pytest.raises(exporter.ExportError):
                exporter.send_package(url,outbound,payload,token='test-secret')
            monkeypatch.setenv('VISION_INGEST_ROOT',str(tmp_path/'sender-receipts'))
            receipt=exporter.send_package(url,outbound,payload,token='test-secret')
            assert receipt['delivered'] is True
            receipt=exporter.send_package(url,outbound,payload,token='test-secret')
            assert json.loads(receipt['response'])['data']['duplicate'] is True
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


def test_concurrent_duplicates(server, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _: server.store_vision_files(*package(),tmp_path),range(4)))
    assert sum(not r['duplicate'] for r in results)==1
    assert len(list(tmp_path.iterdir()))==1


def test_write_failure_has_no_receipt(server, tmp_path, monkeypatch):
    def fail(*args):
        raise OSError('simulated disk failure')
    monkeypatch.setattr(server.os,'fsync',fail)
    with pytest.raises(OSError):
        server.store_vision_files(*package(),tmp_path)
    assert not list(tmp_path.iterdir())
