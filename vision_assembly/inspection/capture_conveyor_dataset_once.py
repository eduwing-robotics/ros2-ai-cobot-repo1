#!/usr/bin/env python3
"""Archive one fresh S22 optical capture for later AOI model development.

This pipeline deliberately performs no defect classification.  Every capture
starts as ``unverified`` so a defective board can never silently become normal
anomaly-detection training data.  The conveyor trigger launches this program
after the inspection station has stopped.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

import cv2
import numpy as np


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CAPTURE = PROJECT_DIR / "run_s22_optical_inspection.sh"
DEFAULT_INSPECTION_DIR = PROJECT_DIR / "runtime/inspection"
DEFAULT_DATASET_ROOT = PROJECT_DIR / "runtime/datasets/s22_aoi"
DEFAULT_EVENT = DEFAULT_INSPECTION_DIR / "dataset_capture_latest.json"
DEFAULT_RAW = DEFAULT_INSPECTION_DIR / "s22_telephoto_latest.jpg"
DEFAULT_ROI = DEFAULT_INSPECTION_DIR / "s22_inspection_roi_latest.png"
DEFAULT_ROI_METADATA = DEFAULT_INSPECTION_DIR / "s22_inspection_roi_latest.json"
DEFAULT_UPRIGHT = DEFAULT_INSPECTION_DIR / "s22_telephoto_upright_latest.png"
DEFAULT_DEBUG = DEFAULT_INSPECTION_DIR / "s22_inspection_roi_debug_latest.jpg"


class CaptureError(RuntimeError):
    """A capture did not produce one complete fresh sample."""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def file_identity(path: Path) -> tuple[str, int, int] | None:
    try:
        resolved = path.resolve(strict=True)
        stat = resolved.stat()
    except FileNotFoundError:
        return None
    return str(resolved), int(stat.st_mtime_ns), int(stat.st_size)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def safe_name(value: str, field: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", normalized):
        raise CaptureError(
            f"{field} must contain only letters, numbers, '.', '_' or '-': {value}"
        )
    return normalized


def known_defects_from(value: str) -> list[str]:
    defects: list[str] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        normalized = safe_name(item, "known defect")
        if normalized not in defects:
            defects.append(normalized)
    return defects


def run_capture(script: Path) -> None:
    environment = os.environ.copy()
    # This dataset recipe is intentionally fixed after the controlled A/B test
    # on 2026-08-31.  Samsung's still-photo flash has no usable intensity
    # control and emphasized harmless 3D-print texture.
    environment["S22_INSPECTION_FLASH"] = "off"
    environment.setdefault("S22_INSPECTION_ZOOM", "3.5")
    print(f"[S22 DATASET] Capture: {script}", flush=True)
    completed = subprocess.run([str(script)], check=False, env=environment)
    if completed.returncode != 0:
        raise CaptureError(
            f"S22 optical capture failed with exit code {completed.returncode}"
        )


def hardlink_or_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def image_quality(path: Path) -> dict[str, Any]:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise CaptureError(f"OpenCV could not decode the rectified ROI: {path}")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return {
        "width_px": int(image.shape[1]),
        "height_px": int(image.shape[0]),
        "gray_mean": round(float(gray.mean()), 4),
        "gray_std": round(float(gray.std()), 4),
        "gray_p01": int(np.percentile(gray, 1)),
        "gray_p50": int(np.percentile(gray, 50)),
        "gray_p99": int(np.percentile(gray, 99)),
        "any_channel_ge_250_percent": round(
            float((image.max(axis=2) >= 250).mean() * 100.0), 6
        ),
        "all_channels_ge_250_percent": round(
            float((image.min(axis=2) >= 250).mean() * 100.0), 6
        ),
        "gray_le_5_percent": round(float((gray <= 5).mean() * 100.0), 6),
        "laplacian_variance": round(
            float(cv2.Laplacian(gray, cv2.CV_64F).var()), 4
        ),
    }


def capture_id_from(path: Path) -> str:
    match = re.search(r"(\d{8}_\d{6})", path.name)
    return match.group(1) if match else datetime.now().strftime("%Y%m%d_%H%M%S")


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "raw": absolute_path(args.raw),
        "roi": absolute_path(args.roi),
        "roi_metadata": absolute_path(args.roi_metadata),
        "upright": absolute_path(args.upright),
        "debug": absolute_path(args.debug),
    }
    old_identities = {name: file_identity(path) for name, path in paths.items()}
    event_path = absolute_path(args.event_output)
    event: dict[str, Any] = {
        "schema_version": 1,
        "pipeline_status": "RUNNING",
        "final_status": "RUNNING",
        "source_topic": args.source_topic,
        "started_at": now_iso(),
        "finished_at": None,
        "dataset_split": args.split,
        "lighting_condition": args.lighting,
        "board_state": args.board_state,
        "known_defects": list(args.known_defects),
        "manifest": None,
        "report": None,
        "roi_image": None,
        "error": None,
    }
    write_json(event_path, event)

    try:
        run_capture(absolute_path(args.capture_script))
        resolved: dict[str, Path] = {}
        for name, path in paths.items():
            identity = file_identity(path)
            if identity is None:
                raise CaptureError(f"capture did not produce {name}: {path}")
            if identity == old_identities[name]:
                raise CaptureError(f"capture left stale {name} output: {path}")
            resolved[name] = path.resolve(strict=True)

        roi_metadata = json.loads(
            resolved["roi_metadata"].read_text(encoding="utf-8")
        )
        capture_id = capture_id_from(resolved["roi"])
        date_folder = capture_id[:8]
        session_dir = (
            absolute_path(args.dataset_root)
            / args.split
            / args.lighting
            / date_folder
        )
        archive_dirs = {
            "raw": session_dir / "raw",
            "roi": session_dir / "roi",
            "roi_metadata": session_dir / "roi_metadata",
            "upright": session_dir / "upright",
            "debug": session_dir / "debug",
        }
        archived: dict[str, str] = {}
        for name, source in resolved.items():
            destination = archive_dirs[name] / source.name
            hardlink_or_copy(source, destination)
            archived[name] = str(destination)

        manifest_path = session_dir / "manifests" / f"{capture_id}.json"
        manifest = {
            "schema_version": 1,
            "capture_id": capture_id,
            "captured_at": now_iso(),
            "classification": "UNVERIFIED",
            "normal_training_allowed": False,
            "review_required": True,
            "board_annotation": {
                "state": args.board_state,
                "known_defects": list(args.known_defects),
                "human_verified": False,
            },
            "source_topic": args.source_topic,
            "camera_recipe": {
                "camera": "Samsung Galaxy S22 telephoto",
                "optical_zoom": "3.5x",
                "flash": "off",
                "lighting_condition": args.lighting,
                "inspection_station": "conveyor_vision_inspection",
            },
            "dataset": {
                "root": str(absolute_path(args.dataset_root)),
                "split": args.split,
                "session_directory": str(session_dir),
            },
            "quality": image_quality(resolved["roi"]),
            "board_detection": roi_metadata.get("detector", {}),
            "source_files": {name: str(path) for name, path in resolved.items()},
            "archived_files": archived,
            "notes": [
                "No OpenCV or AI defect verdict was executed.",
                "Keep this sample out of normal training until a human verifies every component.",
                "A known-defect tag records operator knowledge; it is not an automated verdict.",
            ],
        }
        write_json(manifest_path, manifest)
        append_jsonl(session_dir / "index.jsonl", manifest)

        event.update(
            {
                "pipeline_status": "COMPLETED",
                "final_status": "CAPTURED_UNVERIFIED",
                "finished_at": now_iso(),
                "manifest": str(manifest_path),
                "report": str(manifest_path),
                "roi_image": archived["roi"],
            }
        )
        write_json(event_path, event)
        return event
    except BaseException as exc:
        event.update(
            {
                "pipeline_status": "ERROR",
                "final_status": "ERROR",
                "finished_at": now_iso(),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        write_json(event_path, event)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture one S22 board image at the conveyor inspection stop and "
            "archive it as UNVERIFIED without running a defect verdict."
        )
    )
    parser.add_argument("--capture-script", type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--roi", type=Path, default=DEFAULT_ROI)
    parser.add_argument("--roi-metadata", type=Path, default=DEFAULT_ROI_METADATA)
    parser.add_argument("--upright", type=Path, default=DEFAULT_UPRIGHT)
    parser.add_argument("--debug", type=Path, default=DEFAULT_DEBUG)
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument(
        "--split", default=os.environ.get("S22_DATASET_SPLIT", "unverified")
    )
    parser.add_argument(
        "--lighting",
        default=os.environ.get("S22_LIGHTING_CONDITION", "ambient_unclassified"),
    )
    parser.add_argument(
        "--board-state",
        choices=("unknown", "known_defect", "normal_candidate"),
        default=os.environ.get("S22_BOARD_STATE", "unknown"),
        help=(
            "operator-provided state; all captures remain unverified regardless "
            "of this value"
        ),
    )
    parser.add_argument(
        "--known-defects",
        default=os.environ.get("S22_KNOWN_DEFECTS", ""),
        help="comma-separated operator tags, for example missing_smd",
    )
    parser.add_argument("--event-output", type=Path, default=DEFAULT_EVENT)
    parser.add_argument("--source-topic", default="manual")
    args = parser.parse_args()
    args.split = safe_name(args.split, "split")
    args.lighting = safe_name(args.lighting, "lighting")
    args.known_defects = known_defects_from(args.known_defects)
    if args.board_state == "known_defect" and not args.known_defects:
        parser.error("--board-state known_defect requires --known-defects")
    if args.board_state != "known_defect" and args.known_defects:
        parser.error("--known-defects requires --board-state known_defect")
    return args


def main() -> int:
    args = parse_args()
    try:
        event = run_pipeline(args)
    except KeyboardInterrupt:
        print("[S22 DATASET] Interrupted.", flush=True)
        return 130
    except BaseException as exc:
        print(f"[S22 DATASET] ERROR: {exc}", flush=True)
        return 1
    print(
        f"[S22 DATASET] RESULT: {event['final_status']}\n"
        f"[S22 DATASET] ROI: {event['roi_image']}\n"
        f"[S22 DATASET] MANIFEST: {event['manifest']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
