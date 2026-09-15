#!/usr/bin/env python3
"""Run D435 eye-in-hand SMD pick sequence with detected gripper-camera target."""

import argparse
import json
import re
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CALIBRATION_ROOT = PROJECT_ROOT / 'calibration'
PARTS_CONFIG = PROJECT_ROOT / 'vision_assembly' / 'config' / 'physical_board.json'
DETECT_SCRIPT = CALIBRATION_ROOT / 'run_small_part_detection.sh'
PICK_SCRIPT = CALIBRATION_ROOT / 'run_full_pick_place_same_spot.sh'
DEFAULT_TARGET_FILE = CALIBRATION_ROOT / 'data' / 'smd_gripper_camera_last.json'
PHYSICAL_CONFIG = PARTS_CONFIG


def run(command, label, timeout=None):
    print(f'\n=== {label} ===', flush=True)
    print(' '.join(str(value) for value in command), flush=True)
    try:
        completed = subprocess.run(command, check=False, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f'{label} timed out after {timeout:.1f} s') from exc
    if completed.returncode != 0:
        raise RuntimeError(f'{label} failed with exit code {completed.returncode}')


def canonical_slot_id(slot_id):
    normalized = slot_id.strip().lower().replace('-', '_')
    if normalized.startswith('smd_capacitor_'):
        return normalized
    m = re.fullmatch(r's(\d+)', normalized)
    if m:
        index = int(m.group(1))
        return f'smd_capacitor_{index:02d}'
    m = re.fullmatch(r'(\d+)', normalized)
    if m:
        index = int(m.group(1))
        return f'smd_capacitor_{index:02d}'
    if not normalized.startswith('smd') and not normalized.startswith('right_white'):
        m = re.fullmatch(r'smd(capacitor)?_?(\d+)', normalized)
        if m:
            index = int(m.group(2))
            return f'smd_capacitor_{index:02d}'
    return normalized


