"""Frozen raw-centroid calibration; never estimate correction from the inspected board.

This is advisory reference-relative metrology, not socket containment or height.
The caller must supply explicitly labelled normal calibration scenes. Missing or
changed calibration dependencies invalidate this provider, not the other stages.
"""
from hashlib import sha256
import json
import math
from pathlib import Path


def entries_digest(entries):
    return sha256(json.dumps(entries, sort_keys=True, allow_nan=False).encode()).hexdigest()


def fit_offsets(samples, slot_ids, calibration_id, *, minimum_samples=2):
    """Least-squares constant offset per slot, in the registered board frame.

    No rotation, image transformation, tolerance selection or frame-wise offset
    is fitted. A missing measurement is not a zero-offset sample.
    """
    if minimum_samples < 2 or len({s['source_sha256'] for s in samples}) != len(samples):
        raise ValueError('Repeated calibration image or insufficient sample requirement')
    result = {}
    for sid in slot_ids:
        values = [s['raw_offsets_mm'][sid] for s in samples if sid in s['raw_offsets_mm']]
        if len(values) < minimum_samples:
            raise ValueError(f'Insufficient normal measurements for {sid}')
        if any(len(v) != 2 or not all(math.isfinite(float(x)) for x in v) for v in values):
            raise ValueError(f'Invalid normal measurement for {sid}')
        offset = [sum(float(v[i]) for v in values) / len(values) for i in (0, 1)]
        if not all(math.isfinite(x) for x in offset):
            raise ValueError(f'Nonfinite fitted reference for {sid}')
        result[sid] = dict(offset_mm=offset, calibration_id=calibration_id,
                           sample_count=len(values),
                           maximum_reference_residual_mm=max(math.dist(v, offset) for v in values))
    return result


def validate_fixed_reference(config, root, slot_ids, weights_path):
    """Return None for legacy configs, or a bounded fail-safe validation result."""
    meta = config.get('fixed_pose_reference')
    if meta is None:
        return None
    try:
        if config.get('component_bias_diagnostic_only') is not True:
            raise ValueError('FIXED_REFERENCE_REQUIRES_NO_COMPONENT_BIAS')
        if not config.get('auxiliary_pose_use_active_slot_centers'):
            raise ValueError('FIXED_REFERENCE_REQUIRES_FIXED_CAD_CENTERS')
        entries = config['auxiliary_pose_slot_reference_offsets_mm']
        if set(entries) != set(slot_ids):
            raise ValueError('FIXED_REFERENCE_SLOT_COVERAGE_MISMATCH')
        if entries_digest(entries) != meta['entries_sha256']:
            raise ValueError('FIXED_REFERENCE_OFFSETS_CHANGED')
        recomputed = fit_offsets(meta['samples'], slot_ids, meta['calibration_id'])
        if entries != recomputed:
            raise ValueError('FIXED_REFERENCE_SAMPLE_MISMATCH')
        dependencies = meta['dependencies']
        required = [config[k] for k in ('board_layout', 'physical_board', 'provider_crop_config')]
        required.append(str(weights_path))
        canonical = {str((Path(root) / p).resolve()): digest for p, digest in dependencies.items()}
        if any(str((Path(root) / p).resolve()) not in canonical for p in required):
            raise ValueError('FIXED_REFERENCE_DEPENDENCY_NOT_PINNED')
        for path, digest in canonical.items():
            if sha256(Path(path).read_bytes()).hexdigest() != digest:
                raise ValueError('FIXED_REFERENCE_DEPENDENCY_CHANGED')
        return dict(status='AVAILABLE', authority='ADVISORY_ONLY',
                    reason='FROZEN_NORMAL_RAW_OFFSETS_NO_FRAME_COMPONENT_CORRECTION',
                    calibration_id=meta['calibration_id'], sample_count=len(meta['samples']),
                    entries_sha256=meta['entries_sha256'],
                    limitation='Reference-relative candidate; not production containment/height validation.')
    except (KeyError, TypeError, ValueError, OSError, OverflowError, AttributeError) as error:
        reason = str(error) if isinstance(error, ValueError) else type(error).__name__
        return dict(status='UNAVAILABLE', authority='INVALID', reason=reason,
                    calibration_id=None)
