#!/usr/bin/env python3
"""Pure validation helpers for the non-SMD 50 mm tray-hover workflow."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np


class TrayHoverContractError(RuntimeError):
    """A live tray state or requested target violated the safety contract."""


def load_contract(path: Path) -> dict:
    try:
        contract = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrayHoverContractError(f'Cannot read tray-hover contract: {exc}') from exc
    if contract.get('mode') != 'non_smd_tray_hover_only':
        raise TrayHoverContractError('Unexpected tray-hover contract mode')
    if float(contract.get('hover_offset_mm', math.nan)) != 50.0:
        raise TrayHoverContractError('Tray-hover contract must fix the offset at 50.0 mm')
    return contract


def normalize_part_type(value: str, contract: dict) -> str:
    requested = str(value).strip().lower().replace(' ', '_')
    for canonical, profile in contract.get('parts', {}).items():
        aliases = {canonical, *(str(alias).lower() for alias in profile.get('aliases', []))}
        if requested in aliases:
            return canonical
    for canonical, profile in contract.get('excluded_parts', {}).items():
        aliases = {canonical, *(str(alias).lower() for alias in profile.get('aliases', []))}
        if requested in aliases:
            raise TrayHoverContractError(
                f'{profile.get("display_name", canonical)} is excluded: '
                f'{profile.get("reason", "dedicated workflow required")}'
            )
    supported = ', '.join(contract.get('parts', {}))
    raise TrayHoverContractError(
        f'Unknown part type {value!r}; supported non-SMD types: {supported}'
    )


def state_age_sec(timestamp_ros_ns: object, now_ns: int | None = None) -> float:
    try:
        timestamp_ns = int(timestamp_ros_ns)
    except (TypeError, ValueError) as exc:
        raise TrayHoverContractError('State timestamp_ros_ns is missing or invalid') from exc
    if timestamp_ns <= 0:
        raise TrayHoverContractError('State timestamp_ros_ns must be positive')
    if now_ns is None:
        now_ns = time.time_ns()
    return (int(now_ns) - timestamp_ns) / 1e9


def _require_fresh(payload: dict, contract: dict, now_ns: int | None = None) -> float:
    maximum_age = float(contract['required_state']['maximum_state_age_sec'])
    age = state_age_sec(payload.get('timestamp_ros_ns'), now_ns)
    if age < -1.0 or age > maximum_age:
        raise TrayHoverContractError(
            f'Live tray state is stale or clock-mismatched (age={age:.3f} s)'
        )
    return age


def validate_registration(payload: dict, contract: dict, now_ns: int | None = None) -> dict:
    age = _require_fresh(payload, contract, now_ns)
    prefix = str(contract['required_state']['registration_state_prefix'])
    state = str(payload.get('state', ''))
    if not state.startswith(prefix):
        raise TrayHoverContractError(f'Tray registration is not tracking ({state or "missing"})')
    if payload.get('at_trayhome') is not True:
        raise TrayHoverContractError('Robot is not at the validated tray waiting pose')
    homography = np.asarray(payload.get('homography_reference_to_image'), dtype=float)
    if homography.shape != (3, 3) or not np.all(np.isfinite(homography)):
        raise TrayHoverContractError('Tray registration has no valid 3x3 homography')
    return {'state': state, 'age_sec': age, 'timestamp_ros_ns': int(payload['timestamp_ros_ns'])}


def validate_surface_workspace(xyz: object, contract: dict) -> np.ndarray:
    point = np.asarray(xyz, dtype=float)
    if point.shape != (3,) or not np.all(np.isfinite(point)):
        raise TrayHoverContractError('Part has no finite Base XYZ surface coordinate')
    bounds = contract['surface_workspace_base_mm']
    for index, axis in enumerate(('x', 'y', 'z')):
        lower, upper = map(float, bounds[axis])
        if not lower <= float(point[index]) <= upper:
            raise TrayHoverContractError(
                f'Part surface {axis}={point[index]:.3f} mm is outside '
                f'tray workspace [{lower:.3f}, {upper:.3f}] mm'
            )
    return point


def validate_unity_target(
    payload: dict,
    part_type: str,
    instance: int,
    contract: dict,
    now_ns: int | None = None,
) -> dict:
    required = contract['required_state']
    age = _require_fresh(payload, contract, now_ns)
    expected = {
        'schema': required['schema'],
        'base_transform_status': required['base_transform_status'],
        'coordinate_frame': required['coordinate_frame'],
        'position_units': required['position_units'],
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            raise TrayHoverContractError(
                f'Unity tray state {key}={payload.get(key)!r}; expected {expected_value!r}'
            )
    if payload.get('valid') is not True:
        raise TrayHoverContractError('Unity tray state is not valid')
    prefix = str(required['registration_state_prefix'])
    if not str(payload.get('registration_state', '')).startswith(prefix):
        raise TrayHoverContractError('Unity tray state is not tracking the tray')
    try:
        sequence = int(payload['sequence'])
    except (KeyError, TypeError, ValueError) as exc:
        raise TrayHoverContractError('Unity tray state sequence is missing or invalid') from exc
    if sequence < 0:
        raise TrayHoverContractError('Unity tray state sequence must be non-negative')
    try:
        count = int(payload.get('counts', {}).get(part_type, 0))
    except (TypeError, ValueError) as exc:
        raise TrayHoverContractError(f'Invalid live count for {part_type}') from exc
    if count < instance:
        raise TrayHoverContractError(
            f'{part_type} #{instance} is not currently visible (live count={count})'
        )
    matches = [
        item for item in payload.get('parts', [])
        if item.get('part_type') == part_type
        and int(item.get('instance_index', -1)) == instance
    ]
    if len(matches) != 1:
        raise TrayHoverContractError(
            f'Expected one live target for {part_type} #{instance}; found {len(matches)}'
        )
    part = matches[0]
    observations = int(part.get('observation_frames', 0))
    minimum_observations = int(required['minimum_observation_frames'])
    if observations < minimum_observations:
        raise TrayHoverContractError(
            f'Target has only {observations} stable observations; need {minimum_observations}'
        )
    point = validate_surface_workspace(part.get('base_xyz_mm'), contract)
    profile = contract['parts'][part_type]
    angle = None
    if profile['orientation_mode'] == 'long_axis':
        try:
            angle = float(part['angle_base_deg'])
        except (KeyError, TypeError, ValueError) as exc:
            raise TrayHoverContractError('Target has no valid Base-frame long-axis angle') from exc
        if not math.isfinite(angle):
            raise TrayHoverContractError('Target Base-frame angle is not finite')
    return {
        'sequence': sequence,
        'timestamp_ros_ns': int(payload['timestamp_ros_ns']),
        'state_age_sec': age,
        'part_type': part_type,
        'instance_index': instance,
        'display_name': part.get('display_name', profile['display_name']),
        'base_xyz_mm': point,
        'long_axis_angle_base_deg': angle,
        'observation_frames': observations,
        'live_count': count,
        'camera_xyz_m': part.get('camera_xyz_m'),
        'reference_xy_px': part.get('reference_xy_px'),
    }


def symmetric_axis_delta_deg(angle_deg: float, reference_deg: float) -> float:
    """Return the signed shortest delta for an axis with 180-degree symmetry."""
    return (float(angle_deg) - float(reference_deg) + 90.0) % 180.0 - 90.0


def summarize_samples(samples: list[dict], contract: dict) -> dict:
    if not samples:
        raise TrayHoverContractError('No target samples were collected')
    points = np.asarray([sample['base_xyz_mm'] for sample in samples], dtype=float)
    center = np.median(points, axis=0)
    jitter = float(np.max(np.linalg.norm(points - center, axis=1)))
    limit = float(contract['capture']['max_position_jitter_mm'])
    if jitter > limit:
        raise TrayHoverContractError(
            f'Target position jitter {jitter:.3f} mm exceeds {limit:.3f} mm'
        )
    angles = [
        float(sample['long_axis_angle_base_deg'])
        for sample in samples
        if sample.get('long_axis_angle_base_deg') is not None
    ]
    axis_angle = None
    angle_jitter = 0.0
    if angles:
        doubled = np.deg2rad(np.asarray(angles, dtype=float) * 2.0)
        axis_angle = 0.5 * math.degrees(
            math.atan2(float(np.mean(np.sin(doubled))), float(np.mean(np.cos(doubled))))
        )
        angle_jitter = max(abs(symmetric_axis_delta_deg(angle, axis_angle)) for angle in angles)
        angle_limit = float(contract['capture']['max_axis_angle_jitter_deg'])
        if angle_jitter > angle_limit:
            raise TrayHoverContractError(
                f'Target angle jitter {angle_jitter:.3f} deg exceeds {angle_limit:.3f} deg'
            )
    return {
        'center_base_mm': center,
        'max_position_jitter_mm': jitter,
        'axis_angle_base_deg': axis_angle,
        'max_axis_angle_jitter_deg': angle_jitter,
    }