def load_smd_slot_size(slot_id):
    slots = json.loads(PHYSICAL_CONFIG.read_text(encoding='utf-8'))['component_slot_overrides']['SMD Capacitor']['slots']
    target = canonical_slot_id(slot_id)
    for slot in slots:
        if slot.get('slot_id', '').lower() == target:
            nominal = slot.get('nominal_size_mm')
            if not nominal:
                raise RuntimeError(f'Slot {slot_id} exists but nominal_size_mm is missing')
            return (
                float(nominal['x']),
                float(nominal['y']),
                float(nominal['height']),
            ), target
    raise RuntimeError(
        f'SMD slot "{slot_id}" not found. Expected one of: '
        + ', '.join(item.get('slot_id', '') for item in slots)
    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--slot-id', help='Use nominal size from physical_board.json')
    parser.add_argument('--part-length-mm', type=float, default=None)
    parser.add_argument('--part-width-mm', type=float, default=None)
    parser.add_argument('--part-height-mm', type=float, default=None)
    parser.add_argument('--part-color', choices=('light', 'orange', 'brown', 'any'), default='light')
    parser.add_argument('--frames', type=int, default=30)
    parser.add_argument('--refine-frames', type=int, default=15)
    parser.add_argument('--cell-col', type=int, default=2)
    parser.add_argument('--cell-row', type=int, default=2)
    parser.add_argument('--min-corners', type=int, default=12)
    parser.add_argument('--scan-all-black-cells', action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument('--depth-topic', default='/camera/camera/aligned_depth_to_color/image_raw')
    parser.add_argument('--detection-timeout-sec', type=float, default=15.0)
    parser.add_argument('--max-target-age-sec', type=float, default=120.0)
    parser.add_argument('--approach-offset-mm', type=float, default=50.0)
    parser.add_argument('--grasp-z-offset-mm', type=float, default=None,
                        help='physically calibrated final TCP Z relative to component top')
    parser.add_argument('--extra-descent-mm', type=float, default=None,
                        help=argparse.SUPPRESS)
    parser.add_argument('--xy-speed-percent', type=int, default=40)
    parser.add_argument('--vertical-speed-percent', type=int, default=40)
    parser.add_argument('--grasp-descent-speed-percent', type=int, default=15)
    parser.add_argument('--rotation-speed-percent', type=int, default=50)
    parser.add_argument('--lift-mm', type=float, default=50.0)
    parser.add_argument('--retreat-mm', type=float, default=50.0)
    parser.add_argument('--cycle-speed-percent', type=int, default=40)
    parser.add_argument('--gripper-open-position', type=int, default=100)
    parser.add_argument('--gripper-close-position', type=int, default=5)
    parser.add_argument('--gripper-axis', choices=('tool_x', 'tool_y'), default='tool_y')
    parser.add_argument('--return-point', default='ClosePin')
    parser.add_argument('--return-safe-clearance-mm', type=float, default=100.0)
    parser.add_argument('--no-return', action='store_true')
    parser.add_argument('--approach-only', action='store_true',
                        help='detect, align, and stop 50 mm above the part without gripping')
    parser.add_argument('--target-file', type=Path, default=DEFAULT_TARGET_FILE)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-full-cycle', action='store_true')
    parser.add_argument('--confirm-approach-only', action='store_true')
    parser.add_argument('--allow-provisional-calibration', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    if args.approach_only:
        if args.execute != args.confirm_approach_only:
            raise SystemExit('실제 5 cm 접근에는 --execute와 --confirm-approach-only가 모두 필요합니다')
        if args.confirm_full_cycle:
            raise SystemExit('--approach-only cannot use --confirm-full-cycle')
        args.approach_offset_mm = 50.0
    elif args.execute != args.confirm_full_cycle:
        raise SystemExit('실제 실행에는 --execute와 --confirm-full-cycle이 모두 필요합니다')
    elif args.confirm_approach_only:
        raise SystemExit('--confirm-approach-only requires --approach-only')
    if args.dry_run and args.execute:
        raise SystemExit('--dry-run and --execute cannot be combined')
    if args.extra_descent_mm is not None:
        if args.grasp_z_offset_mm is not None:
            raise SystemExit('use only --grasp-z-offset-mm')
        args.grasp_z_offset_mm = -args.extra_descent_mm
    if args.grasp_z_offset_mm is not None and not -10.0 <= args.grasp_z_offset_mm <= 20.0:
        raise SystemExit('--grasp-z-offset-mm must be between -10 and 20')
    if args.execute and not args.approach_only and args.grasp_z_offset_mm is None:
        raise SystemExit('full pick requires a physically calibrated --grasp-z-offset-mm')
    if args.frames <= 0 or args.refine_frames <= 0:
        raise SystemExit('frame counts must be positive')
    if args.part_length_mm is None and args.part_width_mm is None and args.part_height_mm is None:
        # Use slot nominal values when provided; otherwise use conservative default
        if args.slot_id:
            (length, width, height), resolved_slot = load_smd_slot_size(args.slot_id)
            print(f'Using physical_board nominal size for slot "{resolved_slot}"')
        else:
            length, width, height = 6.0, 3.5, 2.5
            resolved_slot = None
    elif args.slot_id:
        size, resolved_slot = load_smd_slot_size(args.slot_id)
        length, width, height = (
            args.part_length_mm if args.part_length_mm is not None else size[0],
            args.part_width_mm if args.part_width_mm is not None else size[1],
            args.part_height_mm if args.part_height_mm is not None else size[2],
        )
    else:
        length = args.part_length_mm if args.part_length_mm is not None else 6.0
        width = args.part_width_mm if args.part_width_mm is not None else 3.5
        height = args.part_height_mm if args.part_height_mm is not None else 2.5
        resolved_slot = None

    detect_command = [
        str(DETECT_SCRIPT),
        '--part-length-mm', str(length),
        '--part-width-mm', str(width),
        '--part-height-mm', str(height),
        '--part-color', args.part_color,
        '--frames', str(args.frames),
        '--cell-col', str(args.cell_col),
        '--cell-row', str(args.cell_row),
        '--min-corners', str(args.min_corners),
        '--depth-topic', args.depth_topic,
        '--output-file', str(args.target_file),
    ]
    if args.scan_all_black_cells:
        detect_command.append('--scan-all-black-cells')
    else:
        detect_command.append('--no-scan-all-black-cells')
    run(detect_command, '1/3 DETECT PART ON /camera/camera', timeout=args.detection_timeout_sec)

    pick_command = [
        str(PICK_SCRIPT),
        '--part-length-mm', str(length),
        '--part-width-mm', str(width),
        '--part-height-mm', str(height),
        '--part-color', args.part_color,
        '--frames', str(args.frames),
        '--refine-frames', str(args.refine_frames),
        '--depth-topic', args.depth_topic,
        '--target-file', str(args.target_file),
        '--max-target-age-sec', str(args.max_target_age_sec),
        '--skip-detection',
        '--approach-offset-mm', str(args.approach_offset_mm),
        '--xy-speed-percent', str(args.xy_speed_percent),
        '--vertical-speed-percent', str(args.vertical_speed_percent),
        '--grasp-descent-speed-percent', str(args.grasp_descent_speed_percent),
        '--rotation-speed-percent', str(args.rotation_speed_percent),
        '--lift-mm', str(args.lift_mm),
        '--retreat-mm', str(args.retreat_mm),
        '--cycle-speed-percent', str(args.cycle_speed_percent),
        '--gripper-open-position', str(args.gripper_open_position),
        '--gripper-close-position', str(args.gripper_close_position),
        '--gripper-axis', args.gripper_axis,
        '--return-point', args.return_point,
        '--return-safe-clearance-mm', str(args.return_safe_clearance_mm),
    ]
    if args.grasp_z_offset_mm is not None:
        pick_command.extend(['--grasp-z-offset-mm', str(args.grasp_z_offset_mm)])
    if args.allow_provisional_calibration:
        pick_command.append('--allow-provisional-calibration')
    if args.no_return:
        pick_command.append('--no-return')
    if args.scan_all_black_cells:
        pick_command.append('--scan-all-black-cells')
    else:
        pick_command.append('--no-scan-all-black-cells')
    if args.execute:
        pick_command.append('--execute')
        if args.approach_only:
            pick_command.extend(['--approach-only', '--confirm-approach-only'])
        else:
            pick_command.append('--confirm-full-cycle')
    else:
        if args.approach_only:
            pick_command.append('--approach-only')
        pick_command.append('--dry-run')

    run(pick_command, '2/3 ALIGN + APPROACH 5 CM' if args.approach_only else '2/3 PICK + PLACE-AT-SAME-SPOT')


if __name__ == '__main__':
    main()
