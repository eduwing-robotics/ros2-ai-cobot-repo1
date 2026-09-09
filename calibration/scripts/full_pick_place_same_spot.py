#!/usr/bin/env python3
"""Run the markerless profile-sized pick/place-at-same-spot workflow."""

import argparse
import subprocess
import json
import time
from pathlib import Path
from target_numeric_guard import finite_number, validate_cli_floats, validate_target_numbers


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'data/small_part_last.json'
PART_PROFILE_CONFIG = ROOT / 'config/gripper_part_profiles.json'


def run(command, label, timeout=None):
    print(f'\n=== {label} ===', flush=True)
    print(' '.join(str(value) for value in command), flush=True)
    try:
        completed = subprocess.run(command, check=False, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f'{label} timed out after {timeout:.1f} s') from exc
    if completed.returncode != 0:
        raise RuntimeError(f'{label} failed with exit code {completed.returncode}')


def validate_target_file(
    path, max_age_sec, expected_part_profile_id=None,
    expected_orientation_mode=None, expected_part_size_mm=None,
    expected_part_shape=None, expected_segmentation_mode=None,
):
    payload = json.loads(path.read_text(encoding='utf-8'))
    try:
        validate_target_numbers(payload)
        if finite_number(max_age_sec, 'max_age_sec') <= 0:
            raise ValueError('max_age_sec must be positive')
    except ValueError as exc:
        raise RuntimeError(f'target numeric metadata rejected: {exc}') from exc
    age = time.time() - float(payload['timestamp_unix'])
    if age < -5.0 or age > max_age_sec:
        raise RuntimeError(f'target file is stale (age={age:.1f} s); run detection again')
    if 'part_center_base_mm' not in payload:
        raise RuntimeError(f'{path} has no part_center_base_mm')
    quality = payload.get('depth_quality')
    if not isinstance(quality, dict) or quality.get('accepted') is not True:
        raise RuntimeError(f'{path} has no accepted depth_quality; detect again')
    if (
        expected_part_profile_id is not None
        and payload.get('part_profile_id') != expected_part_profile_id
    ):
        raise RuntimeError(
            f'{path} was detected as profile '
            f'{payload.get("part_profile_id")!r}, expected '
            f'{expected_part_profile_id!r}'
        )
    if (
        expected_orientation_mode is not None
        and payload.get('orientation_mode', 'long_axis')
        != expected_orientation_mode
    ):
        raise RuntimeError(
            f'{path} orientation mode differs from the requested workflow'
        )
    if expected_part_size_mm is not None:
        try:
            actual_size = [float(value) for value in payload['part_size_input_mm']]
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f'{path} has no valid configured part size') from exc
        if len(actual_size) != 3 or any(
            abs(actual - expected) > 1e-6
            for actual, expected in zip(actual_size, expected_part_size_mm)
        ):
            raise RuntimeError(
                f'{path} configured part size differs from the requested workflow'
            )
    if (
        expected_part_shape is not None
        and payload.get('part_shape', 'rectangle') != expected_part_shape
    ):
        raise RuntimeError(f'{path} part shape differs from the requested workflow')
    if (
        expected_segmentation_mode is not None
        and payload.get('segmentation_mode', 'bright')
        != expected_segmentation_mode
    ):
        raise RuntimeError(
            f'{path} segmentation mode differs from the requested workflow'
        )
    return payload


def validate_current_target(args):
    return validate_target_file(
        args.target_file,
        args.max_target_age_sec,
        args.part_profile_id,
        args.orientation_mode,
        [args.part_length_mm, args.part_width_mm, args.part_height_mm],
        args.part_shape,
        args.segmentation_mode,
    )


