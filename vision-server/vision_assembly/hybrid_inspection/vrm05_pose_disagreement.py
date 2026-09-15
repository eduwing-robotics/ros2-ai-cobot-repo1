"""Abstain on conflicting advisory geometry, never grant a normal vote."""
import math


def conflicting_pose(row):
    if row.get('slot_id') != 'vrm_05' or row.get('component_type') != 'VRM':
        return False
    stages = row.get('stages',{})
    presence = stages.get('presence',{})
    boundary = stages.get('vrm_boundary',{})
    if presence.get('predicted_state') != 'CORRECT' or boundary.get('reason') != 'VRM_BOUNDARY_UNCERTAIN':
        return False
    if boundary.get('authority') != 'ADVISORY_ONLY' or boundary.get('codes'):
        return False
    try:
        position = boundary['measured']['position']
        bounds = boundary['position_bounds_px']
        margin = boundary['position_margin_px']
        confidence = float(boundary['measured']['confidence'])
        if len(position)!=3 or len(bounds)!=3 or len(margin)!=3 or not .9 <= confidence <= 1:
            return False
        for value, interval, tolerance in zip(position,bounds,margin):
            if len(interval)!=2:
                return False
            value, low, high, tolerance = map(float,(value,*interval,tolerance))
            if not all(math.isfinite(v) for v in (value,low,high,tolerance)) or low>high or tolerance<0:
                return False
            if not low-tolerance <= value <= high+tolerance:
                return False
    except (KeyError,TypeError,ValueError):
        return False
    return True
