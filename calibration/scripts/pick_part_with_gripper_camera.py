#!/usr/bin/env python3
"""Profile-driven markerless D435 part approach/pick workflow."""

import argparse
import json
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CALIBRATION_ROOT = PROJECT_ROOT / 'calibration'
DEFAULT_PROFILE_CONFIG = (
    CALIBRATION_ROOT / 'config' / 'gripper_part_profiles.json'
)
DETECT_SCRIPT = CALIBRATION_ROOT / 'run_small_part_detection.sh'
PICK_SCRIPT = CALIBRATION_ROOT / 'run_full_pick_place_same_spot.sh'


def normalized_name(value):
    return value.strip().lower().replace('-', '_').replace(' ', '_')


def load_catalog(path):
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        profiles = payload['profiles']
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'cannot load part profile config {path}: {exc}') from exc
    if not isinstance(profiles, dict) or not profiles:
        raise RuntimeError(f'{path} contains no part profiles')
    return payload


def resolve_profile(catalog, requested_name):
    lookup = {}
    for profile_id, profile in catalog['profiles'].items():
        names = [profile_id, *profile.get('aliases', [])]
        for name in names:
            key = normalized_name(str(name))
            previous = lookup.get(key)
            if previous is not None and previous != profile_id:
                raise RuntimeError(
                    f'duplicate part alias {name!r}: {previous}, {profile_id}'
                )
            lookup[key] = profile_id
    key = normalized_name(requested_name)
    if key not in lookup:
        raise RuntimeError(
            f'unknown part type {requested_name!r}; available: '
            + ', '.join(sorted(catalog['profiles']))
        )
    profile_id = lookup[key]
    return profile_id, dict(catalog['profiles'][profile_id])


def print_profiles(catalog):
    print('Available markerless gripper-camera part profiles:')
    for profile_id, profile in catalog['profiles'].items():
        size = profile['nominal_size_mm']
        orientation = profile['orientation_mode']
        status = (
            'PICK_VALIDATED' if profile.get('full_pick_validated') is True
            else 'IMPLEMENTED / PHYSICAL PICK BLOCKED'
        )
        print(
            f'  {profile_id:14s} '
            f'{size["length"]:7.3f} x {size["width"]:7.3f} x '
            f'{size["height"]:7.3f} mm  '
            f'{profile["segmentation_mode"]:6s}  {orientation:9s}  {status}'
        )


