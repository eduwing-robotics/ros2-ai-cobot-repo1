#!/usr/bin/env python3
"""Guarded camera-pose move and post-arrival evidence for the cycle launcher."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import signal
import time
from types import SimpleNamespace

from assembly_cycle_launcher import BASELINE, ROOT, read, write
from full_cycle_motion import MotionWaypoint, normalize_controller_tcp
from tray_capture_retry import TrayCaptureRetry, RetryCaptureError


def finite_pose(pose):
    values = tuple(float(x) for x in pose)
    if len(values) != 6 or not all(math.isfinite(x) for x in values):
        raise RuntimeError('camera pose must contain six finite values')
    return values


def camera_route(start, target, point):
    """Use the September 5 camera transit branch and 350mm clearance.

    Translation and wrist change occur together at fixed safe Z. The last
    descent is split into <=50mm vertical segments and uses the slow speed.
    """
    start, target = normalize_controller_tcp(finite_pose(start)), normalize_controller_tcp(finite_pose(target))
    height = max(350.0, start[2], target[2])
    origin = (*start[:2], height, *start[3:])
    destination = (*target[:2], height, *target[3:])
    mapped = list(destination)
    for axis in (3, 4, 5):
        mapped[axis] = origin[axis] + (destination[axis] - origin[axis] + 180) % 360 - 180
    # Keep the wrapped shortest camera transit, including offsets beyond 1 degree.
    # Endpoint orientation and controller IK/joint checks remain mandatory.
    count = max(3, math.ceil(abs(mapped[5] - origin[5]) / 60))
    route = []
    if height > start[2] + 1e-6:
        route.append((point, MotionWaypoint('post_grasp_lift_50mm_vertical', origin, True)))
    for index in range(1, count):
        mid = tuple(origin[k] + (mapped[k] - origin[k]) * index / count for k in range(6))
        route.append((point, MotionWaypoint('place_combined_xy_abc_midpoint', normalize_controller_tcp(mid), False)))
    route.append((point, MotionWaypoint('place_combined_xy_abc', destination, False)))
    distance = height - target[2]
    for index in range(1, math.ceil(distance / 50) + 1):
        z = max(target[2], height - index * 50)
        pose = (*target[:2], z, *target[3:])
        route.append((point, MotionWaypoint('place_final_50mm_vertical', pose, True)))
    return route


def require_fresh_frame(payload, after, now):
    stamp = float(payload.get('timestamp_ros_ns', math.nan)) / 1e9
    if not math.isfinite(stamp) or not after < stamp <= now or now - stamp > 2:
        raise RuntimeError(f'waiting for fresh post-arrival frame (age={now-stamp:.3f}s, after_arrival={stamp-after:.3f}s)')
    return stamp


def next_frame_stamp(payload, last_stamp, after, now):
    # The producer may take >1s per result. A previously accepted result is
    # not a new bad observation when it ages while waiting for its successor.
    stamp = float(payload.get('timestamp_ros_ns', math.nan)) / 1e9
    if stamp == last_stamp:
        return None
    return require_fresh_frame(payload, after, now)


def stop_required_after_failure(motion_started, error, verify_stationary):
    if not motion_started:
        return False
    if not isinstance(error, RetryCaptureError):
        return True
    try:
        return not verify_stationary()
    except BaseException:
        return True


def capture_args(directory):
    vision = ROOT / 'vision_assembly'
    return SimpleNamespace(
        board_input=directory / 'board_measurement.json',
        tray_input=directory / 'tray_measurement.json',
        slot_file=vision / 'config/assembly_slots_r1.json',
        recipe_file=vision / 'config/part_gripper_recipes.json',
        max_source_age_sec=10.0, max_hole_fit_rms_mm=1.5, max_plane_mad_mm=2.0,
        only_part_type=None, only_instance_index=None,
    )


def board_window_valid(samples):
    import numpy as np
    centers = np.asarray([s['T_base_board'] for s in samples], float)[:, :3, 3] * 1000
    if not np.isfinite(centers).all():
        return False
    return float(np.max(np.linalg.norm(centers - np.median(centers, axis=0), axis=1))) <= 1.0


def run(args):
    import numpy as np
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import CameraInfo, CompressedImage
    from execute_full_fixed_cycle import (
        Executor, validate_start_state, preflight_route, move_preflighted, pose_error,
        init_executor_ros, record_fault_and_stop,
    )
    from fixed_cycle_snapshot import capture_board, capture_tray

    init_executor_ros()
    node = Executor()
    motion_started = False
    evidence = {'point': args.point, 'started_unix': time.time(), 'motion_sent': False}
    info = [None]
    image = [None]
    node.create_subscription(CameraInfo, '/camera/camera/color/camera_info',
                             lambda msg: info.__setitem__(0, msg), qos_profile_sensor_data)
    node.create_subscription(CompressedImage, '/camera/camera/color/image_raw/compressed',
                             lambda msg: image.__setitem__(0, msg), qos_profile_sensor_data)
    def fresh_start_state():
        sequence = node.state_sequence
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            if node.state_sequence > sequence:
                return validate_start_state(node)
        raise RuntimeError('fresh stationary robot state unavailable')

    try:
        if not node.client.wait_for_service(timeout_sec=8):
            raise RuntimeError('FR5 command service unavailable')
        state = fresh_start_state()
        node.assert_gripper_ready()
        baseline = read(BASELINE / 'runtime.json')
        tcp = node.response_values(node.service('GetTCPOffset(1)'), 6, 'active TCP offset')
        if not np.allclose(tcp, baseline['active_tcp_offset'], atol=0.1, rtol=0):
            raise RuntimeError('Tool1 TCP differs from successful baseline')
        points = {}
        for name in ('PlaceCamera', 'TrayHome'):
            values = node.response_values(node.service(f'GetRobotTeachingPoint({name})'), 14, name)
            if tuple(values[12:14]) != (1., 0.):
                raise RuntimeError(f'{name}: Tool1/User0 required')
            points[name] = finite_pose(values[:6])
            p, a = pose_error(list(points[name]), baseline['teaching_points'][name][:6])
            if p > 1 or a > 1:
                raise RuntimeError(f'{name}: teaching point changed from successful baseline')
        points['SMDView'] = finite_pose(read(ROOT / 'vision_assembly/config/smd_section_view.json')['reference_tcp_base'])
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            if info[0] is not None and image[0] is not None:
                stamp = image[0].header.stamp.sec + image[0].header.stamp.nanosec / 1e9
                if 0 <= time.time() - stamp < 2:
                    break
        else:
            raise RuntimeError('fresh D435 camera stream unavailable')
        camera = baseline['camera']
        if ([info[0].width, info[0].height] != [camera['width'], camera['height']]
                or not np.allclose(info[0].k, camera['k'], atol=1.0, rtol=0)):
            raise RuntimeError('D435 resolution/intrinsics differ from 1280x720 success baseline')
        evidence.update(active_tcp_offset=tcp.tolist(), teaching_points=points)
        if args.point == 'check':
            print(json.dumps(evidence, indent=2))
            print('Robot/Tool1/teaching points/D435 ready; no motion or gripper commands.')
            return

        directory = args.directory
        if not directory.is_dir():
            raise RuntimeError('existing run directory required')
        target = points[args.point]
        state = fresh_start_state()
        start = node.snapshot()
        evidence['target'] = list(target)
        if args.capture_only:
            p, a = pose_error(start, list(target))
            if p > 1 or a > 1:
                raise RuntimeError('capture-only requires the requested camera pose already reached')
            evidence['mode'] = 'capture_only_no_motion'
        else:
            planned, summary = preflight_route(node, camera_route(start, target, args.point),
                node.state_joints(state), dict(travel=25, combined_rotation=25, vertical=10))
            evidence['preflight'] = summary
            if not args.execute:
                print(json.dumps(evidence, indent=2), flush=True)
                return
            # Camera transit used global20 in the successful camera-stage script.
            motion_started = True
            evidence['motion_sent'] = True
            api_job = os.environ.get('FR5_STEP_API_JOB_ID')
            if api_job:
                from step_api_transport import StepApiSession
                session = StepApiSession(node,api_job,directory/(args.point+'_api'))
                session.ready()
                evidence['execution_backend']='single_step_api'
                evidence['api_result']=session.call(session.client.moveJoint,args.point,list(planned[-1].target_joints))
            else:
                node.service('SetSpeed(20)')
                for waypoint in planned:
                    move_preflighted(node, waypoint)
        print(json.dumps(evidence, indent=2), flush=True)
        arrived = time.time()
        after = arrived + 2.0
        evidence['arrived_unix'] = arrived
        phase = {'PlaceCamera': 'board', 'TrayHome': 'tray', 'SMDView': 'smd_view'}[args.point]
        source = ROOT / 'vision_assembly/data' / ('board_pose_3d_live.json' if phase == 'board' else 'tray_detections_last.json')
        deadline = time.monotonic() + (62 if phase == 'tray' else 60)
        samples, last_stamp, last_reason = [], None, 'no fresh observations'
        last_diagnostic = 0.0
        frozen = None
        parameters = capture_args(directory)
        parameters.part_group = getattr(args, "part_group", None)
        parameters.defer_smd_to_close_view = getattr(args, "defer_smd_to_close_view", False)
        photo_only = getattr(args, 'photo_only', False)
        evidence['capture_scope'] = 'photograph_only' if photo_only else 'measurement'
        prior = read(directory / 'snapshot.json') if phase == 'tray' and not photo_only else None
        retry = (TrayCaptureRetry(read(parameters.recipe_file)['tray_snapshot_quality'], after, defer_smd_to_close_view=parameters.defer_smd_to_close_view)
                 if phase == 'tray' and not photo_only and parameters.part_group is None else None)
        retry_progress = None
        while time.monotonic() < deadline:
            if retry is not None:
                retry.tick(time.time())
            state = fresh_start_state()
            p, a = pose_error(node.snapshot(), list(target))
            if p > 1 or a > 1:
                raise RuntimeError('camera pose drift during capture')
            now = time.time()
            msg = image[0]
            image_stamp = msg.header.stamp.sec + msg.header.stamp.nanosec / 1e9
            if not after < image_stamp <= now or now - image_stamp > 2:
                continue
            if phase == 'smd_view' or photo_only:
                break
            try:
                payload = read(source)
                stamp = next_frame_stamp(payload, last_stamp, after, now)
                if stamp is None:
                    continue
                last_stamp = stamp
                if retry is not None:
                    merged = retry.observe(payload, now)
                    report = retry.report()
                    write(directory / 'tray_retries.json', report)
                    evidence['tray_retries'] = report
                    progress = (report['attempt'], report['accepted_count'])
                    if progress != retry_progress or time.monotonic() - last_diagnostic >= 5:
                        print(f'TRAY CAPTURE {report["attempt"]}/{report["maximum_attempts"]}: '
                              f'{report["accepted_count"]}/25 accepted; pending={report["pending"]}', flush=True)
                        retry_progress = progress
                        last_diagnostic = time.monotonic()
                    if merged is None:
                        continue
                    write(directory / 'tray_current_observation.json', payload)
                    write(parameters.tray_input, merged)
                    frozen = capture_tray(parameters, dict(prior))
                    frozen['tray_capture'].update(
                        captured_unix=merged['oldest_part_capture_unix'],
                        source_age_sec=round(now-merged['oldest_part_capture_unix'],3),
                        per_part_capture_sources=merged['per_part_capture_sources'],
                        capture_mode=merged['capture_mode'],
                    )
                    break
                if phase == 'tray':
                    write(parameters.tray_input, payload)
                    frozen = capture_tray(parameters, dict(prior))
                    frozen['tray_capture']['captured_unix'] = stamp
                else:
                    write(parameters.board_input, payload)
                    frozen = capture_board(parameters)
                samples.append(payload)
                samples = samples[-4:]
                if len(samples) < 4:
                    continue
                if phase == 'board' and not board_window_valid(samples):
                    raise RuntimeError('board center jitter exceeds 1mm')
                if phase == 'tray':
                    # Retain the coarse reference pixels used for post-pick checks.
                    if any(p.get('reference_center_pixel') is None for p in frozen['tray_capture']['parts']):
                        raise RuntimeError('tray cell reference pixels unavailable')
                break
            except RetryCaptureError:
                raise
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                if retry is not None:
                    retry.streak = {k: v for k, v in retry.streak.items() if k in retry.accepted}
                last_reason = str(exc)
                samples.clear()
                evidence['last_capture_rejection'] = last_reason
                if time.monotonic() - last_diagnostic >= 5:
                    print(f'WAITING {phase}: {last_reason}', flush=True)
                    last_diagnostic = time.monotonic()
        else:
            if retry is not None:
                retry.tick(time.time())
            raise RuntimeError(f'{phase}: capture timeout: {last_reason}')
        (directory / f'{phase}.jpg').write_bytes(bytes(image[0].data))
        if frozen is not None:
            frozen[f'{phase}_capture']['image_timestamp_ros_ns'] = int(last_stamp * 1e9)
            frozen[f'{phase}_capture']['arrived_unix'] = arrived
            # capture_board creates a new cycle; subsequent phases preserve it.
            write(directory / 'snapshot.json', frozen)
            write(directory / f'{phase}_snapshot.json', frozen)
        evidence.update(status='captured', photograph_timestamp_unix=image_stamp,
                        finished_unix=time.time(), distinct_valid_frames=(len(samples) if retry is None else None))
        print(f'ARRIVED AND CAPTURED {args.point}', flush=True)
    except BaseException as exc:
        evidence.update(status='stopped_on_error', error=f'{type(exc).__name__}: {exc}')
        def verify_stationary_camera():
            fresh_start_state()
            position_error, angle_error = pose_error(node.snapshot(), list(target))
            return position_error <= 1 and angle_error <= 1
        # A vision rejection at a freshly verified stationary pose needs no
        # StopMotion (which latches abnormal_stop on this FR5).
        stop_required = stop_required_after_failure(motion_started, exc, verify_stationary_camera)
        if motion_started and not stop_required:
            evidence['stationary_capture_rejection'] = True
        if stop_required and os.environ.get('FR5_STEP_API_JOB_ID'):
            evidence['stop_owned_by_step_api']=True
        elif stop_required:
            record_fault_and_stop(node, evidence,
                                  args.directory / f'{args.point}_camera_stage.json', exc)
            stop = evidence['stop_motion_on_error']
            if 'response' in stop:
                evidence['stop_motion_response'] = stop['response']
            if 'error' in stop:
                evidence['stop_motion_error'] = stop['error']
        raise
    finally:
        if args.directory and args.directory.is_dir():
            write(args.directory / f'{args.point}_camera_stage.json', evidence)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('point', choices=['check', 'PlaceCamera', 'TrayHome', 'SMDView'])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--execute', action='store_true')
    mode.add_argument('--capture-only', action='store_true', help='capture at current verified camera pose without any motion')
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--photo-only', action='store_true', help='save a fresh photograph only; do not create measurement snapshots or authorize assembly')
    parser.add_argument('--defer-smd-to-close-view', action='store_true', help='TrayHome SMD presence only; SMDView validation required before any CAP pick')
    parser.add_argument('--part-group', choices=['gpu','hbm','long_orange','black_block','marked_white','right_white_brown'])
    args = parser.parse_args()
    if args.part_group and args.point != 'TrayHome':
        parser.error('--part-group is only valid for TrayHome')
    if args.point != 'check' and args.directory is None:
        parser.error('--directory required')
    if args.point == 'check' and (args.execute or args.capture_only):
        parser.error('check cannot execute motion')
    run(args)


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    main()