def profile_motion_validation(args, parser):
    """Apply the profile gate even when this low-level script is called directly."""
    if args.part_profile_id == 'custom':
        return
    try:
        catalog = json.loads(
            PART_PROFILE_CONFIG.read_text(encoding='utf-8')
        )['profiles']
        profile = catalog[args.part_profile_id]
        nominal = profile['nominal_size_mm']
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.error(
            f'cannot validate part profile {args.part_profile_id!r}: {exc}'
        )
    expected = [
        float(nominal['length']),
        float(nominal['width']),
        float(nominal['height']),
    ]
    actual = [
        args.part_length_mm, args.part_width_mm, args.part_height_mm,
    ]
    contract_matches = (
        all(abs(left - right) <= 1e-6 for left, right in zip(actual, expected))
        and args.part_shape == profile['shape']
        and args.segmentation_mode == profile['segmentation_mode']
        and args.part_color == profile['color_profile']
        and args.orientation_mode == profile['orientation_mode']
        and abs(
            args.height_tolerance_mm - float(profile['height_tolerance_mm'])
        ) <= 1e-6
        and abs(
            args.depth_mask_height_fraction
            - float(profile['depth_mask_height_fraction'])
        ) <= 1e-6
        and args.gripper_axis == profile['gripper_axis']
    )
    detection_validated = (
        profile.get('detection_validated') is True
        and contract_matches
    )
    full_pick_validated = (
        profile.get('full_pick_validated') is True
        and detection_validated
    )
    required_validated = (
        detection_validated if args.approach_only else full_pick_validated
    )
    if (
        args.execute
        and not required_validated
        and not args.allow_unvalidated_part_profile
    ):
        parser.error(
            f'{args.part_profile_id} profile motion is not physically '
            'validated; --allow-unvalidated-part-profile is required'
        )


def make_detection_command(args, frames, track_existing=False):
    command = [
        str(ROOT / 'run_small_part_detection.sh'),
        '--part-length-mm', str(args.part_length_mm),
        '--part-width-mm', str(args.part_width_mm),
        '--part-height-mm', str(args.part_height_mm),
        '--part-profile-id', args.part_profile_id,
        '--part-shape', args.part_shape,
        '--orientation-mode', args.orientation_mode,
        '--segmentation-mode', args.segmentation_mode,
        '--part-color', args.part_color,
        '--height-tolerance-mm', str(args.height_tolerance_mm),
        '--depth-mask-height-fraction', str(args.depth_mask_height_fraction),
        '--frames', str(frames),
        '--output-file', str(args.target_file),
        '--depth-topic', args.depth_topic,
    ]
    if args.scan_all_black_cells:
        command.append('--scan-all-black-cells')
    else:
        command.append('--no-scan-all-black-cells')
    if track_existing:
        command.extend(['--track-base-target-file', str(args.target_file)])
    return command


