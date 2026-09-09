"""Store + real retry pipeline with fake camera/inference, no network/hardware."""
import argparse
import json
from pathlib import Path
import sys
import threading

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_inspection_api import api, request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'inspection'))
import triggered_inspection_once as pipeline


@pytest.mark.parametrize('second_decision', ['UNKNOWN', 'PASS', 'FAIL'])
def test_same_request_owns_two_attempts_and_duplicate_never_recaptures(tmp_path, monkeypatch, second_decision):
    monkeypatch.setenv('KSMC_VISION_EXPORT', '0')
    monkeypatch.delenv('KSMC_VISION_CONTEXT_FILE', raising=False)
    retry_started, release = threading.Event(), threading.Event()
    calls, events, requests = [], [], []
    args = argparse.Namespace(capture_script=tmp_path/'capture', inspector_script=tmp_path/'inspect',
        image=tmp_path/'roi.png', report=tmp_path/'report.json', debug_image=tmp_path/'debug.png',
        event_output=tmp_path/'event.json', source_topic='mock_sequencer', skip_capture=False,
        unknown_recaptures=1)

    def stage(label, command):
        if label == 'S22 optical capture':
            calls.append(label)
            if len(calls) == 2:
                retry_started.set()
                if not release.wait(3):
                    raise RuntimeError('Test release timed out')
            image = tmp_path/f'capture_{len(calls)}.png'
            image.write_bytes(str(len(calls)).encode())
            args.image.unlink(missing_ok=True)
            args.image.symlink_to(image)
        else:
            report = tmp_path/f'report_{len(calls)}.json'
            report.write_text(json.dumps({'status': 'UNKNOWN' if len(calls) == 1 else second_decision,
                                          'input_image': command[-1]}))
            args.report.unlink(missing_ok=True)
            args.report.symlink_to(report)

    def run(req, directory):
        requests.append(dict(req))
        args.event_output = directory/'event.json'
        event = pipeline.run_pipeline(args)
        events.append(event)
        # Public transport keeps UNKNOWN/PASS/FAIL; HOLD is not a new enum.
        return {'decision': event['final_status']}, {'ready': False}

    monkeypatch.setattr(pipeline, 'run_stage', stage)
    store = api.Store(tmp_path/'store', lambda: True, run)
    req = request()
    store.submit(req, req['inspection_id'])
    try:
        assert retry_started.wait(3)
        duplicate = store.submit(dict(req), req['inspection_id'])
        assert duplicate['status'] == 'RUNNING'
        assert 'result' not in duplicate
        other = request()
        with pytest.raises(api.ApiError) as caught:
            store.submit(other, other['inspection_id'])
        assert caught.value.code == 'inspection_busy'
    finally:
        release.set()
        store.thread.join(timeout=5)
    assert not store.thread.is_alive()
    final = store.get(req['inspection_id'])
    assert all(final[k] == v for k, v in req.items())
    assert final['status'] == 'COMPLETED'
    assert final['result']['decision'] == second_decision
    assert requests == [req]
    assert len(calls) == 2
    assert len(events[0]['attempts']) == 2
    assert events[0]['attempts'][0]['roi_image'] != events[0]['attempts'][1]['roi_image']
    assert events[0]['recommended_action'] == ('HOLD' if second_decision == 'UNKNOWN' else 'NONE')
    restarted = api.Store(tmp_path/'store', lambda: False, run)
    assert restarted.submit(req, req['inspection_id'])['status'] == 'COMPLETED'
    assert len(calls) == 2


@pytest.mark.parametrize('failure', ['capture_error', 'stale_capture', 'invalid_decision'])
def test_retry_failure_is_failed_not_completed_and_replay_never_captures(tmp_path, monkeypatch, failure):
    monkeypatch.setenv('KSMC_VISION_EXPORT', '0')
    monkeypatch.delenv('KSMC_VISION_CONTEXT_FILE', raising=False)
    args = argparse.Namespace(capture_script=tmp_path/'capture', inspector_script=tmp_path/'inspect',
        image=tmp_path/'roi.png', report=tmp_path/'report.json', debug_image=tmp_path/'debug.png',
        event_output=tmp_path/'event.json', source_topic='mock_sequencer', skip_capture=False,
        unknown_recaptures=1)
    captures = []

    def stage(label, command):
        if label == 'S22 optical capture':
            captures.append(label)
            if len(captures) == 2:
                if failure == 'capture_error':
                    raise pipeline.PipelineError('simulated capture failure')
                if failure == 'stale_capture':
                    return
            image = tmp_path/f'capture_{len(captures)}.png'
            image.write_bytes(str(len(captures)).encode())
            args.image.unlink(missing_ok=True)
            args.image.symlink_to(image)
        else:
            report = tmp_path/f'report_{len(captures)}.json'
            report.write_text(json.dumps({'status': 'UNKNOWN' if len(captures) == 1 else 'BOGUS',
                                          'input_image': command[-1]}))
            args.report.unlink(missing_ok=True)
            args.report.symlink_to(report)

    def run(req, directory):
        args.event_output = directory/'event.json'
        event = pipeline.run_pipeline(args)
        # Mirror Runner's completion gate, without starting its hardware child.
        if event['pipeline_status'] != 'COMPLETED':
            raise RuntimeError('pipeline_not_completed')
        return {'decision': event['final_status']}, {'ready': False}

    monkeypatch.setattr(pipeline, 'run_stage', stage)
    store = api.Store(tmp_path/'store', lambda: True, run)
    req = request()
    store.submit(req, req['inspection_id'])
    store.thread.join(timeout=5)
    assert not store.thread.is_alive()
    final = store.get(req['inspection_id'])
    assert final['status'] == 'FAILED'
    assert 'result' not in final
    assert all(final[k] == value for k, value in req.items())
    event = json.loads(args.event_output.read_text())
    assert event['pipeline_status'] == 'ERROR'
    assert len(event['attempts']) == 1
    assert event['attempts'][0]['final_status'] == 'UNKNOWN'
    assert len(captures) == 2
    restarted = api.Store(tmp_path/'store', lambda: True, run)
    assert restarted.submit(req, req['inspection_id'])['status'] == 'FAILED'
    assert len(captures) == 2
