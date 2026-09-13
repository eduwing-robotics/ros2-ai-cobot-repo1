"""Sequencer-owned requests; durable, single-flight S22 inspection backend.

No DB writes, outbound uploads, or motion commands. ROS imports are CLI-only.
"""
import copy
import hashlib
import hmac
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import threading
import time
import uuid
from urllib.parse import urlsplit, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / 'runtime/s22_camera_control/auto_inspection_trigger.lock'
IMAGE_NAME = '02_annotated_report.png'
DEMO_CONFIRMATION_POLICY = 'USER_AUTHORIZED_DEMO_CANDIDATES_V1'


def demo_confirmation_enabled():
    contract = json.loads((ROOT / 'vision_assembly/config/inspection_fusion_contract.json').read_text())
    return contract.get('operational_decision', {}).get('demo_confirmation', {}).get('mode') == DEMO_CONFIRMATION_POLICY


def confirm_demo_candidates(result):
    """Confirm a portfolio-demo disposition, not underlying model validation."""
    policy = result.get('operational_decision') or {}
    if not (result.get('decision') == policy.get('status') == 'FAIL'
            and policy.get('mode') == 'PROVISIONAL_BINARY_V1'
            and policy.get('validated') is False
            and policy.get('reasons') == ['DEFECT_CANDIDATE']):
        return
    findings, slots = result.get('findings', []), result.get('slots', [])
    by_id = {s.get('slot_id'): s for s in slots}
    # Never invent a defect for capture/registration/provider failures or
    # incomplete/malformed results. Confirm only existing, identifiable slots.
    if (not findings or len(slots) != 25 or len(by_id) != 25 or None in by_id
            or len({f.get('finding_id') for f in findings}) != len(findings)):
        return
    for f in findings:
        slot = by_id.get(f.get('slot_id'), {})
        if (not f.get('finding_id') or not f.get('primary_defect_code')
                or not f.get('slot_code') or f['slot_code'] != slot.get('slot_code')
                or f.get('authority') not in ('ADVISORY_ONLY', 'AUTHORITATIVE')):
            return
    for f in findings:
        if f.get('authority') == 'ADVISORY_ONLY':
            f['source_authority'] = 'ADVISORY_ONLY'
            f['source_confirmed_defect'] = f.get('confirmed_defect', False)
            f['decision_basis'] = DEMO_CONFIRMATION_POLICY
            f['authority'] = 'AUTHORITATIVE'
            f['confirmed_defect'] = True
    result['confirmation_policy'] = {
        'mode': DEMO_CONFIRMATION_POLICY, 'scope': 'PORTFOLIO_DEMO_ONLY',
        'model_validated': False,
        'basis': 'User-approved candidate confirmation, not measured defect verification.'}
    result['defects'] = [dict(slot_code=f['slot_code'], defect_type=f['primary_defect_code'],
                              finding_id=f['finding_id']) for f in findings
                         if f.get('confirmed_defect') is True and f.get('authority') == 'AUTHORITATIVE']
    if 'summary' in result:
        result['summary']['confirmed_defect_count'] = len(result['defects'])
        result['summary']['advisory_candidate_count'] = sum(f['authority'] == 'ADVISORY_ONLY' for f in findings)


