"""Current visual station occupancy, separate from latched crossing events.

No ROS/motor calls. Frame history is never advanced by a timer or repeated image.
Geometric continuity is not a serial number or Job/Unit identity.
"""
import math
import uuid


def fresh_stamp(stamp, now, max_age):
    return (type(stamp) is int and stamp > 0 and type(now) is int
            and 0 <= now - stamp <= max_age * 1e9)


def stopped_motor(state, now, max_age, *, allow_manual_stop=False):
    allowed_states = ('IDLE', 'ASSEMBLY_STOP', 'INSPECTION_STOP')
    if allow_manual_stop:
        allowed_states += ('MANUAL_STOP',)
    return (isinstance(state, dict)
            and fresh_stamp(state.get('timestamp_ns'), now, max_age)
            and state.get('state') in allowed_states
            and state.get('moving') is False
            and type(state.get('command_linear_x_mps')) in (int, float)
            and state['command_linear_x_mps'] == 0.0
            and bool(state.get('server_instance_id')))


class LiveArrival:
    def __init__(self, *, tolerance_px=8.0, stationary_span_px=2.0,
                 minimum_seconds=0.4, minimum_frames=5, max_age=0.15,
                 empty_minimum_seconds=2.0, empty_minimum_frames=20,
                 restart_empty_minimum_seconds=None,
                 restart_empty_minimum_frames=None):
        restart_empty_minimum_seconds = (
            minimum_seconds if restart_empty_minimum_seconds is None
            else restart_empty_minimum_seconds
        )
        restart_empty_minimum_frames = (
            minimum_frames if restart_empty_minimum_frames is None
            else restart_empty_minimum_frames
        )
        if (not all(math.isfinite(x) and x > 0 for x in
                    (tolerance_px, stationary_span_px, minimum_seconds, max_age,
                     empty_minimum_seconds, restart_empty_minimum_seconds))
                or type(minimum_frames) is not int or minimum_frames < 2
                or type(empty_minimum_frames) is not int or empty_minimum_frames < 2
                or type(restart_empty_minimum_frames) is not int
                or restart_empty_minimum_frames < 2):
            raise ValueError('Invalid live arrival limits')
        self.tolerance_px = tolerance_px
        self.stationary_span_px = stationary_span_px
        self.minimum_seconds = minimum_seconds
        self.minimum_frames = minimum_frames
        self.max_age = max_age
        # A long window remains the conservative passive cleanup criterion.
        # The shorter window is only used by a new move request to recover a
        # completed stop after an operator has physically removed the board.
        self.empty_minimum_seconds = empty_minimum_seconds
        self.empty_minimum_frames = empty_minimum_frames
        self.restart_empty_minimum_seconds = restart_empty_minimum_seconds
        self.restart_empty_minimum_frames = restart_empty_minimum_frames
        self.motor = None
        self.last_frame = 0
        self.history = {}
        self.empty_window = None
        self.restart_empty_window = None
        self.station_reasons = {}
        self.reason = 'NO_CURRENT_IMAGE'
        self.instance = str(uuid.uuid4())
        self.sequence = 0

    def invalidate(self, reason):
        self.history.clear()
        self.empty_window = None
        self.restart_empty_window = None
        self.station_reasons.clear()
        self.reason = reason

    def set_motor(self, state, now):
        previous = self.motor or {}
        if not stopped_motor(state, now, self.max_age, allow_manual_stop=True):
            self.motor = None
            reason = ('MOTOR_STATE_' + state['state'] if isinstance(state, dict)
                      and state.get('state') in ('MANUAL_STOP', 'FAULT', 'MOVING_TO_ASSEMBLY',
                                                'MOVING_TO_INSPECTION')
                      else 'MOTOR_NOT_VERIFIABLY_STOPPED')
            self.invalidate(reason)
            return
        if (previous.get('server_instance_id') == state['server_instance_id']
                and state['timestamp_ns'] <= previous.get('timestamp_ns', 0)):
            self.invalidate('REPEATED_OR_OLD_MOTOR_STATE')
            return
        if any(previous.get(k) != state.get(k) for k in ('server_instance_id', 'motion_id', 'state')):
            self.invalidate('MOTOR_CONTEXT_CHANGED')
        # Do not echo nested live observations back into /conveyor/state.
        self.motor = {k: state.get(k) for k in ('timestamp_ns', 'state', 'moving',
                     'command_linear_x_mps', 'server_instance_id', 'motion_id')}

    def observe(self, stamp, now, observations, *, regions_clear=False):
        if not fresh_stamp(stamp, now, self.max_age) or stamp <= self.last_frame:
            self.invalidate('STALE_OR_REPEATED_IMAGE')
            return
        if self.last_frame and stamp - self.last_frame > self.max_age * 1e9:
            self.invalidate('IMAGE_GAP')
        self.last_frame = stamp
        if not stopped_motor(self.motor, now, self.max_age, allow_manual_stop=True):
            self.invalidate(self.reason if self.motor is None and self.reason.startswith('MOTOR_')
                            else 'MOTOR_NOT_VERIFIABLY_STOPPED')
            return
        self.reason = 'OBSERVING'
        if (regions_clear is True and all(not values for values in observations.values())
                and set(observations) == {'assembly', 'inspection'}):
            for name in ('empty_window', 'restart_empty_window'):
                window = getattr(self, name)
                if window is None:
                    window = dict(first=stamp, count=0)
                window.update(last=stamp, count=window['count'] + 1)
                setattr(self, name, window)
        else:
            self.empty_window = None
            self.restart_empty_window = None
        if self.motor.get('state') == 'MANUAL_STOP':
            # A manual stop is never arrival authority. It may only accumulate
            # the separate empty evidence used by an explicit operator retry.
            self.history.clear()
            self.station_reasons.clear()
            self.reason = 'MOTOR_STATE_MANUAL_STOP'
            return
        for station in set(self.history) - set(observations):
            self.history.pop(station, None)
            self.station_reasons[station] = 'MISSING_STATION_OBSERVATION'
        for station, candidates in observations.items():
            # A caller provides raw detections within the station window.
            # Two candidates are ambiguous; smoothed/held UI tracks are forbidden.
            if len(candidates) != 1:
                self.history.pop(station, None)
                self.station_reasons[station] = ('NO_BOARD_IN_STATION_WINDOW' if not candidates
                                                 else 'AMBIGUOUS_MULTIPLE_BOARDS')
                continue
            value = candidates[0]
            if (len(value) != 5 or not all(math.isfinite(x) for x in value)
                    or abs(value[0]) > self.tolerance_px):
                self.history.pop(station, None)
                self.station_reasons[station] = 'INVALID_OR_OUTSIDE_STATION_GEOMETRY'
                continue
            window = self.history.get(station)
            # The vector contains distance, centre x/y, projected body length
            # and width (all scaled to a 960px control frame).
            if window is not None:
                low = [min(a, b) for a, b in zip(window['low'], value)]
                high = [max(a, b) for a, b in zip(window['high'], value)]
                if max(b-a for a, b in zip(low, high)) > self.stationary_span_px:
                    window = None
            if window is None:
                self.sequence += 1
                window = dict(first=stamp, count=0, low=list(value), high=list(value),
                              observation_id=f'{self.instance}:{self.sequence}')
            else:
                window.update(low=low, high=high)
            window.update(last=stamp, value=list(value), count=window['count']+1)
            self.history[station] = window
            self.station_reasons[station] = 'POSITION_NOT_YET_STABLE'

    def snapshot(self, station, now):
        if not fresh_stamp(self.last_frame, now, self.max_age):
            self.invalidate('IMAGE_EVIDENCE_STALE')
        elif (self.motor is not None
              and not stopped_motor(self.motor, now, self.max_age, allow_manual_stop=True)):
            self.invalidate('MOTOR_EVIDENCE_STALE')
        window = self.history.get(station)
        at_station = bool(self.motor and self.motor.get('state') != 'MANUAL_STOP'
                          and window and window['last'] == self.last_frame
                          and window['count'] >= self.minimum_frames
                          and window['last']-window['first'] >= self.minimum_seconds*1e9)
        empty = self.empty_window
        restart_empty = self.restart_empty_window
        regions_empty = bool(
            empty and empty['last'] == self.last_frame
            and empty['count'] >= self.empty_minimum_frames
            and empty['last'] - empty['first'] >= self.empty_minimum_seconds * 1e9
        )
        restart_regions_empty = bool(
            restart_empty and restart_empty['last'] == self.last_frame
            and restart_empty['count'] >= self.restart_empty_minimum_frames
            and restart_empty['last'] - restart_empty['first']
            >= self.restart_empty_minimum_seconds * 1e9
        )
        return dict(regions_empty=regions_empty,
                    empty_frames=empty['count'] if empty else 0,
                    empty_since_ns=empty['first'] if empty else None,
                    restart_regions_empty=restart_regions_empty,
                    restart_empty_frames=restart_empty['count'] if restart_empty else 0,
                    restart_empty_since_ns=restart_empty['first'] if restart_empty else None,
                    schema_version=1, station=station, timestamp_ns=now,
                    source_image_timestamp_ns=self.last_frame,
                    status='AT_STATION' if at_station else 'UNKNOWN', at_station=at_station,
                    reason=('CURRENT_IMAGE_STABLE_AND_ZERO_COMMAND' if at_station else
                            self.station_reasons.get(station, self.reason)),
                    observation_id=window['observation_id'] if window else None,
                    stable_frames=window['count'] if window else 0,
                    distance_to_stop_px=window['value'][0] if window else None,
                    motor_state=dict(self.motor) if self.motor else None,
                    limits=dict(reference_width_px=960, tolerance_px=self.tolerance_px,
                                stationary_span_px=self.stationary_span_px,
                                minimum_seconds=self.minimum_seconds,
                                minimum_frames=self.minimum_frames,
                                max_age_seconds=self.max_age,
                                empty_minimum_seconds=self.empty_minimum_seconds,
                                empty_minimum_frames=self.empty_minimum_frames,
                                restart_empty_minimum_seconds=self.restart_empty_minimum_seconds,
                                restart_empty_minimum_frames=self.restart_empty_minimum_frames),
            basis='VISUAL_CONTINUITY_AND_ZERO_COMMAND_NOT_ENCODER_OR_UNIT_ID')