def gripper_open(position):
    run([
        str(ROOT / 'run_set_gripper_position.sh'),
        '--position', str(position),
        '--expected-motion-state', '1',
        '--execute', '--confirm-gripper',
    ], 'OPEN AND VERIFY GRIPPER BEFORE DESCENT')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--part-length-mm', type=float, default=6.0)
    parser.add_argument('--part-width-mm', type=float, default=3.5)
    parser.add_argument('--part-height-mm', type=float, default=2.5)
    parser.add_argument('--part-profile-id', default='custom')
    parser.add_argument('--part-shape', choices=('rectangle', 'circle'), default='rectangle')
    parser.add_argument(
        '--orientation-mode', choices=('long_axis', 'preserve'),
        default='long_axis',
    )
    parser.add_argument(
        '--segmentation-mode', choices=('bright', 'dark', 'depth'),
        default='bright',
    )
    parser.add_argument('--part-color', choices=('light', 'orange', 'brown', 'any'), default='light')
    parser.add_argument('--height-tolerance-mm', type=float, default=2.0)
    parser.add_argument('--depth-mask-height-fraction', type=float, default=0.35)
    parser.add_argument('--frames', type=int, default=30)
    parser.add_argument('--refine-frames', type=int, default=15)
    parser.add_argument('--scan-all-black-cells', action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument('--depth-topic', default='/camera/camera/aligned_depth_to_color/image_raw')
    parser.add_argument('--target-file', type=Path, default=TARGET)
    parser.add_argument('--skip-detection', action='store_true')
    parser.add_argument('--max-target-age-sec', type=float, default=120.0)
    parser.add_argument('--detection-timeout-sec', type=float, default=15.0)
    parser.add_argument('--approach-offset-mm', type=float, default=50.0)
    parser.add_argument('--grasp-z-offset-mm', type=float, default=None,
                        help='calibrated final TCP Z relative to detected component top')
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
                        help='align over the part and stop 50 mm above it')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-full-cycle', action='store_true')
    parser.add_argument('--confirm-approach-only', action='store_true')
    parser.add_argument('--allow-provisional-calibration', action='store_true')
    parser.add_argument('--allow-unvalidated-part-profile', action='store_true')
    args = parser.parse_args()
    validate_cli_floats(args, parser)

    if args.approach_only:
        if args.execute != args.confirm_approach_only:
            parser.error('실제 5 cm 접근에는 --execute와 --confirm-approach-only가 모두 필요합니다')
        if args.confirm_full_cycle:
            parser.error('--approach-only cannot be combined with --confirm-full-cycle')
        args.approach_offset_mm = 50.0
    elif args.execute != args.confirm_full_cycle:
        parser.error('실제 전체 동작에는 --execute와 --confirm-full-cycle이 모두 필요합니다')
    elif args.confirm_approach_only:
        parser.error('--confirm-approach-only requires --approach-only')
    if args.dry_run and args.execute:
        parser.error('--dry-run and --execute cannot be combined')
    if args.extra_descent_mm is not None:
        if args.grasp_z_offset_mm is not None:
            parser.error('use only --grasp-z-offset-mm')
        args.grasp_z_offset_mm = -args.extra_descent_mm
    if args.grasp_z_offset_mm is not None and not -10.0 <= args.grasp_z_offset_mm <= 20.0:
        parser.error('--grasp-z-offset-mm must be between -10 and 20')
    if args.execute and not args.approach_only and args.grasp_z_offset_mm is None:
        parser.error('full pick requires a physically calibrated --grasp-z-offset-mm')
    if not 50.0 <= args.approach_offset_mm <= 130.0:
        parser.error('--approach-offset-mm must be between 50 and 130')
    if args.frames <= 0 or args.refine_frames <= 0:
        parser.error('frame counts must be positive')
    if min(args.part_length_mm, args.part_width_mm, args.part_height_mm) <= 0.0:
        parser.error('part dimensions must be positive')
    if args.part_shape == 'circle' and args.orientation_mode != 'preserve':
        parser.error('circular parts require --orientation-mode preserve')
    if args.height_tolerance_mm <= 0.0:
        parser.error('--height-tolerance-mm must be positive')
    if not 0.05 <= args.depth_mask_height_fraction <= 0.9:
        parser.error('--depth-mask-height-fraction must be in [0.05, 0.9]')
    if not 1 <= args.grasp_descent_speed_percent <= 50:
        parser.error('--grasp-descent-speed-percent must be between 1 and 50')
    if any(not 1 <= value <= 50 for value in (
        args.xy_speed_percent,
        args.vertical_speed_percent,
        args.rotation_speed_percent,
        args.cycle_speed_percent,
    )):
        parser.error('all motion speed percentages must be between 1 and 50')
    if not 5.0 <= args.lift_mm <= 50.0 or not 5.0 <= args.retreat_mm <= 50.0:
        parser.error('--lift-mm and --retreat-mm must be between 5 and 50')
    if not 0 <= args.gripper_open_position <= 100:
        parser.error('--gripper-open-position must be in [0, 100]')
    if not 0 <= args.gripper_close_position <= 100:
        parser.error('--gripper-close-position must be in [0, 100]')
    if args.detection_timeout_sec <= 0.0 or args.max_target_age_sec <= 0.0:
        parser.error('detection timeout and target age must be positive')
    profile_motion_validation(args, parser)

    print('PART 5 CM NON-CONTACT APPROACH' if args.approach_only else 'FULL PART PICK/PLACE-AT-SAME-SPOT WORKFLOW')
    print('1 detect, 2 orient gripper, 3 stop 50 mm above; no gripper command' if args.approach_only else
          '1 detect, 2 open, 3 approach, 4 depth-target descent, 5 grasp/lift/place/retreat')
    print(
        f'Profile={args.part_profile_id}, shape={args.part_shape}, '
        f'segmentation={args.segmentation_mode}, '
        f'orientation={args.orientation_mode}'
    )
    print('No horizontal transfer to a different placement target is included.')

    if args.skip_detection:
        validate_current_target(args)
        print(f'USING EXISTING TARGET FILE: {args.target_file}')
    else:
        run(
            make_detection_command(args, args.frames),
            '1/8 DETECT CURRENT PART', timeout=args.detection_timeout_sec,
        )

    initial_payload = validate_current_target(args)
    initial_warning = str(initial_payload.get('handeye', {}).get('warning', '')).strip()
    if (
        args.execute and not args.approach_only and initial_warning
        and not args.allow_provisional_calibration
    ):
        raise RuntimeError(
            'active Hand-Eye calibration is marked provisional; no full-cycle motion was sent. '
            'Validate it physically or explicitly pass --allow-provisional-calibration.'
        )

    approach = [
        str(ROOT / 'run_object_approach.sh'),
        '--target-file', str(args.target_file),
        '--approach-offset-mm', str(args.approach_offset_mm),
        '--speed-percent', str(args.xy_speed_percent),
        '--descent-speed-percent', str(args.vertical_speed_percent),
        '--rotation-speed-percent', str(args.rotation_speed_percent),
        '--no-center-correction',
    ]
    if args.orientation_mode == 'long_axis':
        approach.extend(['--align-part', '--gripper-axis', args.gripper_axis])

    if not args.execute:
        run(approach + ['--dry-run'], '2/5 APPROACH DRY RUN')
        print('\nDRY RUN STOP: subsequent descent depends on the robot reaching the approach pose.')
        print('ROBOT AND GRIPPER DID NOT MOVE.')
        return

    run(approach + ['--execute', '--confirm-move'], '2/10 INITIAL MOVE TO 50 MM HOVER')
    for refinement_index in range(2):
        run(
            make_detection_command(args, args.refine_frames, track_existing=True),
            f'{3 + refinement_index * 2}/10 TRACKED RGB-D DETECTION, PASS {refinement_index + 1}',
            timeout=args.detection_timeout_sec,
        )
        refine = approach + [
            '--refine-hover',
            '--max-refine-xy-mm', '15' if refinement_index == 0 else '5',
            '--max-refine-z-mm', '15' if refinement_index == 0 else '5',
            '--max-refine-rotation-deg', '20' if refinement_index == 0 else '8',
            '--execute', '--confirm-move',
        ]
        run(refine, f'{4 + refinement_index * 2}/10 BOUNDED HOVER REFINEMENT, PASS {refinement_index + 1}')
    run(
        make_detection_command(args, args.refine_frames, track_existing=True),
        '7/10 FINAL TRACKED RGB-D VERIFICATION DETECTION',
        timeout=args.detection_timeout_sec,
    )
    verify = approach + [
        '--verify-only',
        '--arrival-position-tolerance-mm', '1.0',
        '--arrival-angle-tolerance-deg', '1.0',
    ]
    run(verify, '8/10 VERIFY FINAL 50 MM HOVER')

    if args.approach_only:
        print('\nAPPROACH-ONLY COMPLETED: verified at 50 mm hover; no gripper, grasp descent, lift, place, or return command was sent.')
        return

    final_payload = validate_current_target(args)
    warning = str(final_payload.get('handeye', {}).get('warning', '')).strip()
    if warning and not args.allow_provisional_calibration:
        raise RuntimeError(
            'active Hand-Eye calibration is marked provisional; full pick is blocked. '
            'Validate it physically or explicitly pass --allow-provisional-calibration.'
        )
    gripper_open(args.gripper_open_position)

    descent_base = [
        str(ROOT / 'run_vertical_test.sh'),
        '--target-file', str(args.target_file),
        '--speed-percent', str(args.grasp_descent_speed_percent),
        '--target-z-offset-mm', str(args.grasp_z_offset_mm),
        '--max-descent-mm', str(args.approach_offset_mm + 10.0),
        '--max-target-xy-error-mm', '1.0',
        '--execute', '--confirm-descent',
    ]
    run(descent_base, '9/10 DEPTH-TARGET DESCENT TO CALIBRATED GRASP HEIGHT')

    run([
        str(ROOT / 'run_grasp_place_cycle.sh'),
        '--target-file', str(args.target_file),
        '--lift-mm', str(args.lift_mm),
        '--retreat-mm', str(args.retreat_mm),
        '--motion-speed-percent', str(args.cycle_speed_percent),
        '--close-position', str(args.gripper_close_position),
        '--open-position', str(args.gripper_open_position),
        '--max-target-xy-error-mm', '1.0',
        '--max-target-z-error-mm', '1.0',
        '--max-axis-error-deg', '1.5',
        '--grasp-z-offset-mm', str(args.grasp_z_offset_mm),
        '--orientation-mode', args.orientation_mode,
        '--gripper-axis', args.gripper_axis,
        '--execute', '--confirm-gripper', '--confirm-cycle',
    ], '10/10 GRASP, LIFT, PLACE, RETREAT')
    if not args.no_return:
        run([
            str(ROOT / 'run_return_to_teaching_point.sh'),
            '--point-name', args.return_point,
            '--speed-percent', str(args.xy_speed_percent),
            '--vertical-speed-percent', str(args.vertical_speed_percent),
            '--safe-clearance-mm', str(args.return_safe_clearance_mm),
            '--execute', '--confirm-return',
        ], f'6/6 RETURN TO {args.return_point}')
    else:
        print('\n=== 6/6 RETURN SKIPPED ===')
    print('\nFULL SAME-SPOT PICK/PLACE TEST COMPLETED')


if __name__ == '__main__':
    main()
