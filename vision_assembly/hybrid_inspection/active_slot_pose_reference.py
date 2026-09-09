"""Bind auxiliary measured centers to selected fixed geometry, never to themselves."""
from copy import deepcopy
import math


def bind_active_slot_centers(items, slots):
    result=deepcopy(items)
    for slot in slots:
        item=result.get(slot.slot_id)
        if not isinstance(item,dict) or not isinstance(item.get('evidence'),dict):
            continue
        center=[float(v) for v in slot.geometry[:2]]
        if len(center)!=2 or not all(math.isfinite(v) for v in center):
            raise ValueError('Invalid fixed reference center')
        evidence=item['evidence']
        evidence['original_expected_center_px']=evidence.get('expected_center_px')
        evidence['expected_center_px']=center
        evidence['expected_center_source']='active_fixed_slot_geometry'
    return result
