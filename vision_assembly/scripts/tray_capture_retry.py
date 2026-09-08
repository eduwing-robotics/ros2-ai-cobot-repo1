"""Bounded, per-physical-cell recapture while the camera and tray stay fixed."""
from copy import deepcopy
import math

import numpy as np

from fixed_cycle_snapshot import EXPECTED_TRAY_COUNTS, validate_tray_detection_quality


class RetryCaptureError(RuntimeError):
    """A bounded retry is exhausted or cached geometry became unsafe to reuse."""


class TrayCaptureRetry:
    def __init__(self, quality, after, *, window_sec=15, retries=3, required_frames=4, defer_smd_to_close_view=False):
        self.defer_smd_to_close_view = defer_smd_to_close_view
        self.quality = quality
        self.after = after
        self.window_sec = window_sec
        self.retries = retries
        self.required_frames = required_frames
        self.attempt = 1
        self.anchors = {}
        self.streak = {}
        self.accepted = {}
        self.geometry_candidates = {}
        self.reasons = {}
        self.hash = None
        self.last_stamp = None
        self.current_visible = set()
        self.keys = [(kind, i) for kind, count in EXPECTED_TRAY_COUNTS.items() for i in range(1, count + 1)]

    def tick(self, now):
        attempt = 1 + max(0, int((now - self.after) // self.window_sec))
        if attempt > self.retries + 1:
            pending = ', '.join(f'{k[0]}:{k[1]} ({self.reasons.get(k, "not visible")})'
                                for k in self.keys if k not in self.accepted or k not in self.current_visible)
            raise RetryCaptureError(f'tray retries exhausted: initial + {self.retries} retries; {pending}')
        if attempt != self.attempt:
            # Failed/pending cells start a fresh window; accepted cells stay fixed.
            self.streak = {k: n for k, n in self.streak.items() if k in self.accepted}
            self.geometry_candidates.clear()
            self.attempt = attempt
        return self.attempt

    def observe(self, payload, now):
        self.tick(now)
        stamp = float(payload.get('timestamp_ros_ns', math.nan)) / 1e9
        if stamp == self.last_stamp:
            return None
        if not math.isfinite(stamp) or not self.after < stamp <= now or now - stamp > 2:
            raise RuntimeError('waiting for fresh post-arrival tray frame')
        self.last_stamp = stamp
        if (payload.get('tray_registration') != 'TRACKING'
                or payload.get('base_transform_status') not in ('OK', 'VALID_COORDINATES_ONLY')):
            # Registration loss invalidates previous geometry, even if it returns.
            if self.anchors:
                raise RetryCaptureError('tray registration lost during per-part capture; recapture whole tray')
            raise RuntimeError('waiting for registered tray')
        current_hash = payload.get('handeye_sha256', '')
        if len(current_hash) != 64 or any(c not in '0123456789abcdef' for c in current_hash):
            raise RetryCaptureError('invalid handeye hash')
        if self.hash is not None and self.hash != current_hash:
            raise RetryCaptureError('handeye changed during capture')
        self.hash = current_hash
        detections = payload.get('stable_detections', [])
        if not isinstance(detections, list) or any(not isinstance(d, dict) for d in detections):
            raise RetryCaptureError('invalid tray detection array')
        if any(d.get('part_type') not in EXPECTED_TRAY_COUNTS for d in detections):
            raise RetryCaptureError('unexpected part type')
        visible = {}
        for kind, count in EXPECTED_TRAY_COUNTS.items():
            group = [d for d in detections if d['part_type'] == kind]
            if len(group) > count:
                raise RetryCaptureError(f'{kind}: extra/ambiguous detections; cannot bind physical cells')
            # Partial detector indices can be renumbered after a missing part.
            # Establish this class only when its complete physical layout is seen.
            if kind not in self.anchors:
                if len(group) != count:
                    for i in range(1, count + 1):
                        self.reasons[(kind, i)] = f'waiting for complete {kind} layout ({len(group)}/{count})'
                    continue
                minimum = int(self.quality.get('minimum_observation_frames', 1))
                observed = min(int(d.get('observation_frames', 0)) for d in group)
                if observed < minimum:
                    for i in range(1, count + 1):
                        self.reasons[(kind, i)] = f'warming up observations {observed}/{minimum}'
                    continue
                if sorted(d.get('instance_index') for d in group) != list(range(1, count + 1)):
                    raise RetryCaptureError(f'{kind}: invalid initial instance identities')
                self.anchors[kind] = [deepcopy(d) for d in sorted(group, key=lambda d: d['instance_index'])]
            anchors = self.anchors[kind]
            assigned = set()
            for detection in group:
                pixel = np.asarray(detection.get('reference_center_pixel'), float)
                xyz = np.asarray(detection.get('base_xyz_mm'), float)
                angle = float(detection.get('long_axis_angle_base_deg', math.nan))
                if pixel.shape != (2,) or xyz.shape != (3,) or not np.isfinite(pixel).all() or not np.isfinite(xyz).all() or not math.isfinite(angle):
                    raise RetryCaptureError(f'{kind}: invalid coordinates')
                reference_pixels = np.asarray([a.get('reference_center_pixel') for a in anchors], float)
                if reference_pixels.shape != (count, 2) or not np.isfinite(reference_pixels).all():
                    raise RetryCaptureError(f'{kind}: invalid reference cell pixels')
                distances = np.linalg.norm(reference_pixels - pixel, axis=1)
                order = np.argsort(distances)
                index = int(order[0])
                if (distances[index] > 12 or index in assigned
                        or (count > 1 and distances[order[1]] - distances[index] < 2)):
                    raise RetryCaptureError(f'{kind}: cell moved or identity ambiguous')
                assigned.add(index)
                key = (kind, index + 1)
                # Use bound physical identity, never a potentially compacted index.
                bound = deepcopy(detection)
                bound['instance_index'] = index + 1
                visible[key] = bound
        self.current_visible = set(visible)
        for key in self.keys:
            if key not in visible:
                self.streak[key] = 0
                self.reasons.setdefault(key, 'not detected in current frame')
                continue
            detection = visible[key]
            try:
                validate_tray_detection_quality(detection, self.quality, defer_smd_to_close_view=self.defer_smd_to_close_view)
                quality_error = None
            except RuntimeError as exc:
                quality_error = str(exc)
            anchor = (self.accepted[key]['detection'] if key in self.accepted
                      else self.geometry_candidates.get(key))
            changed = False
            if anchor is not None:
                xyz_delta = float(np.linalg.norm(np.asarray(detection['base_xyz_mm'], float)
                                                - np.asarray(anchor['base_xyz_mm'], float)))
                angle_delta = abs((float(detection['long_axis_angle_base_deg'])
                                   - float(anchor['long_axis_angle_base_deg']) + 90) % 180 - 90)
                changed = xyz_delta > 2 or angle_delta > 3
            if key in self.accepted:
                if changed:
                    if quality_error is None:
                        raise RetryCaptureError(f'{key[0]}:{key[1]}: confirmed part geometry changed '
                                                f'(XYZ={xyz_delta:.3f}mm, axis={angle_delta:.3f}deg); discard cached coordinates')
                    # A weak observation cannot prove motion or unchanged presence.
                    self.current_visible.discard(key)
                    self.reasons[key] = quality_error
                elif int(detection.get('observation_frames',0)) < int(self.quality.get('minimum_observation_frames',1)):
                    self.current_visible.discard(key)
                    self.reasons[key] = quality_error or 'waiting for mature observations'
                continue
            if quality_error is not None:
                self.streak[key] = 0
                self.geometry_candidates.pop(key, None)
                self.reasons[key] = quality_error
                continue
            if anchor is None or changed:
                # No frozen pick coordinates exist yet for this cell. Let a
                # mature, valid estimate settle instead of treating it as motion.
                self.streak[key] = 0
                self.geometry_candidates[key] = deepcopy(detection)
            self.streak[key] = self.streak.get(key, 0) + 1
            self.reasons[key] = f'valid frames {self.streak[key]}/{self.required_frames}'
            if self.streak[key] >= self.required_frames:
                self.accepted[key] = {'detection': detection, 'source_timestamp_unix': stamp,
                                      'accepted_attempt': self.attempt, 'valid_frames': self.streak[key]}
                self.reasons.pop(key, None)
        if len(self.accepted) != 25 or len(self.current_visible) != 25:
            return None
        oldest = min(v['source_timestamp_unix'] for v in self.accepted.values())
        if now - oldest > self.window_sec * (self.retries + 1):
            raise RetryCaptureError('accepted coordinates expired during retries')
        result = deepcopy(payload)
        result['stable_detections'] = [deepcopy(self.accepted[k]['detection']) for k in self.keys]
        result['per_part_capture_sources'] = self.sources()
        result['oldest_part_capture_unix'] = oldest
        result['capture_mode'] = 'per_cell_bounded_retry_fixed_geometry'
        return result

    def sources(self):
        return {f'{k[0]}:{k[1]}': {name: value for name, value in v.items() if name != 'detection'}
                for k, v in self.accepted.items()}

    def report(self):
        return {'attempt': self.attempt, 'maximum_attempts': self.retries + 1,
                'window_sec': self.window_sec, 'accepted_count': len(self.accepted),
                'pending': {f'{k[0]}:{k[1]}': self.reasons.get(k, 'waiting for detection')
                            for k in self.keys if k not in self.accepted or k not in self.current_visible},
                'accepted_sources': self.sources()}
