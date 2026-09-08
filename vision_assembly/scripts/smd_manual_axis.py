#!/usr/bin/env python3
"""Load and validate operator-clicked SMD terminal axes."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np


def default_manual_axis_path(project_root: Path, set_index: int) -> Path:
    return project_root / "vision_assembly" / "data" / f"smd_manual_axes_set{set_index}.json"


def directed_axis_angle_deg(first: np.ndarray, second: np.ndarray) -> float:
    delta = np.asarray(second, dtype=float) - np.asarray(first, dtype=float)
    if delta.shape != (2,) or not np.all(np.isfinite(delta)):
        raise ValueError("manual SMD terminal axis must contain two finite points")
    if float(np.linalg.norm(delta)) < 12.0:
        raise ValueError("manual SMD terminal clicks are too close together")
    return (math.degrees(math.atan2(float(delta[1]), float(delta[0]))) + 180.0) % 360.0 - 180.0


def canonical_axis_angle_deg(directed_angle: float) -> float:
    return (float(directed_angle) + 90.0) % 180.0 - 90.0


def load_manual_axes(
    path: Path,
    *,
    set_index: int,
    canonical_size: tuple[int, int],
    required_count: int,
    max_age_sec: float,
) -> dict:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"manual SMD axis file is missing: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read manual SMD axes: {exc}") from exc
    if payload.get("mode") != "operator_two_terminal_axes":
        raise ValueError("manual SMD axis file has an unsupported mode")
    if int(payload.get("set_index", -1)) != int(set_index):
        raise ValueError("manual SMD axis set does not match the selected set")
    if [int(value) for value in payload.get("canonical_size", [])] != list(canonical_size):
        raise ValueError("manual SMD axis canonical image size changed")
    age = time.time() - float(payload.get("timestamp_unix", 0.0))
    if age < -5.0 or age > float(max_age_sec):
        raise ValueError(f"manual SMD axes are stale ({age:.1f} s)")
    parts = payload.get("parts", [])
    if len(parts) != int(required_count):
        raise ValueError(
            f"manual SMD axes contain {len(parts)} parts; expected {required_count}"
        )
    by_instance = {}
    for part in parts:
        instance = int(part["instance_index"])
        endpoints = np.asarray(part["terminal_endpoints_canonical_pixel"], dtype=float)
        center = np.asarray(part["detection_center_canonical_pixel"], dtype=float)
        if endpoints.shape != (2, 2) or center.shape != (2,):
            raise ValueError(f"manual SMD axis {instance} has invalid point dimensions")
        angle = directed_axis_angle_deg(endpoints[0], endpoints[1])
        saved_angle = float(part["directed_axis_canonical_deg"])
        delta = abs((angle - saved_angle + 180.0) % 360.0 - 180.0)
        if delta > 0.1:
            raise ValueError(f"manual SMD axis {instance} angle does not match its points")
        if instance in by_instance:
            raise ValueError(f"duplicate manual SMD axis instance {instance}")
        by_instance[instance] = part
    expected = set(range(1, int(required_count) + 1))
    if set(by_instance) != expected:
        raise ValueError("manual SMD axis instance numbering is incomplete")
    payload["by_instance"] = by_instance
    return payload


def resolve_manual_axis(
    payload: dict,
    instance: int,
    detected_center: np.ndarray,
    *,
    center_tolerance_px: float,
) -> dict:
    part = payload["by_instance"][int(instance)]
    saved_center = np.asarray(part["detection_center_canonical_pixel"], dtype=float)
    current_center = np.asarray(detected_center, dtype=float)
    shift = current_center - saved_center
    distance = float(np.linalg.norm(shift))
    if distance > float(center_tolerance_px):
        raise ValueError(
            f"manual SMD axis {instance} center moved {distance:.2f}px; relabel required"
        )
    endpoints = np.asarray(part["terminal_endpoints_canonical_pixel"], dtype=float) + shift
    directed = directed_axis_angle_deg(endpoints[0], endpoints[1])
    return {
        "angle_canonical_deg": canonical_axis_angle_deg(directed),
        "directed_axis_canonical_deg": directed,
        "endpoints_canonical_pixel": endpoints.tolist(),
        "center_shift_px": distance,
        "method": "operator_two_terminal_clicks",
    }
