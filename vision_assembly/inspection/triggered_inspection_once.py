#!/usr/bin/env python3
"""Capture one S22 optical image and run the full-board inspection.

The conveyor trigger node launches this program in a child process.  Keeping
the physical camera hand-off and the CPU-heavy inspection outside the ROS
callback process prevents either operation from delaying stop-trigger traffic.
"""

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
DEFAULT_INSPECTOR = PROJECT_DIR / "vision_assembly/run_hybrid_fixed_slot_inspection.sh"
DEFAULT_IMAGE = PROJECT_DIR / "runtime/inspection/s22_inspection_roi_latest.png"
DEFAULT_REPORT = (
    PROJECT_DIR
    / "runtime/inspection/hybrid_fixed_slot/hybrid_report_latest.json"
)
DEFAULT_DEBUG_IMAGE = (
    PROJECT_DIR / "runtime/inspection/hybrid_fixed_slot/hybrid_report_latest.png"
)
DEFAULT_EVENT = PROJECT_DIR / "runtime/inspection/auto_inspection_latest.json"


class PipelineError(RuntimeError):
    """An automatic capture or inspection stage did not produce fresh output."""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def absolute_path(path: Path) -> Path:
    """Make a path absolute without resolving a rotating ``latest`` symlink."""
    return Path(os.path.abspath(path.expanduser()))


def file_identity(path: Path) -> tuple[str, int, int] | None:
    """Return enough identity information to reject a stale ``latest`` link."""
    try:
        resolved = path.resolve(strict=True)
        stat = resolved.stat()
    except FileNotFoundError:
        return None
    return str(resolved), int(stat.st_mtime_ns), int(stat.st_size)


def resolved_string(path: Path) -> str | None:
    try:
        return str(path.resolve(strict=True))
    except FileNotFoundError:
        return None


