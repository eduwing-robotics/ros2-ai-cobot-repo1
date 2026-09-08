"""Tray inventory evidence and high-clearance inspection excursions.

Removal evidence is not labelled as physical holding or placement proof.
"""
import time
import json
import numpy as np
import rclpy
from scipy.optimize import linear_sum_assignment
from full_cycle_motion import MotionWaypoint
from fixed_cycle_snapshot import validate_tray_detection_quality
from execution_safety import STATE_MAX_AGE_SEC

HOME = (-527.997, -60.954, 337.88, -180., 0., 90.)
INSPECTION_Z = 350.0


def excursion(start, prefix, return_to_start=False):
    z=max(INSPECTION_Z,float(start[2]))
    high=(*start[:2],z,*start[3:])
    home_high=(*HOME[:2],z,*HOME[3:])
    def midpoints(first,last,name):
        target=list(last)
        for axis in (3,4,5):
            target[axis]=first[axis]+(target[axis]-first[axis]+180)%360-180
        return [MotionWaypoint(name,tuple(first[k]+f*(target[k]-first[k]) for k in range(6)),False)
                for f in (1/3,2/3)]
    result=[MotionWaypoint(prefix+'_raise',high,True)]
    result+=midpoints(high,home_high,prefix+'_mid_travel')
    result+=[
            MotionWaypoint(prefix+'_travel',home_high,False),
            MotionWaypoint(prefix+'_inspect',HOME,True)]
    if return_to_start:
        result += [MotionWaypoint(prefix+'_depart',home_high,True)]
        result += midpoints(home_high,high,prefix+'_mid_return')
        result += [
                   MotionWaypoint(prefix+'_return',high,False),
                   MotionWaypoint(prefix+'_restore',tuple(start),True)]
    return result


def add_inspections(route, start):
    """Inspect after the proof lift, then transfer directly from TrayHome.

    Rebuild the outgoing transfer from the actual inspection pose: old
    midpoints were based on the pick pose and cannot be reused here.
    """
    output=[]
    index=0
    while index < len(route):
        slot,waypoint=route[index]
        output.append((slot,waypoint))
        index+=1
        if waypoint.label != 'post_grasp_proof_lift_100mm_vertical':
            continue
        end=index
        while end < len(route) and route[end][0]==slot and route[end][1].label!='place_combined_xy_abc':
            end+=1
        if end==len(route) or route[end][0]!=slot:
            raise RuntimeError('inspection requires a following board transfer')
        destination=route[end][1]
        height=float(destination.tcp[2])
        if height < max(INSPECTION_Z, waypoint.tcp[2]):
            raise RuntimeError('board transfer is below inspection safe height')
        output.extend((slot,w) for w in excursion(waypoint.tcp,'tray_after'))
        origin=(*HOME[:2],height,*HOME[3:])
        output.append((slot,MotionWaypoint('tray_after_depart',origin,True)))
        target=list(destination.tcp)
        for axis in (3,4,5):
            target[axis]=origin[axis]+(target[axis]-origin[axis]+180)%360-180
        for fraction in (1/3,2/3):
            mid=tuple(origin[k]+fraction*(target[k]-origin[k]) for k in range(6))
            output.append((slot,MotionWaypoint('place_combined_xy_abc_midpoint',mid,False)))
        output.append((slot,destination))
        index=end+1
    return output


def check_pick_removal(live, reference, removed, slot, now, after):
    """Check only picked section/cell, without recalculating any pick pose."""
    stamp=float(live['timestamp_ros_ns'])/1e9
    if not after < stamp <= now or now-stamp>2:
        raise RuntimeError('waiting for fresh post-pick image')
    if live.get('tray_registration')!='TRACKING' or live.get('base_transform_status') not in ('OK','VALID_COORDINATES_ONLY'):
        raise RuntimeError('tray not visible/registered')
    if live.get('handeye_sha256')!=reference['handeye_sha256']:
        raise RuntimeError('handeye changed')
    kind={'GPU':'gpu','HBM':'hbm','PM':'long_orange','VRM':'black_block','IND':'marked_white','CAP':'right_white_brown'}[slot.split('-')[0]]
    code=slot.split('-')[0]
    bindings=[b for b in reference['bindings'] if b['part_type']==kind]
    target=next(b for b in bindings if b['physical_index']==int(slot.split('-')[1]))
    actual=[d for d in live['stable_detections'] if d['part_type']==kind]
    # Even a weak detection in the picked cell blocks absence inference.
    for d in live.get('detections',[])+actual:
        if d['part_type']==kind and np.linalg.norm(np.array(d['reference_center_pixel'])-np.array(target['reference_center_pixel']))<20:
            raise RuntimeError('picked cell still occupied')
    expected=[b for b in bindings if f"{code}-{b['physical_index']:02d}" not in removed]
    if len(actual)!=len(expected):
        raise RuntimeError('picked-section count does not show exactly expected removal')
    if not live['stable_detections']:
        # The final part legitimately leaves no part-based visual anchor.
        # Require a fresh registered tray observation and completion of every
        # referenced cell instead of accepting a missing/blank detector output.
        prefix={'gpu':'GPU','hbm':'HBM','long_orange':'PM','black_block':'VRM',
                'marked_white':'IND','right_white_brown':'CAP'}
        cells={f"{prefix[b['part_type']]}-{b['physical_index']:02d}"
               for b in reference['bindings'] if b['part_type'] in prefix}
        def bounded(key,limit):
            value=float(live.get(key,float('nan')))
            return np.isfinite(value) and 0 <= value <= limit
        registered_empty=(cells and cells.issubset(removed)
            and live.get('registration_source')=='shared_section_tracker'
            and bounded('registration_age_ms',500)
            and bounded('robot_pose_span_mm',.2) and bounded('robot_rotation_span_deg',.1)
            and bounded('depth_sync_ms',120)
            and live.get('detected_total')==0 and live.get('stable_detected_total')==0
            and live.get('detections')==[])
        if not registered_empty:
            raise RuntimeError('no visual observations; cannot infer empty cell')
    if expected:
        distances=np.array([[np.linalg.norm(np.array(d['reference_center_pixel'])-np.array(b['reference_center_pixel'])) for b in expected] for d in actual])
        ii,jj=linear_sum_assignment(distances)
        if not np.isfinite(distances).all() or any(distances[i,j]>12 for i,j in zip(ii,jj)):
            raise RuntimeError('picked-section identity mismatch')
    return {'timestamp_ros_ns':live['timestamp_ros_ns'],'picked_slot':slot,
            'removed_slots':sorted(removed),'evidence':'picked_cell_absent_not_physical_holding_proof'}


