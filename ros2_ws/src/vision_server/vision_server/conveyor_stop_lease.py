"""Finite-lived conveyor-stop evidence carried by Bool plus DDS metadata.

The wire topic stays std_msgs/Bool. Publishers must send periodic fresh samples;
one latched true is insufficient. The DDS writer GID is a transport session ID,
not a physical safety interlock or an application-level conveyor controller ID.
"""

import math
import time
from collections.abc import Mapping


class ConveyorStopLease:
    def __init__(self, max_age_sec=1.0, *, monotonic=time.monotonic,
                 wall_time_ns=time.time_ns):
        self.max_age_sec = float(max_age_sec)
        if not math.isfinite(self.max_age_sec) or self.max_age_sec <= 0:
            raise ValueError('conveyor heartbeat max age must be finite and positive')
        self._monotonic = monotonic
        self._wall_time_ns = wall_time_ns
        self._writer = None
        self._retired_writers = set()
        self._source_ns = None
        self._received = None
        self._true_count = 0
        self._generation = 0

    def _invalidate(self):
        self._true_count = 0
        self._generation += 1

    def observe(self, stopped, message_info):
        try:
            # Jazzy passes a metadata dict; newer bindings may expose attributes.
            value = (message_info.__getitem__ if isinstance(message_info, Mapping)
                     else lambda key: getattr(message_info, key))
            writer = bytes(value('publisher_gid'))
            source_ns = int(value('source_timestamp'))
            if not writer or not any(writer) or source_ns <= 0:
                raise ValueError('missing DDS publisher identity or source time')
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
            self._invalidate()
            return
        now, wall_ns = self._monotonic(), self._wall_time_ns()
        age = (wall_ns - source_ns) / 1_000_000_000
        if not 0 <= age <= self.max_age_sec:
            self._invalidate()
            return
        if writer != self._writer:
            self._invalidate()
            if writer in self._retired_writers:
                return
            if self._writer is not None:
                self._retired_writers.add(self._writer)
            self._writer, self._source_ns = writer, None
            self._received = None
        if self._source_ns is not None and source_ns <= self._source_ns:
            self._invalidate()
            return
        if self._received is not None and not 0 <= now - self._received <= self.max_age_sec:
            self._invalidate()
        self._source_ns, self._received = source_ns, now
        if stopped is True:
            self._true_count += 1
        else:
            self._invalidate()

    def current_session(self):
        if self._true_count < 2 or self._received is None or self._source_ns is None:
            return None
        receipt_age = self._monotonic() - self._received
        source_age = (self._wall_time_ns() - self._source_ns) / 1_000_000_000
        if not (0 <= receipt_age <= self.max_age_sec and
                0 <= source_age <= self.max_age_sec):
            self._invalidate()
            return None
        return self._generation

    def permits(self, session):
        return session is not None and self.current_session() == session
