#!/usr/bin/env python3
"""Capture a fresh S22 PCB ROI and run whole-board PatchCore inspection."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CAPTURE = PROJECT_DIR / "run_s22_optical_inspection.sh"
DEFAULT_PREDICTOR = PROJECT_DIR / "vision_assembly/run_predict_component_patchcore.sh"
DEFAULT_WHOLE_PREDICTOR = PROJECT_DIR / "vision_assembly/run_predict_pcb_patchcore.sh"
DEFAULT_IMAGE = PROJECT_DIR / "runtime/inspection/s22_inspection_roi_latest.png"
DEFAULT_REPORT = (
    PROJECT_DIR
    / "runtime/inspection/patchcore/component_live_v3/component_patchcore_latest.json"
)
DEFAULT_OVERLAY = (
    PROJECT_DIR
    / "runtime/inspection/patchcore/component_live_v3/component_patchcore_latest.png"
)
DEFAULT_EVENT = (
    PROJECT_DIR / "runtime/inspection/patchcore/s22_component_inspection_latest.json"
)
DEFAULT_WHOLE_REPORT = (
    PROJECT_DIR / "runtime/inspection/patchcore/whole_live_v4/whole_patchcore_latest.json"
)
DEFAULT_WHOLE_VISUALIZATION = (
    PROJECT_DIR / "runtime/inspection/patchcore/whole_live_v4/whole_patchcore_latest.png"
)


class PipelineError(RuntimeError):
    """A stage failed or reused an old output."""


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _identity(path: Path) -> tuple[str, int, int] | None:
    try:
        resolved = path.resolve(strict=True)
        stat = resolved.stat()
    except FileNotFoundError:
        return None
    return str(resolved), int(stat.st_mtime_ns), int(stat.st_size)


def _resolved(path: Path) -> str | None:
    try:
        return str(path.resolve(strict=True))
    except FileNotFoundError:
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _run(label: str, command: list[str]) -> None:
    print(f"[S22 PATCHCORE] {label}: {' '.join(command)}", flush=True)
    completed = subprocess.run(command, check=False)
    if completed.returncode:
        raise PipelineError(f"{label} failed with exit code {completed.returncode}")


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    image = _absolute(args.image)
    report = _absolute(args.report)
    overlay = _absolute(args.overlay)
    whole_report = _absolute(args.whole_report)
    whole_visualization = _absolute(args.whole_visualization)
    event_path = _absolute(args.event_output)
    old_image = _identity(image)
    old_report = _identity(report) if args.with_components else None
    old_whole_report = _identity(whole_report)
    event: dict[str, Any] = {
        "schema_version": 1,
        "pipeline_status": "RUNNING",
        "inspection_status": "RUNNING",
        "started_at": datetime.now().astimezone().isoformat(),
        "finished_at": None,
        "roi_image": None,
        "report": None,
        "overlay": None,
        "whole_board_report": None,
        "whole_board_visualization": None,
        "component_inspection_enabled": bool(args.with_components),
        "error": None,
    }
    _write_json(event_path, event)

    try:
        if not args.skip_capture:
            _run("fresh optical capture", [str(args.capture_script)])
            if _identity(image) is None or _identity(image) == old_image:
                raise PipelineError("capture did not create a fresh PCB ROI")
        elif not image.is_file():
            raise PipelineError(f"PCB ROI does not exist: {image}")

        _run(
            "whole-board PatchCore inference",
            [str(args.whole_predictor_script), "--image", str(image)],
        )
        if _identity(whole_report) is None or _identity(whole_report) == old_whole_report:
            raise PipelineError("whole-board inference did not create a fresh report")
        if not whole_visualization.is_file():
            raise PipelineError("whole-board inference did not create a visualization")

        whole_result = json.loads(whole_report.read_text(encoding="utf-8"))
        result = None
        if args.with_components:
            _run(
                "optional 25-slot PatchCore inference",
                [str(args.predictor_script), "--image", str(image)],
            )
            if _identity(report) is None or _identity(report) == old_report:
                raise PipelineError("component inference did not create a fresh report")
            if not overlay.is_file():
                raise PipelineError(f"component overlay does not exist: {overlay}")
            result = json.loads(report.read_text(encoding="utf-8"))
        event.update({
            "pipeline_status": "COMPLETED",
            "inspection_status": whole_result.get(
                "status", "UNVERIFIED_BASELINE_ONLY"
            ),
            "whole_board_label": whole_result.get("predicted_label"),
            "whole_board_score": whole_result.get("anomaly_score"),
            "alignment": result.get("alignment") if result else None,
            "component_count": len(result.get("components", [])) if result else 0,
            "roi_image": _resolved(image),
            "report": _resolved(report) if result else None,
            "overlay": _resolved(overlay) if result else None,
            "whole_board_report": _resolved(whole_report),
            "whole_board_visualization": _resolved(whole_visualization),
            "finished_at": datetime.now().astimezone().isoformat(),
        })
        _write_json(event_path, event)
        return event
    except BaseException as exc:
        event.update({
            "pipeline_status": "ERROR",
            "inspection_status": "ERROR",
            "roi_image": _resolved(image),
            "report": _resolved(report),
            "overlay": _resolved(overlay),
            "whole_board_report": _resolved(whole_report),
            "whole_board_visualization": _resolved(whole_visualization),
            "finished_at": datetime.now().astimezone().isoformat(),
            "error": f"{type(exc).__name__}: {exc}",
        })
        _write_json(event_path, event)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture the current S22 board view and run whole-board PatchCore v4."
    )
    parser.add_argument("--capture-script", type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--predictor-script", type=Path, default=DEFAULT_PREDICTOR)
    parser.add_argument(
        "--whole-predictor-script", type=Path, default=DEFAULT_WHOLE_PREDICTOR
    )
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--overlay", type=Path, default=DEFAULT_OVERLAY)
    parser.add_argument("--whole-report", type=Path, default=DEFAULT_WHOLE_REPORT)
    parser.add_argument(
        "--whole-visualization", type=Path, default=DEFAULT_WHOLE_VISUALIZATION
    )
    parser.add_argument("--event-output", type=Path, default=DEFAULT_EVENT)
    parser.add_argument("--skip-capture", action="store_true")
    parser.add_argument(
        "--with-components", action="store_true",
        help="also run the experimental six-model/25-slot component inspection",
    )
    return parser.parse_args()


def main() -> int:
    try:
        event = run_pipeline(parse_args())
    except KeyboardInterrupt:
        return 130
    except BaseException as exc:
        print(f"[S22 PATCHCORE] ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"[S22 PATCHCORE] STATUS: {event['inspection_status']}")
    print(f"[S22 PATCHCORE] ROI: {event['roi_image']}")
    print(f"[S22 PATCHCORE] WHOLE BOARD: {event['whole_board_visualization']}")
    if event["component_inspection_enabled"]:
        print(f"[S22 PATCHCORE] COMPONENTS: {event['overlay']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
