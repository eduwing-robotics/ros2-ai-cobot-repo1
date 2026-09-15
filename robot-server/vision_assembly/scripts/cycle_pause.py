"""Cooperative whole-cycle barrier shared by existing launcher children."""
import json
import os
from pathlib import Path
import time

_CACHE = [None, 0., None]
PAUSED = {'pause_requested', 'paused', 'resume_requested'}


def state(fresh=False):
    path = os.environ.get('FR5_ASSEMBLY_CONTROL_RECORD')
    if not path:
        return None
    now = time.monotonic()
    if fresh or _CACHE[0] != path or now - _CACHE[1] > .05:
        record = json.loads(Path(path).read_text())
        if record.get('operation_id') != os.environ.get('FR5_ASSEMBLY_EXECUTION_ID'):
            raise RuntimeError('whole-cycle control identity mismatch')
        if record.get('server_pid') is not None:
            process = Path('/proc') / str(record['server_pid']) / 'stat'
            if not process.exists() or process.read_text().split()[21] != record['server_process_start']:
                raise RuntimeError('whole-cycle API owner lost; no automatic replay')
        _CACHE[:] = [path, now, record]
    return _CACHE[2]


def clock():
    record = state()
    now = time.monotonic()
    if record is None:
        return now
    started = record.get('pause_started_monotonic') if record.get('status') in PAUSED else None
    return now - record.get('paused_seconds', 0.) - (max(0., now-started) if started is not None else 0.)


def checkpoint(spin=None):
    while True:
        record = state(fresh=True)
        if record is None or record['status'] in ('starting', 'running'):
            return
        if record['status'] not in PAUSED:
            raise RuntimeError('whole-cycle stopped or lost: ' + record['status'])
        if spin is None:
            time.sleep(.02)
        else:
            spin()
