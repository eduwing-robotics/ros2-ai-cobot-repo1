"""Pure numeric guards before target freshness/quality comparisons or motion.

NaN compares false in both directions. Reject it before applying existing limits;
this module does not authorize motion or change calibration/tolerances.
"""
import math


def finite_number(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a finite number, not bool')
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} must be a finite number') from exc
    if not math.isfinite(number):
        raise ValueError(f'{name} must be finite (NaN/Inf rejected)')
    return number


def finite_vector(values, size, name):
    if not isinstance(values, (list, tuple)) or len(values) != size:
        raise ValueError(f'{name} must contain exactly {size} finite numbers')
    return [finite_number(value, name) for value in values]


def validate_cli_floats(args, parser):
    for name, value in vars(args).items():
        if isinstance(value, float) and not math.isfinite(value):
            parser.error(f'--{name.replace("_", "-")} must be finite (NaN/Inf rejected)')
    if getattr(args, 'max_target_age_sec', 1.0) <= 0:
        parser.error('--max-target-age-sec must be positive')


def validate_target_numbers(payload):
    if not isinstance(payload, dict):
        raise ValueError('target must be a JSON object')
    timestamp = finite_number(payload.get('timestamp_unix'), 'timestamp_unix')
    if timestamp <= 0:
        raise ValueError('timestamp_unix must be positive')
    finite_vector(payload.get('part_center_base_mm'), 3, 'part_center_base_mm')
    for key in ('long_axis_angle_base_deg', 'long_axis_angle_jitter_max_deg'):
        if payload.get(key) is not None:
            value = finite_number(payload[key], key)
            if key.endswith('jitter_max_deg') and value < 0:
                raise ValueError(f'{key} cannot be negative')
    if 'part_size_input_mm' in payload:
        size = finite_vector(payload['part_size_input_mm'], 3, 'part_size_input_mm')
        if any(value <= 0 for value in size):
            raise ValueError('part_size_input_mm must be positive')
    quality = payload.get('depth_quality')
    if quality is not None:
        if not isinstance(quality, dict):
            raise ValueError('depth_quality must be an object')
        for key in ('valid_fraction_min', 'local_mad_max_mm',
                    'frame_jitter_max_mm', 'support_plane_mad_max_mm'):
            if key in quality:
                value = finite_number(quality[key], f'depth_quality.{key}')
                if value < 0 or (key == 'valid_fraction_min' and value > 1):
                    raise ValueError(f'depth_quality.{key} is outside physical bounds')
