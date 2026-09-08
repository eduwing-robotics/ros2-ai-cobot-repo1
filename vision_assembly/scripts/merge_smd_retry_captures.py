"""Combine independently validated SMD captures while preserving provenance."""
import copy
import math
import numpy as np


def merge_captures(inputs, now):
    fresh = [(name, p) for name, p in inputs
             if math.isfinite(float(p.get('timestamp_unix', math.nan)))
             and 0 <= now - float(p['timestamp_unix']) <= 120]
    if not fresh:
        raise RuntimeError('no fresh SMD retry captures')
    fresh.sort(key=lambda row: row[1]['timestamp_unix'])
    reference = fresh[0][1]
    required = ('mode', 'set_index', 'required_count', 'layout_capacity',
                'handeye_sha256', 'model_sha256', 'operator_confirmed_consumed_prefix_count', 'axis_geometry_version')
    if reference['mode'] != 'smd_close_multiframe_base_targets' or reference['required_count'] != 5:
        raise RuntimeError('unexpected SMD capture scope')
    selected, observations, poses = {}, {}, []
    for name, payload in fresh:
        if any(payload.get(k) != reference.get(k) for k in required):
            raise RuntimeError('SMD retry identity/calibration changed')
        parts = payload['parts']
        if sorted(p['instance_index'] for p in parts) != [1, 2, 3, 4, 5]:
            raise RuntimeError('SMD retry cell mapping changed')
        for part in parts:
            index = part['instance_index']
            if (part['physical_instance_index'] != (reference['set_index']-1)*5+index
                    or part['part_type'] != 'right_white_brown'
                    or part['center_correction_applied'] is not False):
                raise RuntimeError('invalid SMD retry part identity')
            xyz = np.asarray(part['part_center_base_mm'], float)
            if xyz.shape != (3,) or not np.isfinite(xyz).all():
                raise RuntimeError('invalid SMD center')
            observations.setdefault(index, []).append(xyz)
            poses.extend(sample['pose'] for sample in part['samples'])
            if part['validation_passed'] is True:
                if (part['frame_count'] < 24 or len(part['samples']) != part['frame_count']
                        or part['temporal_batch_count'] != 3
                        or part['confidence_median'] < .5
                        or max(part['center_span_canonical_px']) > 3.5
                        or part['angle_batch_span_deg'] > 3):
                    raise RuntimeError('SMD accepted part fails original quality limits')
                selected[index] = (name, payload['timestamp_unix'], copy.deepcopy(part))
    if set(selected) != {1, 2, 3, 4, 5}:
        raise RuntimeError(f'SMD retries still pending: {sorted(set(range(1,6))-set(selected))}')
    for index, rows in observations.items():
        if np.max(np.linalg.norm(np.asarray(rows)-selected[index][2]['part_center_base_mm'], axis=1)) > .5:
            raise RuntimeError('SMD part moved between retries; discard cached measurements')
    poses = np.asarray(poses, float)
    if poses.ndim != 2 or poses.shape[1] != 6 or not np.isfinite(poses).all():
        raise RuntimeError('invalid SMD capture robot poses')
    if (np.max(np.linalg.norm(poses[:,:3]-poses[0,:3], axis=1)) > .5
            or np.max(np.abs((poses[:,3:]-poses[0,3:]+180)%360-180)) > .1):
        raise RuntimeError('robot moved between SMD retries')
    result = copy.deepcopy(reference)
    result['parts'] = [selected[i][2] for i in range(1,6)]
    result['timestamp_unix'] = min(row[1] for row in selected.values())
    result['validation_passed'] = True  # Every constituent independently passed.
    result['capture_mode'] = 'independently_validated_per_part_retries'
    result['retry_sources'] = {str(i): {'file': selected[i][0], 'captured_unix': selected[i][1]}
                               for i in range(1,6)}
    return result