def arrival_matches(payload, station, now, max_age, server_id, motion_id, state):
    if not isinstance(payload, dict):
        return False
    motor = payload.get('motor_state')
    return (payload.get('station') == station and payload.get('status') == 'AT_STATION'
            and payload.get('at_station') is True and bool(payload.get('observation_id'))
            and fresh_stamp(payload.get('timestamp_ns'), now, max_age)
            and fresh_stamp(payload.get('source_image_timestamp_ns'), now, max_age)
            and stopped_motor(motor, now, max_age)
            and motor.get('server_instance_id') == server_id
            and motor.get('motion_id') == motion_id and motor.get('state') == state)


def _empty_matches(payload, station, now, max_age, server_id, motion_id, state,
                   *, regions_key, frames_key, since_key,
                   minimum_seconds, minimum_frames, allow_manual_stop=False):
    if not isinstance(payload, dict):
        return False
    motor = payload.get('motor_state')
    first = payload.get(since_key)
    last = payload.get('source_image_timestamp_ns')
    return (payload.get('station') == station and payload.get('at_station') is False
            and payload.get(regions_key) is True
            and type(payload.get(frames_key)) is int
            and payload[frames_key] >= minimum_frames
            and type(first) is int and type(last) is int
            and last-first >= minimum_seconds * 1e9
            and fresh_stamp(payload.get('timestamp_ns'), now, max_age)
            and fresh_stamp(last, now, max_age)
            and stopped_motor(motor, now, max_age,
                              allow_manual_stop=allow_manual_stop)
            and motor.get('server_instance_id') == server_id
            and motor.get('motion_id') == motion_id and motor.get('state') == state)


