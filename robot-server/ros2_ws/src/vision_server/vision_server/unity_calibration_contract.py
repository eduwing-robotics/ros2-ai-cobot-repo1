"""Read-only Unity board/tray snapshot geometry; no robot command dependency."""
from collections import deque
import hashlib
import json
import math
import numpy as np
from .orchestration_contract import ContractFailure, pcb_snapshot, tray_snapshot, matrix_quaternion_xyzw


def vector(value, size, label):
    try:
        data = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as error:
        raise ContractFailure('FRAME_TRANSFORM_FAILED', f'invalid {label}') from error
    if data.shape != (size,) or not np.isfinite(data).all():
        raise ContractFailure('FRAME_TRANSFORM_FAILED', f'invalid {label}')
    return data


def board_state(payload, config, geometry, *, now_ns):
    snapshot = pcb_snapshot(payload,
        requested_product_code=config['expected_product_code'],
        requested_product_version=config['expected_product_version'],
        expected_product_code=config['expected_product_code'],
        expected_product_version=config['expected_product_version'], now_ns=now_ns,
        maximum_age_sec=2.5, maximum_hole_fit_rms_mm=config['maximum_hole_fit_rms_mm'],
        maximum_plane_mad_mm=config['maximum_plane_mad_mm'],
        minimum_plane_inliers=config['minimum_plane_inliers'])
    if snapshot.stamp_ns > now_ns:
        raise ContractFailure('DETECTION_TIMEOUT', 'future acquisition timestamp')
    T = np.asarray(payload['T_base_board'], float)
    rotation, origin = T[:3,:3], T[:3,3]
    residual = vector(geometry['residual']['residual_base_mm'], 3, 'slot residual') / 1000
    definitions = geometry['slots']['slots']
    codes = [s['slot_code'] for s in definitions]
    if len(codes) != 25 or len(set(codes)) != 25 or set(payload.get('slots', {})) != set(codes):
        raise ContractFailure('CALIBRATION_NOT_READY', 'all 25 unique calibrated slots required')
    slots = []
    for slot in definitions:
        code = slot['slot_code']
        nominal = vector([slot['x_mm'], slot['y_mm'], 0], 3, code) / 1000
        surface = vector(payload['slots'][code]['surface_base_mm'], 3, code) / 1000
        expected = origin + rotation @ nominal + residual
        if np.linalg.norm(surface - expected) > 1e-6:
            raise ContractFailure('CALIBRATION_NOT_READY', f'{code}: geometry/residual differs from tracker')
        local = np.linalg.solve(rotation, surface-origin)
        angle = float(slot['long_axis_board_deg'])
        if not math.isfinite(angle):
            raise ContractFailure('FRAME_TRANSFORM_FAILED', f'{code}: invalid axis')
        c,s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        local_rotation = np.array([[c,-s,0],[s,c,0],[0,0,1]])
        size = vector(slot['size_mm'], 2, f'{code} size')/1000
        if np.any(size <= 0):
            raise ContractFailure('CALIBRATION_NOT_READY', f'{code}: invalid size')
        slots.append(dict(slot_code=code, part_id=code.split('-')[0],
            nominal_board_position_m=nominal.tolist(), board_position_m=local.tolist(),
            base_position_m=surface.tolist(), size_m=size.tolist(),
            board_orientation_xyzw=list(matrix_quaternion_xyzw(local_rotation)),
            base_orientation_xyzw=list(matrix_quaternion_xyzw(rotation @ local_rotation))))
    size = vector([geometry['board']['size_mm']['x'], geometry['board']['size_mm']['y']],2,'board size') / 1000
    if np.any(size <= 0):
        raise ContractFailure('CALIBRATION_NOT_READY','invalid board dimensions')
    hx,hy=size/2
    outline = [[-hx,-hy,0],[hx,-hy,0],[hx,hy,0],[-hx,hy,0]]
    geometry_hash = hashlib.sha256(json.dumps(geometry,sort_keys=True,allow_nan=False).encode()).hexdigest()
    return dict(schema='fr5.board.unity_state/v1', valid=True,
        timestamp_ros_ns=snapshot.stamp_ns, coordinate_frame='base_link', position_units='m',
        product_code=config['expected_product_code'],product_version=config['expected_product_version'],
        board_pose=dict(position_m=list(snapshot.pose.position_m),orientation_xyzw=list(snapshot.pose.orientation_xyzw)),
        T_base_board=T.tolist(), board_size_m=size.tolist(), outline_board_m=outline,
        slots=slots, slot_count=len(slots), geometry_sha256=geometry_hash,
        calibration_id=f'{snapshot.stamp_ns}:{geometry_hash[:16]}',
        slot_semantics='calibrated_surface_centers_not_robot_tcp',
        residual_base_m=residual.tolist(), robot_motion_authorized=False,
        quality={k:payload[k] for k in ('hole_fit_rms_mm','plane_residual_mad_mm','plane_inliers')})


class BoardWindow:
    """Four distinct source frames, <=1mm translation and <=1deg rotation span."""
    def __init__(self):
        self.frames = deque(maxlen=4)

    def clear(self):
        self.frames.clear()

    def observe(self, state):
        stamp = state['timestamp_ros_ns']
        if self.frames and stamp <= self.frames[-1]['timestamp_ros_ns']:
            return
        if self.frames and state['geometry_sha256'] != self.frames[-1]['geometry_sha256']:
            self.clear()
        self.frames.append(state)

    def stable(self, *, after_ns=0, now_ns=None):
        if len(self.frames) != 4 or self.frames[0]['timestamp_ros_ns'] <= after_ns:
            return False
        if now_ns is not None and now_ns-self.frames[0]['timestamp_ros_ns'] > 2_500_000_000:
            return False
        matrices = np.asarray([v['T_base_board'] for v in self.frames])
        for a in matrices:
            for b in matrices:
                if np.linalg.norm(a[:3,3]-b[:3,3]) > .001:
                    return False
                cosine = (np.trace(a[:3,:3].T @ b[:3,:3])-1)/2
                if math.degrees(math.acos(float(np.clip(cosine,-1,1)))) > 1:
                    return False
        return True


def tray_state(payload, config, layout, *, now_ns):
    snapshot = tray_snapshot(payload, config['part_mappings'], now_ns=now_ns,
        maximum_age_sec=2.5, minimum_observation_frames=config['minimum_observation_frames'])
    if snapshot.stamp_ns > now_ns:
        raise ContractFailure('DETECTION_TIMEOUT','future acquisition timestamp')
    parts = []
    for original, part_id, pose in zip(payload['parts'],snapshot.part_ids,snapshot.poses):
        parts.append(dict(original, part_id=part_id,
            position_m=list(pose.position_m),orientation_xyzw=list(pose.orientation_xyzw)))
    return dict(schema='fr5.tray.calibration_snapshot/v1',valid=True,
        timestamp_ros_ns=snapshot.stamp_ns,coordinate_frame='base_link',position_units='m',
        parts=parts,part_count=len(parts),
        section_reference=dict(reference_only=True,image_size_px=layout['reference_image_size_px'],
            sections=[{k:b[k] for k in ('bin_id','part_type','section_polygon_normalized')}
                      for b in layout['bins']]),
        robot_motion_authorized=False)
