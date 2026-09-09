#!/usr/bin/env python3
"""Capture a live RGB-D tray target, then plan/execute a 50 mm hover only."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

from tray_hover_contract import (
    TrayHoverContractError,
    load_contract,
    normalize_part_type,
)


def parse_args(argv=None):
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=root / 'config/tray_hover_5cm.json')
    parser.add_argument('--part-type', required=True)
    parser.add_argument('--instance', type=int, default=1)
    parser.add_argument('--frames', type=int)
    parser.add_argument('--max-jitter-mm', type=float)
    parser.add_argument('--max-angle-jitter-deg', type=float)
    parser.add_argument('--capture-timeout-sec', type=float)
    parser.add_argument('--max-state-age-sec', type=float)
    parser.add_argument('--state-topic')
    parser.add_argument('--registration-topic')
    parser.add_argument(
        '--target-file',
        type=Path,
        default=root / 'data/tray_hover_target_last.json',
    )
    parser.add_argument('--horizontal-speed-percent', type=int)
    parser.add_argument('--vertical-speed-percent', type=int)
    parser.add_argument('--rotation-speed-percent', type=int)
    parser.add_argument('--safe-clearance-mm', type=float)
    parser.add_argument('--max-distance-mm', type=float)
    parser.add_argument('--max-rotation-deg', type=float, default=90.0)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-hover-only', action='store_true')
    parser.add_argument(
        '--confirm-move',
        action='store_true',
        help='legacy alias for --confirm-hover-only',
    )
    args = parser.parse_args(argv)
    try:
        contract = load_contract(args.config)
        args.part_type = normalize_part_type(args.part_type, contract)
    except TrayHoverContractError as exc:
        parser.error(str(exc))
    if args.instance < 1:
        parser.error('--instance must be at least 1')
    confirmed = bool(args.confirm_hover_only or args.confirm_move)
    if args.execute != confirmed:
        parser.error('actual motion requires --execute and --confirm-hover-only together')
    if args.dry_run and args.execute:
        parser.error('--dry-run and --execute cannot be combined')
    return args, contract


def append_option(command, name, value):
    if value is not None:
        command.extend([name, str(value)])


def build_commands(args, contract):
    scripts = Path(__file__).resolve().parent
    capture = [
        sys.executable,
        str(scripts / 'capture_live_tray_hover_target.py'),
        '--config',
        str(args.config),
        '--part-type',
        args.part_type,
        '--instance',
        str(args.instance),
        '--output',
        str(args.target_file),
    ]
    append_option(capture, '--frames', args.frames)
    append_option(capture, '--max-jitter-mm', args.max_jitter_mm)
    append_option(capture, '--max-angle-jitter-deg', args.max_angle_jitter_deg)
    append_option(capture, '--timeout-sec', args.capture_timeout_sec)
    append_option(capture, '--max-state-age-sec', args.max_state_age_sec)
    append_option(capture, '--state-topic', args.state_topic)
    append_option(capture, '--registration-topic', args.registration_topic)

    approach = [
        sys.executable,
        str(scripts / 'move_tray_part_approach.py'),
        '--config',
        str(args.config),
        '--target-file',
        str(args.target_file),
        '--part-type',
        args.part_type,
        '--instance',
        str(args.instance),
        '--approach-offset-mm',
        '50',
        '--max-target-age-sec',
        '15',
    ]
    append_option(
        approach, '--horizontal-speed-percent', args.horizontal_speed_percent
    )
    append_option(approach, '--vertical-speed-percent', args.vertical_speed_percent)
    append_option(approach, '--rotation-speed-percent', args.rotation_speed_percent)
    append_option(approach, '--safe-clearance-mm', args.safe_clearance_mm)
    append_option(approach, '--max-distance-mm', args.max_distance_mm)
    append_option(approach, '--max-rotation-deg', args.max_rotation_deg)
    if args.execute:
        approach.extend(['--execute', '--confirm-hover-only'])
    else:
        approach.append('--dry-run')
    return capture, approach


def main(argv=None):
    args, contract = parse_args(argv)
    capture, approach = build_commands(args, contract)
    profile = contract['parts'][args.part_type]
    print('NON-SMD LIVE TRAY 50 MM HOVER', flush=True)
    print(
        f'Target: {args.part_type} #{args.instance} '
        f'({profile["display_name"]})',
        flush=True,
    )
    print(
        'D435 startup: not requested; using the already-running tray RGB-D topics',
        flush=True,
    )
    print('Contact pick/gripper action: disabled in this runner', flush=True)
    print('Capture command:', shlex.join(capture), flush=True)
    try:
        subprocess.run(capture, check=True)
    except subprocess.CalledProcessError as exc:
        print(f'ERROR: live target capture failed (exit={exc.returncode})', file=sys.stderr)
        return exc.returncode or 2
    print('Approach command:', shlex.join(approach), flush=True)
    try:
        subprocess.run(approach, check=True)
    except subprocess.CalledProcessError as exc:
        print(f'ERROR: 50 mm hover stage failed (exit={exc.returncode})', file=sys.stderr)
        return exc.returncode or 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
