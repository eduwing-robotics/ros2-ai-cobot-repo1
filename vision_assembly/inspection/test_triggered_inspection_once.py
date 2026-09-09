import argparse
import json
from pathlib import Path
import sys
import pytest


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import triggered_inspection_once as pipeline  # noqa: E402


def _args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        capture_script=tmp_path / "capture.sh",
        inspector_script=tmp_path / "inspect.sh",
        image=tmp_path / "roi_latest.png",
        report=tmp_path / "report_latest.json",
        debug_image=tmp_path / "debug_latest.png",
        event_output=tmp_path / "event.json",
        source_topic="/test/inspection_trigger",
        skip_capture=False,
        unknown_recaptures=0,
    )


def _rotate_link(link: Path, target: Path) -> None:
    link.unlink(missing_ok=True)
    link.symlink_to(target)


def test_pipeline_follows_new_latest_symlinks(monkeypatch, tmp_path):
    args = _args(tmp_path)
    old_image = tmp_path / "roi_old.png"
    old_image.write_bytes(b"old image")
    _rotate_link(args.image, old_image)
    old_report = tmp_path / "report_old.json"
    old_report.write_text('{"final_status":"OLD"}\n', encoding="utf-8")
    _rotate_link(args.report, old_report)

    def fake_stage(label, _command):
        if label == "S22 optical capture":
            new_image = tmp_path / "roi_new.png"
            new_image.write_bytes(b"new image")
            _rotate_link(args.image, new_image)
        else:
            new_report = tmp_path / "report_new.json"
            new_report.write_text(
                json.dumps(
                    {"final_status": "PASS", "s22_visible_status": "PASS"}
                ),
                encoding="utf-8",
            )
            _rotate_link(args.report, new_report)
            args.debug_image.write_bytes(b"debug")

    monkeypatch.setattr(pipeline, "run_stage", fake_stage)
    event = pipeline.run_pipeline(args)

    assert event["pipeline_status"] == "COMPLETED"
    assert event["final_status"] == "PASS"
    assert event["roi_image"].endswith("roi_new.png")
    assert event["report"].endswith("report_new.json")
    assert json.loads(args.event_output.read_text(encoding="utf-8")) == event


def test_stale_capture_output_is_an_operational_error(monkeypatch, tmp_path):
    args = _args(tmp_path)
    image = tmp_path / "roi_old.png"
    image.write_bytes(b"unchanged")
    _rotate_link(args.image, image)

    monkeypatch.setattr(pipeline, "run_stage", lambda _label, _command: None)
    try:
        pipeline.run_pipeline(args)
    except pipeline.PipelineError as exc:
        assert "previous PCB ROI unchanged" in str(exc)
    else:
        raise AssertionError("stale capture output should fail")

    event = json.loads(args.event_output.read_text(encoding="utf-8"))
    assert event["pipeline_status"] == "ERROR"
    assert event["final_status"] == "ERROR"


def test_delivery_failure_does_not_change_inspection(monkeypatch, tmp_path):
    sys.path.insert(0, str(MODULE_DIR.parent / 'integration'))
    import export_inspection_result as exporter
    args = _args(tmp_path)
    monkeypatch.setenv('KSMC_VISION_EXPORT', '1')
    monkeypatch.delenv('KSMC_VISION_CONTEXT_FILE', raising=False)
    def stage(label, command):
        if label == 'S22 optical capture':
            args.image.write_bytes(b'fresh')
        else:
            args.report.write_text(json.dumps({'status':'UNKNOWN','input_image':str(args.image)}))
    def fail(*args, **kwargs):
        raise exporter.ExportError('simulated unavailable storage')
    monkeypatch.setattr(pipeline, 'run_stage', stage)
    monkeypatch.setattr(exporter, 'build_package', fail)
    event = pipeline.run_pipeline(args)
    assert event['pipeline_status']=='COMPLETED'
    assert event['final_status']=='UNKNOWN'
    assert event['delivery']['status']=='PENDING_RETRY'


@pytest.mark.parametrize('decisions,expected,captures', [
    (['UNKNOWN', 'UNKNOWN'], 'UNKNOWN', 2),
    (['UNKNOWN', 'PASS'], 'PASS', 2),
    (['UNKNOWN', 'FAIL'], 'FAIL', 2),
    (['FAIL'], 'FAIL', 1),
    (['PASS'], 'PASS', 1),
])
def test_bounded_unknown_recapture(monkeypatch, tmp_path, decisions, expected, captures):
    args = _args(tmp_path)
    args.unknown_recaptures = 1
    monkeypatch.setenv('KSMC_VISION_EXPORT', '0')
    monkeypatch.delenv('KSMC_VISION_CONTEXT_FILE', raising=False)
    calls = []
    def stage(label, command):
        if label == 'S22 optical capture':
            calls.append(label)
            image = tmp_path / f'image_{len(calls)}.png'
            image.write_bytes(str(len(calls)).encode())
            _rotate_link(args.image, image)
        else:
            report = tmp_path / f'report_{len(calls)}.json'
            report.write_text(json.dumps({'status': decisions[len(calls)-1],
                                         'input_image': command[-1]}))
            _rotate_link(args.report, report)
    monkeypatch.setattr(pipeline, 'run_stage', stage)
    event = pipeline.run_pipeline(args)
    assert len(calls) == captures
    assert len(event['attempts']) == captures
    assert event['final_status'] == expected
    assert event['recommended_action'] == ('HOLD' if expected == 'UNKNOWN' else 'NONE')
    assert not event['hold_command_sent']


def test_offline_unknown_does_not_recapture(monkeypatch, tmp_path):
    args = _args(tmp_path)
    args.unknown_recaptures = 1
    args.skip_capture = True
    args.image.write_bytes(b'existing')
    monkeypatch.setenv('KSMC_VISION_EXPORT', '0')
    monkeypatch.delenv('KSMC_VISION_CONTEXT_FILE', raising=False)
    calls = []
    def stage(label, command):
        calls.append(label)
        args.report.write_text(json.dumps({'status': 'UNKNOWN', 'input_image': command[-1]}))
    monkeypatch.setattr(pipeline, 'run_stage', stage)
    event = pipeline.run_pipeline(args)
    assert calls == ['full-board inspection']
    assert event['final_status'] == 'UNKNOWN'
    assert len(event['attempts']) == 1


def test_stale_retry_does_not_reuse_first_result(monkeypatch, tmp_path):
    args = _args(tmp_path)
    args.unknown_recaptures = 1
    monkeypatch.setenv('KSMC_VISION_EXPORT', '0')
    monkeypatch.delenv('KSMC_VISION_CONTEXT_FILE', raising=False)
    captures = []
    def stage(label, command):
        if label == 'S22 optical capture':
            captures.append(label)
            if len(captures) == 1:
                args.image.write_bytes(b'first')
        else:
            args.report.write_text(json.dumps({'status': 'UNKNOWN', 'input_image': command[-1]}))
    monkeypatch.setattr(pipeline, 'run_stage', stage)
    with pytest.raises(pipeline.PipelineError, match='previous PCB ROI unchanged'):
        pipeline.run_pipeline(args)
    event = json.loads(args.event_output.read_text())
    assert event['pipeline_status'] == 'ERROR'
    assert len(event['attempts']) == 1