def check_inventory(live, reference, removed, quality, now, after):
    stamp=float(live['timestamp_ros_ns'])/1e9
    if not after < stamp <= now or now-stamp>2:
        raise RuntimeError('waiting for fresh post-arrival tray frame')
    if live.get('tray_registration')!='TRACKING' or live.get('base_transform_status') not in ('OK','VALID_COORDINATES_ONLY'):
        raise RuntimeError('tray registration/transform unavailable')
    if live.get('handeye_sha256')!=reference['handeye_sha256']:
        raise RuntimeError('handeye changed')
    binding={(b['part_type'],b['physical_index']):b for b in reference['bindings']}
    prefix={'hbm':'HBM','long_orange':'PM','black_block':'VRM','marked_white':'IND'}
    matches=[]
    for kind,code in prefix.items():
        expected=[p for p in reference['parts'] if p['part_type']==kind
                  and f"{code}-{p['instance_index']:02d}" not in removed]
        actual=[p for p in live['stable_detections'] if p['part_type']==kind]
        if len(actual)!=len(expected):
            raise RuntimeError(f'{kind} inventory mismatch: {len(actual)} != {len(expected)}')
        if not expected:continue
        distances=np.array([[np.linalg.norm(np.array(d['reference_center_pixel'])-
            np.array(binding[(kind,p['instance_index'])]['reference_center_pixel']))
            for p in expected] for d in actual])
        ii,jj=linear_sum_assignment(distances)
        for i,j in zip(ii,jj):
            d,p=actual[i],expected[j]
            if not np.isfinite(distances[i,j]) or distances[i,j]>12:
                raise RuntimeError(f'{kind} cell identity mismatch')
            validate_tray_detection_quality(d,quality)
            xyz=np.asarray(d['base_xyz_mm'],float)
            prior=np.asarray(p['base_xyz_mm'],float)
            if not np.isfinite(xyz).all() or np.linalg.norm(xyz[:2]-prior[:2])>2:
                raise RuntimeError(f'{kind} XY changed; new plan required')
            angle=abs((float(d['long_axis_angle_base_deg'])-float(p['long_axis_angle_base_deg'])+90)%180-90)
            if angle>3:
                raise RuntimeError(f'{kind} axis changed; new plan required')
            matches.append(f"{code}-{p['instance_index']:02d}")
    return {'timestamp_ros_ns':live['timestamp_ros_ns'],'remaining_slots':matches,
            'removed_slots':sorted(removed),'evidence':'tray_inventory_only_not_holding_proof'}


def wait_inventory(node, path, reference, removed, quality, timeout=45, picked_slot=None, attempts=3):
    if not 1 <= attempts <= 3 or timeout <= 0:
        raise ValueError('invalid inspection retry limits')
    arrived=time.time()
    deadline=time.monotonic()+timeout
    attempt=1
    attempt_reasons=[]
    last_stamp=None
    consecutive=0
    reason='no frames'
    while True:
        if time.monotonic()>=deadline:
            attempt_reasons.append(reason)
            if attempt>=attempts:
                raise RuntimeError(f'TrayHome inspection exhausted ({attempts} attempts): '+reason)
            attempt+=1
            consecutive=0
            arrived=time.time()  # Next window requires post-window image timestamps.
            deadline=time.monotonic()+timeout
            print(f'TRAY DETECTION RETRY {attempt}/{attempts}: {reason}', flush=True)
        # Fresh image evidence cannot compensate for lost robot feedback.
        state=node.spin_state(timeout_sec=STATE_MAX_AGE_SEC)
        error=node.safety_error(state)
        if error:raise RuntimeError(error)
        if int(state.robot_motion_done)!=1:
            raise RuntimeError('robot moved during inspection')
        try:
            live=json.loads(path.read_text())
            stamp=live['timestamp_ros_ns']
            if stamp==last_stamp:continue
            last_stamp=stamp
            result=(check_pick_removal(live,reference,removed,picked_slot,time.time(),arrived)
                    if picked_slot else check_inventory(live,reference,removed,quality,time.time(),arrived))
        except (ValueError,KeyError,RuntimeError,OSError) as exc:
            consecutive=0
            reason=str(exc)
            continue
        consecutive+=1
        if consecutive>=3:
            result['detection_attempts']=attempt
            result['previous_attempt_reasons']=attempt_reasons
            result['distinct_consecutive_frames']=consecutive
            return result
