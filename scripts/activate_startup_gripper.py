#!/usr/bin/env python3
"""Activate the gripper under shared actuator locks; preserve recovery records."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]

def main():
    runtime = ROOT / 'runtime/assembly_cycles'
    runtime.mkdir(parents=True, exist_ok=True)
    with (runtime/'launcher.lock').open('a') as launcher, (runtime/'step_operation.lock').open('a') as operation:
        for handle in (launcher, operation):
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        directory = ROOT/'runtime/assembly_stack/gripper_startup'
        directory.mkdir(parents=True, exist_ok=True)
        record = directory / (str(time.time_ns()) + '.json')
        record.write_text(json.dumps(dict(assembly_motion_started=False, activation_outcome_unknown=False)))
        subprocess.run([sys.executable, str(ROOT/'vision_assembly/scripts/prepare_cycle_gripper.py'),
                        '--activation-only', '--safety-record', str(record)], check=True, timeout=45)

if __name__ == '__main__':
    main()