def public_result(result, *, demo_confirmation=False):
    """Binary operator view; never rewrite archived provider evidence."""
    result = copy.deepcopy(result)
    if demo_confirmation:
        confirm_demo_candidates(result)
    policy = result.get('operational_decision') or {}
    provisional = (policy.get('mode') == 'PROVISIONAL_BINARY_V1'
                   and policy.get('validated') is False
                   and policy.get('status') == result.get('decision')
                   and result.get('decision') in ('PASS', 'FAIL'))
    if result.get('decision') not in ('PASS', 'FAIL'):
        result['decision'] = 'FAIL'
        result['reason'] = 'INSPECTION_INCONCLUSIVE'
    # Only the existing authorized operational policy may allow an uncertain
    # slot. Legacy/incomplete results fail closed; no blanket UNKNOWN -> PASS.
    localizable = provisional and bool(policy.get('reasons')) and set(policy['reasons']) <= {
        'NO_DISPLAYED_DEFECT_CANDIDATE', 'DEFECT_CANDIDATE'}
    findings = result.get('findings', [])
    failing_ids = {f.get('slot_id') for f in findings}
    for finding in findings:
        finding['decision'] = 'FAIL'
        # Candidate rejection is not a confirmed physical defect.
        finding.pop('measurements', None)
    for slot in result.get('slots', []):
        slot['decision'] = ('PASS' if localizable and slot.get('decision') != 'FAIL'
                            and slot.get('slot_id') not in failing_ids else 'FAIL')
        slot['reason'] = ('PROVISIONAL_NO_DEFECT_CANDIDATE' if slot['decision'] == 'PASS'
                          else 'OPERATIONAL_REJECTION')
        slot.pop('stages', None)
        # Raw status-bearing measurements belong to the local evidence archive.
        measurements = slot.get('measurements', {})
        measurements.pop('pin_status', None)
        measurements.pop('presence_state', None)
    if 'summary' in result:
        result['summary']['slot_decisions'] = {
            status: sum(s['decision'] == status for s in result.get('slots', []))
            for status in ('PASS', 'FAIL')}
    result.pop('validated_decision', None)
    result.pop('diagnostics', None)
    return result


def prepare_result(report, directory, request, config=None):
    """Archive locally; expose only compact findings/slots JSON and one PNG."""
    from export_inspection_result import build_package, DEFAULT_CONFIG
    package, _, payload = build_package(Path(report), config or DEFAULT_CONFIG,
        directory / 'package', create_archive=False, **request)
    findings = [{k: v for k, v in item.items() if k != 'evidence_image_roles'}
                for item in payload['findings']]
    result = dict(decision=payload['overall']['decision'],
        inspected_at=payload['inspected_at'], captured_at=payload['captured_at'],
        summary=payload['summary'], findings=findings, slots=payload['slots'],
        defects=[dict(slot_code=f['slot_code'], defect_type=f['primary_defect_code'],
                      finding_id=f['finding_id']) for f in findings if f['confirmed_defect']])
    result['diagnostics'] = payload.get('diagnostics', {})
    result['operational_decision'] = payload.get('operational_decision')
    result['validated_decision'] = payload.get('validated_decision')
    image = next(item for item in payload['images'] if item['role'] == 'annotated_report')
    source = package / image['file']
    if image['mime_type'] != 'image/png' or source.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('annotated_report_must_be_png')
    target = directory / IMAGE_NAME
    temporary = directory / (IMAGE_NAME + '.tmp')
    shutil.copyfile(source, temporary)
    with temporary.open('rb') as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, target)
    try:
        from countermeasure_image import prepare_views
        views, view_status = prepare_views(report, package, payload, directory)
    except (OSError, ValueError, ImportError, KeyError, TypeError):
        views, view_status = [], 'COUNTERMEASURE_RENDER_UNAVAILABLE'
    return result, dict(ready=True, filename=IMAGE_NAME, mime_type='image/png',
        path=f"/api/v1/inspections/{request['inspection_id']}/image",
        size_bytes=image['size_bytes'], sha256=image['sha256'],
        countermeasure_views=views, countermeasure_status=view_status)


class ApiError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


def identity(body):
    try:
        if set(body) != {'inspection_id', 'job_id', 'unit_id'}:
            raise ValueError()
        if type(body['unit_id']) is not int or body['unit_id'] <= 0:
            raise ValueError()
        return dict(inspection_id=str(uuid.UUID(body['inspection_id'])),
                    job_id=str(uuid.UUID(body['job_id'])), unit_id=body['unit_id'])
    except (ValueError, TypeError, AttributeError, KeyError):
        raise ApiError(400, 'invalid_identity')


class Station:
    """Require fresh continuously stopped/arrived samples before admission."""
    def __init__(self):
        self.samples = {}
        self.lock = threading.Lock()

    def update(self, name, value):
        now = time.monotonic()
        with self.lock:
            old = self.samples.get(name)
            since = old[2] if old and old[0] == value and now-old[1] < 1 else now
            self.samples[name] = (value, now, since)

    def ready(self):
        now = time.monotonic()
        with self.lock:
            return all(name in self.samples and self.samples[name][0] == value
                       and now-self.samples[name][1] < 1
                       and now-self.samples[name][2] >= .35
                       for name, value in [('arrived', True), ('moving', False)])