def write_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(event, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def run_stage(label: str, command: list[str]) -> None:
    print(f"[AUTO INSPECTION] {label}: {' '.join(command)}", flush=True)
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise PipelineError(
            f"{label} failed with exit code {completed.returncode}"
        )


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    # These paths intentionally remain unresolved.  Capture and inspection
    # atomically repoint their ``latest`` symlinks; resolving here would pin
    # the pipeline to the previous image/report target.
    image_path = absolute_path(args.image)
    report_path = absolute_path(args.report)
    debug_image_path = absolute_path(args.debug_image)
    event_path = absolute_path(args.event_output)
    started_at = now_iso()
    # Snapshot an optional context once, before capture. Never infer a Unit
    # from a mutable latest-job query or reuse another board's production ID.
    context = {}
    context_file = os.environ.get('KSMC_VISION_CONTEXT_FILE')
    if context_file:
        context = json.loads(Path(context_file).read_text())
        if not isinstance(context, dict):
            raise PipelineError('Vision context must be an object')
    event: dict[str, Any] = {
        "schema_version": 1,
        "pipeline_status": "RUNNING",
        "final_status": "RUNNING",
        "source_topic": args.source_topic,
        "started_at": started_at,
        "finished_at": None,
        "roi_image": None,
        "report": None,
        "debug_image": None,
        "error": None,
    }
    write_event(event_path, event)

    def inspect_attempt():
        old_image = file_identity(image_path)
        old_report = file_identity(report_path)
        if not args.skip_capture:
            run_stage("S22 optical capture", [str(args.capture_script)])
            new_image = file_identity(image_path)
            if new_image is None:
                raise PipelineError(
                    f"capture completed without a PCB ROI: {image_path}"
                )
            if new_image == old_image:
                raise PipelineError(
                    f"capture left the previous PCB ROI unchanged: {image_path}"
                )
        elif not image_path.is_file():
            raise PipelineError(f"inspection image does not exist: {image_path}")

        captured_image = image_path.resolve(strict=True)
        run_stage(
            "full-board inspection",
            [str(args.inspector_script), "--image", str(captured_image)],
        )
        new_report = file_identity(report_path)
        if new_report is None:
            raise PipelineError(
                f"inspection completed without a JSON report: {report_path}"
            )
        if new_report == old_report:
            raise PipelineError(
                f"inspection left the previous JSON report unchanged: {report_path}"
            )

        captured_report = report_path.resolve(strict=True)
        report = json.loads(captured_report.read_text(encoding="utf-8"))
        if report.get('input_image') and Path(report['input_image']).resolve() != captured_image:
            raise PipelineError('Inspection report belongs to a different capture')
        final_status = str(report.get("final_status", report.get("status", "ERROR")))
        if final_status not in ('PASS', 'FAIL', 'UNKNOWN'):
            raise PipelineError('Invalid inspection decision')
        return report, final_status, captured_image, captured_report

    try:
        retries = getattr(args, 'unknown_recaptures', 1)
        if retries not in (0, 1):
            raise PipelineError('unknown_recaptures must be 0 or 1')
        # Offline inspection must never unexpectedly turn on the camera.
        retries = 0 if args.skip_capture else retries
        event['attempts'] = []
        for attempt in range(1, retries + 2):
            report, final_status, captured_image, captured_report = inspect_attempt()
            event['attempts'].append(dict(attempt=attempt, final_status=final_status,
                roi_image=str(captured_image), report=str(captured_report), finished_at=now_iso()))
            write_event(event_path, event)
            if final_status != 'UNKNOWN' or attempt == retries + 1:
                break
        event['recommended_action'] = 'HOLD' if final_status == 'UNKNOWN' else 'NONE'
        event['hold_command_sent'] = False
        event.update(
            {
                "pipeline_status": "COMPLETED",
                "final_status": final_status,
                "s22_visible_status": report.get("s22_visible_status"),
                "roi_image": str(captured_image),
                "report": str(captured_report),
                "debug_image": resolved_string(debug_image_path),
                "finished_at": now_iso(),
            }
        )
        # Delivery is a separate outcome: an upload failure must not re-decide
        # the inspection or lose the local evidence. No motion is sent here.
        if os.environ.get('KSMC_VISION_EXPORT', '0') == '1':
            sys.path.insert(0, str(PROJECT_DIR / 'vision_assembly/integration'))
            from export_inspection_result import build_package, DEFAULT_CONFIG, DEFAULT_OUTBOX
            try:
                package, archive, payload = build_package(captured_report, DEFAULT_CONFIG, DEFAULT_OUTBOX,
                    job_id=context.get('job_id'), unit_id=context.get('unit_id'),
                    production_cycle_id=context.get('production_cycle_id'), board_id=context.get('board_id'))
                event['delivery'] = dict(status='LOCAL_ONLY', package=str(package),
                    archive=str(archive), inspection_id=payload['inspection_id'])
                # Production evidence is pulled by Sequencer, never uploaded
                # directly to MainServer. Legacy endpoint environment is ignored.
            except Exception as exc:
                event.setdefault('delivery', {})
                event['delivery'].update(status='PENDING_RETRY', error=f'{type(exc).__name__}: {exc}')
        write_event(event_path, event)
        return event
    except BaseException as exc:
        event.update(
            {
                "pipeline_status": "ERROR",
                "final_status": "ERROR",
                "roi_image": resolved_string(image_path),
                "report": resolved_string(report_path),
                "debug_image": resolved_string(debug_image_path),
                "finished_at": now_iso(),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        write_event(event_path, event)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Take one true-optical S22 board photo, extract its PCB ROI, and "
            "run the full-board inspection."
        )
    )
    parser.add_argument("--capture-script", type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--inspector-script", type=Path, default=DEFAULT_INSPECTOR)
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--debug-image", type=Path, default=DEFAULT_DEBUG_IMAGE)
    parser.add_argument("--event-output", type=Path, default=DEFAULT_EVENT)
    parser.add_argument('--unknown-recaptures', type=int, choices=(0, 1), default=1,
                        help='Additional optical capture on UNKNOWN; skipped with --skip-capture.')
    parser.add_argument(
        "--source-topic",
        default="manual",
        help="trigger source recorded in the event JSON",
    )
    parser.add_argument(
        "--skip-capture",
        action="store_true",
        help="inspect the current ROI without controlling the phone (test/manual use)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        event = run_pipeline(args)
    except KeyboardInterrupt:
        print("[AUTO INSPECTION] Interrupted.", file=sys.stderr)
        return 130
    except BaseException as exc:
        print(f"[AUTO INSPECTION] ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"[AUTO INSPECTION] RESULT: {event['final_status']}\n"
        f"[AUTO INSPECTION] ROI: {event['roi_image']}\n"
        f"[AUTO INSPECTION] REPORT: {event['report']}\n"
        f"[AUTO INSPECTION] DEBUG: {event['debug_image']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
