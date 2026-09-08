#!/usr/bin/env python3
"""Bounded fresh SMD observations; no robot movement or grasp retries."""
import argparse
import json
from pathlib import Path
import subprocess
import time

from fixed_cycle_snapshot import atomic_write
from merge_smd_retry_captures import merge_captures

ROOT = Path(__file__).resolve().parents[2]


def capture_with_retries(output, *, attempts=4, runner=subprocess.run, now=time.time):
    if not 1 <= attempts <= 4:
        raise ValueError('SMD attempts must be between 1 and 4')
    output = Path(output)
    # A unique run directory prevents historical output from being accepted.
    if output.exists():
        raise RuntimeError('SMD output already exists; use a fresh run directory')
    inputs = []
    for attempt in range(1, attempts + 1):
        target = output.with_name(f'{output.stem}_attempt_{attempt}.json')
        if target.exists():
            raise RuntimeError('SMD attempt output already exists')
        command = [str(ROOT / '.venv-vision/bin/python'),
                   str(ROOT / 'vision_assembly/scripts/capture_smd_close_target.py'),
                   '--all-instances', '--set-index', '1', '--frames', '24',
                   '--raw-color-topic', '/camera/camera/color/image_raw', '--output', str(target)]
        print(f'SMD detection attempt {attempt}/{attempts}', flush=True)
        with target.with_suffix('.log').open('w') as log:
            result = runner(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                            timeout=90, check=False)
        if result.returncode == 3:
            # No complete observation: discard earlier candidates, never replay.
            inputs.clear()
            print('SMD observation incomplete; collecting new frames', flush=True)
            continue
        if result.returncode not in (0, 2) or not target.exists():
            raise RuntimeError(f'SMD capture error {result.returncode}; see {target.with_suffix(".log")}')
        inputs.append((str(target), json.loads(target.read_text())))
        try:
            merged = merge_captures(inputs, now())
        except RuntimeError as error:
            if 'still pending' not in str(error):
                raise
            print(str(error), flush=True)
            continue
        merged['detection_attempts'] = attempt
        atomic_write(output, merged)
        print(f'SMD all five validated after {attempt} attempt(s)', flush=True)
        return merged
    raise RuntimeError(f'SMD detection exhausted after {attempts} attempts; no assembly targets published')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    capture_with_retries(args.output)


if __name__ == '__main__':
    main()
