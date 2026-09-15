"""Operator-confirmed grasp/place branches; never choose an IK-friendly opposite.

General parts: 20260907-150051-662747, confirmed in placement_review_20260907_150051.
CAP: full_cycle_success_20260906/criteria_and_completed_slots.json.
PM-02: operator corrected camera-facing placement, pm_all_05 (20260908).
These are branch references, not stale absolute XYZ or exact measured yaw.
"""
import math

REFERENCES = {
    'GPU-01': (90., 180.),
    **{f'HBM-{i:02d}': (90., 180.) for i in range(1, 9)},
    'PM-01': (90., 180.), 'PM-02': (90., 180.),
    'PM-03': (90., 90.), 'PM-04': (90., 90.),
    **{f'VRM-{i:02d}': (90., 180.) for i in range(1, 6)},
    'IND-01': (0., 180.), 'IND-02': (0., 180.),
    'CAP-01': (0., 180.),
    **{f'CAP-{i:02d}': (0., 90.) for i in range(2, 6)},
}
REVISION = 'operator_confirmed_pm02_camera_forward_20260908'
MAX_FINE_ANGLE_DEG = 15.


def distance(a, b):
    return abs((float(a)-float(b)+180) % 360-180)


def validate_item(item):
    slot = item['slot_code']
    if slot not in REFERENCES:
        raise RuntimeError(f'{slot}: no successful gripper direction recorded')
    for field, reference in zip(('pick_final_tcp', 'place_final_tcp'), REFERENCES[slot]):
        pose = item.get(field)
        if not isinstance(pose, (tuple, list)) or len(pose) != 6 or not all(math.isfinite(float(v)) for v in pose):
            raise RuntimeError(f'{slot}: invalid {field}')
        if (distance(pose[3], 180) > 5 or distance(pose[4], 0) > 5
                or distance(pose[5], reference) > MAX_FINE_ANGLE_DEG):
            raise RuntimeError(f'{slot}: {field} violates successful gripper direction; '
                               f'C={pose[5]}, successful branch={reference}; do not flip endpoints to solve IK')
