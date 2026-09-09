from argparse import Namespace
import json
from pathlib import Path

import capture_and_predict_component_patchcore as pipeline


def _args(tmp_path, **overrides):
    values = dict(
        image=tmp_path / "latest.png", report=tmp_path / "report.json",
        overlay=tmp_path / "overlay.png", event_output=tmp_path / "event.json",
        whole_report=tmp_path / "whole.json",
        whole_visualization=tmp_path / "whole.png",
        capture_script=Path("capture"), predictor_script=Path("predict"),
        whole_predictor_script=Path("predict-whole"), skip_capture=False,
        with_components=False,
    )
    values.update(overrides)
    return Namespace(**values)


def test_pipeline_requires_fresh_capture(monkeypatch, tmp_path):
    image = tmp_path / "latest.png"
    image.write_bytes(b"old")
    monkeypatch.setattr(pipeline, "_run", lambda *_: None)
    args = _args(tmp_path, image=image)
    try:
        pipeline.run_pipeline(args)
    except pipeline.PipelineError as exc:
        assert "fresh PCB ROI" in str(exc)
    else:
        raise AssertionError("stale capture was accepted")
    assert json.loads(args.event_output.read_text())["pipeline_status"] == "ERROR"


def test_pipeline_records_whole_board_only_by_default(monkeypatch, tmp_path):
    image = tmp_path / "latest.png"
    report = tmp_path / "report.json"
    overlay = tmp_path / "overlay.png"
    whole_report = tmp_path / "whole.json"
    whole_visualization = tmp_path / "whole.png"

    def fake_run(label, _command):
        if "capture" in label:
            image.write_bytes(b"new")
        elif "whole-board" in label:
            whole_report.write_text(json.dumps({"status": "UNVERIFIED_BASELINE_ONLY"}))
            whole_visualization.write_bytes(b"png")
        else:
            raise AssertionError("component inference should be disabled by default")

    monkeypatch.setattr(pipeline, "_run", fake_run)
    args = _args(
        tmp_path, image=image, report=report, overlay=overlay,
        whole_report=whole_report, whole_visualization=whole_visualization,
    )
    event = pipeline.run_pipeline(args)
    assert event["pipeline_status"] == "COMPLETED"
    assert event["component_count"] == 0
    assert event["component_inspection_enabled"] is False
    assert event["whole_board_visualization"] == str(whole_visualization.resolve())


def test_pipeline_can_enable_component_prediction(monkeypatch, tmp_path):
    image = tmp_path / "latest.png"
    report = tmp_path / "report.json"
    overlay = tmp_path / "overlay.png"
    whole_report = tmp_path / "whole.json"
    whole_visualization = tmp_path / "whole.png"

    def fake_run(label, _command):
        if "capture" in label:
            image.write_bytes(b"new")
        elif "whole-board" in label:
            whole_report.write_text(json.dumps({"status": "UNVERIFIED_BASELINE_ONLY"}))
            whole_visualization.write_bytes(b"png")
        else:
            report.write_text(json.dumps({
                "status": "UNVERIFIED_SCORE_ONLY", "alignment": {"score": 0.99},
                "components": [{}] * 25,
            }))
            overlay.write_bytes(b"png")

    monkeypatch.setattr(pipeline, "_run", fake_run)
    args = _args(
        tmp_path, image=image, report=report, overlay=overlay,
        whole_report=whole_report, whole_visualization=whole_visualization,
        with_components=True,
    )
    event = pipeline.run_pipeline(args)
    assert event["pipeline_status"] == "COMPLETED"
    assert event["component_count"] == 25
    assert event["component_inspection_enabled"] is True
    assert event["whole_board_visualization"] == str(whole_visualization.resolve())