def empty_matches(payload, station, now, max_age, server_id, motion_id, state,
                  *, allow_manual_stop=False):
    """Match the conservative two-second empty-belt evidence."""
    return _empty_matches(
        payload, station, now, max_age, server_id, motion_id, state,
        regions_key='regions_empty', frames_key='empty_frames',
        since_key='empty_since_ns', minimum_seconds=2.0, minimum_frames=20,
        allow_manual_stop=allow_manual_stop,
    )


def restart_empty_matches(payload, station, now, max_age, server_id, motion_id, state,
                          *, allow_manual_stop=False):
    """Match fresh empty evidence used only at an explicit restart request."""
    return _empty_matches(
        payload, station, now, max_age, server_id, motion_id, state,
        regions_key='restart_regions_empty', frames_key='restart_empty_frames',
        since_key='restart_empty_since_ns', minimum_seconds=0.4, minimum_frames=5,
        allow_manual_stop=allow_manual_stop,
    )


def clear_belt_region(image, x_start, x_end, y_start, y_end,
                      ignore_polygons=None):
    """Conservative gray-belt evidence, not mere absence of a detected PCB.

    Fixed overview calibration: belt ~125..150, PCB <55. Entire downstream
    belt must be visible. Different lighting/materials abstain. This cannot
    prove absence of a belt-colored occluder or independently verify camera pose.
    """
    import numpy as np
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        return False
    h, w = image.shape[:2]
    if not (0 <= x_start < x_end <= 1 and 0 <= y_start < y_end <= 1):
        return False
    region = image[int(y_start*h):int(y_end*h), int(x_start*w):int(x_end*w)]
    if region.size < 300:
        return False
    lo = region.min(axis=2)
    hi = region.max(axis=2)
    belt = (lo >= 95) & (hi <= 180) & ((hi.astype(float)-lo) <= 35)
    if ignore_polygons:
        # A board parked upstream of the assembly stop is expected when
        # restarting a failed job. Exclude only its verified polygon from the
        # neutral-belt ratio; unknown/dark pixels remain a fail-safe veto.
        import cv2
        x0, y0 = int(x_start * w), int(y_start * h)
        mask = np.zeros(region.shape[:2], dtype=np.uint8)
        for polygon in ignore_polygons:
            points = np.asarray(polygon, dtype=np.float32)
            if (points.ndim != 2 or points.shape[1] != 2 or points.shape[0] < 3
                    or not np.isfinite(points).all()):
                continue
            local = np.rint(points - np.asarray((x0, y0), dtype=np.float32)).astype(np.int32)
            cv2.fillPoly(mask, [local], 1)
        visible = mask == 0
        visible_count = int(np.count_nonzero(visible))
        if visible_count < 300 or visible_count < int(region.shape[0] * region.shape[1] * .50):
            return False
        return bool(np.mean(belt[visible]) >= .98)
    return bool(np.mean(belt) >= .98)