class Store:
    def __init__(self, root, ready, runner):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.ready, self.runner = ready, runner
        self.demo_confirmation = demo_confirmation_enabled()
        self.lock = threading.RLock()
        self.active = None
        self.thread = None
        self.closing = False
        self.records = {}
        for path in self.root.glob('*/state.json'):
            record = json.loads(path.read_text())
            if record['status'] in ('ACCEPTED', 'RUNNING'):
                record.update(status='FAILED', error={'code': 'interrupted'})
                self.save(record)
            self.records[record['inspection_id']] = record

    def save(self, record):
        directory = self.root / record['inspection_id']
        directory.mkdir(exist_ok=True, mode=0o700)
        temp = directory / 'state.tmp'
        with temp.open('w') as stream:
            os.chmod(temp, 0o600)
            json.dump(record, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, directory / 'state.json')
        fd = os.open(directory, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def submit(self, body, key):
        request = identity(body)
        iid = request['inspection_id']
        if key != iid:
            raise ApiError(400, 'idempotency_key_mismatch')
        with self.lock:
            if iid in self.records:
                record = self.records[iid]
                if any(record[k] != v for k, v in request.items()):
                    raise ApiError(409, 'inspection_conflict')
                return self.get(iid)
            if self.active:
                raise ApiError(409, 'inspection_busy')
            if self.closing or not self.ready():
                raise ApiError(503, 'station_not_ready')
            record = dict(request, status='ACCEPTED', image={'ready': False})
            self.save(record)
            self.records[iid] = record
            self.active = iid
            self.thread = threading.Thread(target=self.work, args=(iid,))
            try:
                self.thread.start()
            except RuntimeError as exc:
                self.thread = None
                self.active = None
                self.fail(iid, exc)
                raise ApiError(503, 'worker_unavailable') from exc
            return self.get(iid)

    def fail(self, iid, exc):
        """A failed write/execution must never expose a partly published result."""
        with self.lock:
            record = dict(self.records[iid], status='FAILED', image={'ready': False},
                          error={'code': 'execution_failed', 'message': type(exc).__name__})
            record.pop('result', None)
            self.records[iid] = record
            try:
                self.save(record)
            except OSError as save_error:
                # Restart recovery fails durable ACCEPTED/RUNNING records.
                # Refuse further work while persistence is unhealthy.
                self.closing = True
                print(f'Inspection {iid} failure could not be saved: {save_error}', file=sys.stderr)
        print(f'Inspection {iid} failed: {exc}', file=sys.stderr)

    def work(self, iid):
        try:
            with self.lock:
                if self.closing or not self.ready():
                    raise RuntimeError('station_not_ready_before_capture')
                record = dict(self.records[iid], status='RUNNING')
                self.save(record)
                self.records[iid] = record
            result, image_info = self.runner(identity({k: record[k] for k in
                ('inspection_id', 'job_id', 'unit_id')}), self.root / iid)
            if result['decision'] not in ('PASS', 'FAIL', 'UNKNOWN'):
                raise RuntimeError('invalid_decision')
            with self.lock:
                completed = copy.deepcopy(dict(record, status='COMPLETED',
                                               result=result, image=image_info))
                self.save(completed)
                self.records[iid] = completed
        except Exception as exc:
            self.fail(iid, exc)
        finally:
            with self.lock:
                self.active = None

    def get(self, iid):
        with self.lock:
            if iid not in self.records:
                raise ApiError(404, 'inspection_not_found')
            data = json.loads(json.dumps(self.records[iid]))
            # Old ZIP records remain locally intact; never expose obsolete links.
            data.pop('evidence', None)
            data.setdefault('image', dict(ready=False, error='legacy_zip_record'))
            if isinstance(data.get('result'), dict):
                data['result'] = public_result(data['result'], demo_confirmation=self.demo_confirmation)
            for view in data['image'].get('countermeasure_views', []):
                rendering = view.get('rendering', {})
                if rendering.get('decision') == 'UNKNOWN':
                    rendering['decision'] = 'FAIL'
            return data


class Runner:
    def __init__(self, timeout, lock_fd, source_topic='/vision/inspection/submit'):
        self.timeout, self.lock_fd = timeout, lock_fd
        self.source_topic = source_topic
        self.stop = threading.Event()
        from inspection_process import InspectionProcess
        self.process = InspectionProcess(lock_fd)

    def close(self):
        self.stop.set()
        self.process.close()

    def __call__(self, request, directory):
        if self.stop.is_set():
            raise RuntimeError('shutdown_before_capture')
        event = directory / 'event.json'
        self.process.execute(
            ['--event-output', str(event), '--source-topic', self.source_topic],
            directory / 'execution.log', timeout=self.timeout, stop=self.stop)
        data = json.loads(event.read_text())
        if data['pipeline_status'] != 'COMPLETED':
            raise RuntimeError('pipeline_not_completed')
        result = {'decision': data['final_status'], 'inspected_at': data['finished_at'],
                  'defects': []}
        try:
            return prepare_result(data['report'], directory, request)
        except Exception as exc:
            print(f'Result preparation failed: {exc}', file=sys.stderr)
            result['details_ready'] = False
            return result, dict(ready=False, error='result_preparation_failed')


def handler(store, token):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.dispatch(True)

        def do_GET(self):
            self.dispatch(False)

        def dispatch(self, post):
            try:
                if not hmac.compare_digest(self.headers.get('Authorization', ''),
                                           'Bearer ' + token):
                    raise ApiError(401, 'unauthorized')
                parsed = urlsplit(self.path)
                query = parse_qs(parsed.query, keep_blank_values=True)
                parts = parsed.path.split('/')
                if parts[:4] != ['', 'api', 'v1', 'inspections']:
                    raise ApiError(404, 'not_found')
                if post:
                    if query:
                        raise ApiError(400, 'invalid_query')
                    if len(parts) != 4:
                        raise ApiError(404, 'not_found')
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 4096 or self.headers.get('Transfer-Encoding'):
                        raise ApiError(400, 'invalid_body_size')
                    self.connection.settimeout(5)
                    body = json.loads(self.rfile.read(size))
                    accepted = store.submit(body, self.headers.get('Idempotency-Key'))
                    data = store.get(accepted['inspection_id'])
                    self.reply(202, {'data': data})
                    return
                if len(parts) not in (5, 6):
                    raise ApiError(404, 'not_found')
                iid = str(uuid.UUID(parts[4]))
                data = store.get(iid)
                if len(parts) == 6:
                    if parts[5] != 'image':
                        raise ApiError(404, 'not_found')
                    if not data['image']['ready']:
                        raise ApiError(409, 'image_not_ready')
                    image_info = data['image']
                    if query:
                        if (set(query) != {'view','slot'} or query['view'] != ['countermeasure']
                                or len(query['slot']) != 1):
                            raise ApiError(400, 'invalid_image_view')
                        image_info = next((v for v in image_info.get('countermeasure_views',[])
                                           if v['slot_code']==query['slot'][0]), None)
                        if image_info is None:
                            raise ApiError(404, 'countermeasure_image_unavailable')
                    name = image_info.get('filename', IMAGE_NAME)
                    if Path(name).name != name or not name.endswith('.png'):
                        raise ApiError(409, 'image_integrity_error')
                    png = (store.root / iid / name).read_bytes()
                    if hashlib.sha256(png).hexdigest() != image_info['sha256']:
                        raise ApiError(409, 'image_integrity_error')
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/png')
                    self.send_header('Content-Disposition', f'inline; filename="{name}"')
                    self.send_header('Cache-Control', 'private, no-store')
                    self.send_header('Content-Length', str(len(png)))
                    self.send_header('X-Content-SHA256', image_info['sha256'])
                    self.end_headers()
                    self.wfile.write(png)
                    return
                if query:
                    raise ApiError(400, 'invalid_query')
                self.reply(200, {'data': data})
            except ApiError as exc:
                self.reply(exc.status, {'error': {'code': exc.code}})
            except (ValueError, TypeError, AttributeError):
                self.reply(400, {'error': {'code': 'invalid_request'}})
            except Exception:
                self.reply(500, {'error': {'code': 'internal_error'}})

        def reply(self, status, body):
            encoded = json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
    return Handler


def main():
    # Historical executable name now uses ROS too. HTTP helpers above remain
    # only for legacy fixtures; production launchers cannot open an HTTP port.
    from inspection_ros import main as ros_main
    ros_main()


if __name__ == '__main__':
    main()
