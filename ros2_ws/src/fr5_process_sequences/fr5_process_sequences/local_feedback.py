"""Dedicated, same-host feedback receiver with source-time freshness validation."""
import os
import socket
import struct
import threading
import time

HEADER = struct.Struct('!8sQQQII')
MAGIC = b'FR5FB002'


class LocalFeedbackReceiver:
    def __init__(self, name, callback, decode, *, max_age=.25, clock=time.monotonic_ns):
        self.callback, self.decode, self.max_age, self.clock = callback, decode, max_age, clock
        self.instance = self.sequence = self.last_source = self.last_received = None
        self.stats = dict(transport='unix_datagram_v2', received=0, rejected=0,
                          max_source_gap_ms=0., max_receive_gap_ms=0., max_delivery_age_ms=0.)
        self.capabilities = 0
        self.error = None
        self._stop = threading.Event()
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            # Abstract addresses disappear on close; a second API cannot replace us.
            self.socket.bind('\0' + name)
            self.socket.settimeout(.05)
        except BaseException:
            self.socket.close()
            raise
        self.thread = threading.Thread(target=self._run, daemon=True, name='fr5-local-feedback')
        self.thread.start()

    def accept(self, packet):
        now = self.clock()
        try:
            if len(packet) < HEADER.size: raise ValueError('short feedback header')
            magic, instance, sequence, stamp, size, capabilities = HEADER.unpack_from(packet)
            if magic != MAGIC or size != len(packet)-HEADER.size:
                raise ValueError('invalid local feedback envelope')
            age = (now-stamp)/1e9
            if not 0 <= age <= self.max_age: raise ValueError('stale or future local feedback')
            if self.instance is not None and instance != self.instance:
                raise ValueError('driver instance changed; restart API before another operation')
            if self.sequence is not None and (sequence <= self.sequence or stamp <= self.last_source):
                raise ValueError('replayed or reordered local feedback')
            state = self.decode(packet[HEADER.size:])
            # A communication-error sample must not impersonate healthy zero state.
            if getattr(state, 'reconnect_flag', 0): raise ValueError('driver reports disconnected feedback')
            if self.last_source is not None:
                self.stats['max_source_gap_ms'] = max(self.stats['max_source_gap_ms'], (stamp-self.last_source)/1e6)
                self.stats['max_receive_gap_ms'] = max(self.stats['max_receive_gap_ms'], (now-self.last_received)/1e6)
            self.capabilities = capabilities
            self.instance, self.sequence = instance, sequence
            self.last_source, self.last_received = stamp, now
            self.stats['received'] += 1
            self.stats['max_delivery_age_ms'] = max(self.stats['max_delivery_age_ms'], age*1000)
            self.error = None
            self.callback(state, stamp/1e9)
        except (ValueError, struct.error, RuntimeError) as error:
            self.stats['rejected'] += 1
            self.error = str(error)

    def _run(self):
        try:
            while not self._stop.is_set():
                try:
                    packet, _, flags, _ = self.socket.recvmsg(65536)
                    if flags & socket.MSG_TRUNC:
                        self.error = 'truncated local feedback'; self.stats['rejected'] += 1
                        continue
                    self.accept(packet)
                except socket.timeout:
                    continue
        except OSError as error:
            if not self._stop.is_set(): self.error = str(error)
        except Exception as error:
            self.error = repr(error)  # A dead receiver cannot update source time.

    def continuous_capable(self):
        # Never authorize from stale, rejected, or previous-driver evidence.
        stamp = self.last_source
        return (stamp is not None and self.error is None
                and 0 <= (self.clock()-stamp)/1e9 <= self.max_age
                and bool(self.capabilities & 1))

    def snapshot(self):
        return dict(self.stats, error=self.error, source_sequence=self.sequence,
                    driver_instance=self.instance, continuous_movej_supported=self.continuous_capable(),
                    source_age_ms=None if self.last_source is None else (self.clock()-self.last_source)/1e6)

    def close(self):
        self._stop.set()
        self.thread.join(timeout=1)
        self.socket.close()