def run(command, label, timeout=None):
    print(f'\n=== {label} ===', flush=True)
    print(' '.join(str(value) for value in command), flush=True)
    try:
        completed = subprocess.run(
            command, check=False, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f'{label} timed out after {timeout:.1f} s') from exc
    if completed.returncode != 0:
        raise RuntimeError(f'{label} failed with exit code {completed.returncode}')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            'Detect one centred component with the eye-in-hand D435, then '
            'run the closed-loop 5 cm approach or same-position pick cycle.'
        )
    )
    parser.add_argument('--profile-config', type=Path, default=DEFAULT_PROFILE_CONFIG)
    parser.add_argument('--part-type', help='gpu, hbm, vrm, power_module, inductor, or smd_capacitor')
    parser.add_argument('--list-parts', action='store_true')
    parser.add_argument('--part-length-mm', type=float)
    parser.add_argument('--part-width-mm', type=float)
    parser.add_argument('--part-height-mm', type=float)
    parser.add_argument('--part-shape', choices=('rectangle', 'circle'))
    parser.add_argument('--segmentation-mode', choices=('bright', 'dark', 'depth'))
    parser.add_argument('--part-color', choices=('light', 'orange', 'brown', 'any'))
    parser.add_argument('--orientation-mode', choices=('long_axis', 'preserve'))
    parser.add_argument('--height-tolerance-mm', type=float)
    parser.add_argument('--depth-mask-height-fraction', type=float)
    parser.add_argument('--frames', type=int, default=30)
    parser.add_argument('--refine-frames', type=int, default=15)
    parser.add_argument('--scan-all-black-cells', action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument('--depth-topic', default='/camera/camera/aligned_depth_to_color/image_raw')
    parser.add_argument('--detection-timeout-sec', type=float, default=20.0)
    parser.add_argument('--max-target-age-sec', type=float, default=120.0)
    parser.add_argument('--target-file', type=Path)
    parser.add_argument('--approach-offset-mm', type=float, default=50.0)
    parser.add_argument('--grasp-z-offset-mm', type=float)
    parser.add_argument('--xy-speed-percent', type=int, default=20)
    parser.add_argument('--vertical-speed-percent', type=int, default=15)
    parser.add_argument('--grasp-descent-speed-percent', type=int, default=15)
    parser.add_argument('--rotation-speed-percent', type=int, default=20)
    parser.add_argument('--lift-mm', type=float, default=50.0)
    parser.add_argument('--retreat-mm', type=float, default=50.0)
    parser.add_argument('--cycle-speed-percent', type=int, default=20)
    parser.add_argument('--gripper-open-position', type=int)
    parser.add_argument('--gripper-close-position', type=int)
    parser.add_argument('--gripper-axis', choices=('tool_x', 'tool_y'))
    parser.add_argument('--return-point', default='ClosePin')
    parser.add_argument('--return-safe-clearance-mm', type=float, default=100.0)
    parser.add_argument('--no-return', action='store_true')
    parser.add_argument('--approach-only', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-full-cycle', action='store_true')
    parser.add_argument('--confirm-approach-only', action='store_true')
    parser.add_argument('--allow-provisional-calibration', action='store_true')
    parser.add_argument(
        '--allow-unvalidated-part-profile', action='store_true',
        help=(
            'explicitly unlock robot motion for a profile whose detection or '
            'contact settings have not been physically validated'
        ),
    )
    args = parser.parse_args(argv)
    return parser, args


def profile_value(args, name, profile, profile_name=None):
    value = getattr(args, name)
    if value is not None:
        return value
    return profile[profile_name or name]


def build_detection_command(values):
    command = [
        str(DETECT_SCRIPT),
        '--part-profile-id', values['profile_id'],
        '--part-length-mm', str(values['length_mm']),
        '--part-width-mm', str(values['width_mm']),
        '--part-height-mm', str(values['height_mm']),
        '--part-shape', values['shape'],
        '--segmentation-mode', values['segmentation_mode'],
        '--part-color', values['color_profile'],
        '--orientation-mode', values['orientation_mode'],
        '--height-tolerance-mm', str(values['height_tolerance_mm']),
        '--depth-mask-height-fraction', str(values['depth_mask_height_fraction']),
        '--frames', str(values['frames']),
        '--depth-topic', values['depth_topic'],
        '--output-file', str(values['target_file']),
        '--output-dir', str(values['debug_dir']),
    ]
    command.append(
        '--scan-all-black-cells'
        if values['scan_all_black_cells']
        else '--no-scan-all-black-cells'
    )
    return command


def build_pick_command(values, args):
    command = [
        str(PICK_SCRIPT),
        '--part-profile-id', values['profile_id'],
        '--part-length-mm', str(values['length_mm']),
        '--part-width-mm', str(values['width_mm']),
        '--part-height-mm', str(values['height_mm']),
        '--part-shape', values['shape'],
        '--segmentation-mode', values['segmentation_mode'],
        '--part-color', values['color_profile'],
        '--orientation-mode', values['orientation_mode'],
        '--height-tolerance-mm', str(values['height_tolerance_mm']),
        '--depth-mask-height-fraction', str(values['depth_mask_height_fraction']),
        '--frames', str(args.frames),
        '--refine-frames', str(args.refine_frames),
        '--depth-topic', args.depth_topic,
        '--target-file', str(values['target_file']),
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
        '--gripper-open-position', str(values['gripper_open_position']),
        '--gripper-axis', values['gripper_axis'],
        '--return-point', args.return_point,
        '--return-safe-clearance-mm', str(args.return_safe_clearance_mm),
    ]
    if values['gripper_close_position'] is not None:
        command.extend([
            '--gripper-close-position',
            str(values['gripper_close_position']),
        ])
    if args.grasp_z_offset_mm is not None:
        command.extend(['--grasp-z-offset-mm', str(args.grasp_z_offset_mm)])
    if args.allow_provisional_calibration:
        command.append('--allow-provisional-calibration')
    if args.allow_unvalidated_part_profile:
        command.append('--allow-unvalidated-part-profile')
    if args.no_return:
        command.append('--no-return')
    command.append(
        '--scan-all-black-cells'
        if args.scan_all_black_cells else '--no-scan-all-black-cells'
    )
    if args.execute:
        command.append('--execute')
        if args.approach_only:
            command.extend(['--approach-only', '--confirm-approach-only'])
        else:
            command.append('--confirm-full-cycle')
    else:
        if args.approach_only:
            command.append('--approach-only')
        command.append('--dry-run')
    return command


def main(argv=None):
    parser, args = parse_args(argv)
    try:
        catalog = load_catalog(args.profile_config)
    except RuntimeError as exc:
        parser.error(str(exc))
    if args.list_parts:
        print_profiles(catalog)
        return
    if not args.part_type:
        parser.error('--part-type is required unless --list-parts is used')
    try:
        profile_id, profile = resolve_profile(catalog, args.part_type)
    except RuntimeError as exc:
        parser.error(str(exc))

    if args.approach_only:
        if args.execute != args.confirm_approach_only:
            parser.error(
                '실제 5 cm 접근에는 --execute와 '
                '--confirm-approach-only가 모두 필요합니다'
            )
        if args.confirm_full_cycle:
            parser.error('--approach-only cannot use --confirm-full-cycle')
        args.approach_offset_mm = 50.0
    elif args.execute != args.confirm_full_cycle:
        parser.error(
            '실제 전체 파지에는 --execute와 '
            '--confirm-full-cycle이 모두 필요합니다'
        )
    elif args.confirm_approach_only:
        parser.error('--confirm-approach-only requires --approach-only')
    if args.dry_run and args.execute:
        parser.error('--dry-run and --execute cannot be combined')
    if args.frames <= 0 or args.refine_frames <= 0:
        parser.error('frame counts must be positive')
    if args.detection_timeout_sec <= 0.0:
        parser.error('--detection-timeout-sec must be positive')
    if not 50.0 <= args.approach_offset_mm <= 130.0:
        parser.error('--approach-offset-mm must be between 50 and 130')
    speed_values = (
        args.xy_speed_percent,
        args.vertical_speed_percent,
        args.grasp_descent_speed_percent,
        args.rotation_speed_percent,
        args.cycle_speed_percent,
    )
    if any(not 1 <= value <= 50 for value in speed_values):
        parser.error('all robot speed percentages must be between 1 and 50')
    if not 5.0 <= args.lift_mm <= 50.0 or not 5.0 <= args.retreat_mm <= 50.0:
        parser.error('--lift-mm and --retreat-mm must be between 5 and 50')
    if (
        args.grasp_z_offset_mm is not None
        and not -10.0 <= args.grasp_z_offset_mm <= 20.0
    ):
        parser.error('--grasp-z-offset-mm must be between -10 and 20')

    nominal = profile['nominal_size_mm']
    length_mm = (
        args.part_length_mm if args.part_length_mm is not None
        else float(nominal['length'])
    )
    width_mm = (
        args.part_width_mm if args.part_width_mm is not None
        else float(nominal['width'])
    )
    height_mm = (
        args.part_height_mm if args.part_height_mm is not None
        else float(nominal['height'])
    )
    if min(length_mm, width_mm, height_mm) <= 0.0:
        parser.error('part dimensions must be positive')

    shape = profile_value(args, 'part_shape', profile, 'shape')
    segmentation_mode = profile_value(
        args, 'segmentation_mode', profile
    )
    color_profile = profile_value(
        args, 'part_color', profile, 'color_profile'
    )
    orientation_mode = profile_value(args, 'orientation_mode', profile)
    height_tolerance_mm = profile_value(
        args, 'height_tolerance_mm', profile
    )
    depth_mask_height_fraction = profile_value(
        args, 'depth_mask_height_fraction', profile
    )
    gripper_axis = profile_value(args, 'gripper_axis', profile)
    gripper_open_position = (
        args.gripper_open_position
        if args.gripper_open_position is not None
        else profile.get('gripper_open_position')
    )
    gripper_close_position = (
        args.gripper_close_position
        if args.gripper_close_position is not None
        else profile.get('gripper_close_position')
    )
    if shape == 'circle' and orientation_mode != 'preserve':
        parser.error('circular profiles require --orientation-mode preserve')
    if not 0.05 <= depth_mask_height_fraction <= 0.9:
        parser.error('--depth-mask-height-fraction must be in [0.05, 0.9]')
    if height_tolerance_mm <= 0.0:
        parser.error('--height-tolerance-mm must be positive')
    if gripper_open_position is None or not 0 <= gripper_open_position <= 100:
        parser.error('a gripper open position in [0, 100] is required')
    if gripper_close_position is not None and not 0 <= gripper_close_position <= 100:
        parser.error('--gripper-close-position must be in [0, 100]')

    profile_detection_overridden = any((
        args.part_length_mm is not None,
        args.part_width_mm is not None,
        args.part_height_mm is not None,
        args.part_shape is not None,
        args.segmentation_mode is not None,
        args.part_color is not None,
        args.orientation_mode is not None,
        args.height_tolerance_mm is not None,
        args.depth_mask_height_fraction is not None,
        args.gripper_axis is not None,
    ))
    is_contact_execution = args.execute and not args.approach_only
    detection_is_validated = (
        profile.get('detection_validated') is True
        and not profile_detection_overridden
    )
    pick_is_validated = (
        profile.get('full_pick_validated') is True
        and detection_is_validated
        and not profile_detection_overridden
    )
    if args.execute and not args.allow_unvalidated_part_profile:
        if args.approach_only and not detection_is_validated:
            parser.error(
                f'{profile_id} detection has not been validated on the live '
                'D435; no robot motion was sent. First verify dry-run output, '
                'then explicitly pass --allow-unvalidated-part-profile for '
                'the supervised 5 cm validation move.'
            )
        if is_contact_execution and not pick_is_validated:
            parser.error(
                f'{profile_id} contact picking is implementation-only and '
                'not physically validated; first validate dimensions, jaw '
                'span/force, grasp Z, Hand-Eye, and clearance. The explicit '
                '--allow-unvalidated-part-profile override is required after '
                'those checks.'
            )
    if is_contact_execution and args.grasp_z_offset_mm is None:
        parser.error('contact picking requires a measured --grasp-z-offset-mm')
    if is_contact_execution and gripper_close_position is None:
        parser.error(
            'contact picking requires a measured --gripper-close-position '
            'for this part profile'
        )
    target_file = args.target_file or (
        CALIBRATION_ROOT / 'data' / f'{profile_id}_gripper_camera_last.json'
    )
    values = {
        'profile_id': profile_id,
        'length_mm': length_mm,
        'width_mm': width_mm,
        'height_mm': height_mm,
        'shape': shape,
        'segmentation_mode': segmentation_mode,
        'color_profile': color_profile,
        'orientation_mode': orientation_mode,
        'height_tolerance_mm': float(height_tolerance_mm),
        'depth_mask_height_fraction': float(depth_mask_height_fraction),
        'frames': args.frames,
        'depth_topic': args.depth_topic,
        'target_file': target_file,
        'debug_dir': CALIBRATION_ROOT / 'data' / f'{profile_id}_debug',
        'scan_all_black_cells': args.scan_all_black_cells,
        'gripper_axis': gripper_axis,
        'gripper_open_position': int(gripper_open_position),
        'gripper_close_position': (
            None if gripper_close_position is None
            else int(gripper_close_position)
        ),
    }

    print('MARKERLESS D435 MULTI-PART WORKFLOW')
    print(
        f'Part: {profile["display_name"]} ({profile_id}), '
        f'{length_mm:g} x {width_mm:g} x {height_mm:g} mm'
    )
    print(
        f'Detection: {segmentation_mode} + RGB-D geometry, '
        f'shape={shape}, orientation={orientation_mode}'
    )
    print(f'Dimension status: {profile.get("dimension_status", "unknown")}')
    if not pick_is_validated:
        print('Safety status: IMPLEMENTED, CONTACT PICK NOT PHYSICALLY VALIDATED')

    run(
        build_detection_command(values),
        f'DETECT {profile_id} ON /camera/camera',
        timeout=args.detection_timeout_sec,
    )
    run(
        build_pick_command(values, args),
        'CLOSED-LOOP 5 CM APPROACH'
        if args.approach_only else 'SAME-POSITION PICK CYCLE',
    )


if __name__ == '__main__':
    main()
