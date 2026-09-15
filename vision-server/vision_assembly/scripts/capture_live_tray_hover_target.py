#!/usr/bin/env python3
"""Freeze one fresh non-SMD target from the running RGB-D tray detector."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from tray_hover_contract import (
    TrayHoverContractError,
    load_contract,
    normalize_part_type,
    summarize_samples,
    validate_registration,
    validate_unity_target,
)


class LiveTargetCollector(Node):
    def __init__(self, args, contract, part_type):
        super().__init__('capture_live_tray_hover_target')
        self.args = args
        self.contract = contract
        self.part_type = part_type
        self.registration = None
        self.samples = []
        self.last_sequence = None
        self.first_sequence = None
        self.started = time.monotonic()
        self.last_status_print = 0.0
        self.last_rejection = 'waiting for live tray topics'
        self.completed_payload = None
        self.create_subscription(String, args.registration_topic, self.registration_cb, 10)
        self.create_subscription(String, args.state_topic, self.state_cb, 10)
        self.create_timer(0.1, self.timeout_cb)

    @staticmethod
    def decode(message):
        try:
            payload = json.loads(message.data)
        except (TypeError, json.JSONDecodeError) as exc:
            raise TrayHoverContractError(f'Invalid JSON topic payload: {exc}') from exc
        if not isinstance(payload, dict):
            raise TrayHoverContractError('Topic payload must be a JSON object')
        return payload

    def report_wait(self, reason):
        self.last_rejection = str(reason)
        now = time.monotonic()
        if now - self.last_status_print >= 2.0:
            print(f'WAITING: {self.last_rejection}', flush=True)
            self.last_status_print = now

    def reset_samples(self, reason):
        if self.samples:
            print(f'RESTARTING STABILITY WINDOW: {reason}', flush=True)
        self.samples.clear()
        self.first_sequence = None
        self.report_wait(reason)

    def registration_cb(self, message):
        try:
            self.registration = self.decode(message)
            validate_registration(self.registration, self.contract)
        except TrayHoverContractError as exc:
            self.registration = None
            self.reset_samples(exc)

    def state_cb(self, message):
        try:
            if self.registration is None:
                raise TrayHoverContractError('No fresh tray-home registration state')
            registration_status = validate_registration(self.registration, self.contract)
            payload = self.decode(message)
            sample = validate_unity_target(
                payload,
                self.part_type,
                self.args.instance,
                self.contract,
            )
        except (TrayHoverContractError, TypeError, ValueError) as exc:
            self.reset_samples(exc)
            return

        sequence = sample['sequence']
        if sequence == self.last_sequence:
            return
        if self.last_sequence is not None and sequence < self.last_sequence:
            self.reset_samples('tray detector sequence restarted')
        self.last_sequence = sequence
        if self.first_sequence is None:
            self.first_sequence = sequence
        self.samples.append(sample)
        if len(self.samples) > self.args.frames:
            self.samples = self.samples[-self.args.frames:]
        try:
            summary = summarize_samples(self.samples, self.contract)
        except TrayHoverContractError as exc:
            latest = self.samples[-1]
            self.samples = [latest]
            self.first_sequence = latest['sequence']
            self.report_wait(exc)
            return

        print(
            f'STABLE RGB-D TARGET: {len(self.samples)}/{self.args.frames}; '
            f'position jitter={summary["max_position_jitter_mm"]:.3f} mm; '
            f'axis jitter={summary["max_axis_angle_jitter_deg"]:.3f} deg',
            flush=True,
        )
        if len(self.samples) < self.args.frames:
            return
        self.completed_payload = self.build_output(summary, registration_status)
        self.save_output(self.completed_payload)
        rclpy.shutdown()

    def build_output(self, summary, registration_status):
        latest = self.samples[-1]
        profile = self.contract['parts'][self.part_type]
        camera_points = [
            sample.get('camera_xyz_m') for sample in self.samples
            if sample.get('camera_xyz_m') is not None
        ]
        camera_center = None
        if camera_points:
            points = np.asarray(camera_points, dtype=float)
            if points.shape == (len(camera_points), 3) and np.all(np.isfinite(points)):
                camera_center = np.median(points, axis=0).round(6).tolist()
        return {
            'schema_version': 2,
            'mode': 'frozen_tray_part_target',
            'workflow': 'non_smd_tray_hover_only',
            'timestamp_unix': time.time(),
            'part_type': self.part_type,
            'instance_index': self.args.instance,
            'display_name': latest['display_name'],
            'part_center_base_mm': np.round(summary['center_base_mm'], 3).tolist(),
            'part_center_camera_m': camera_center,
            'long_axis_angle_base_deg': (
                None if summary['axis_angle_base_deg'] is None
                else round(float(summary['axis_angle_base_deg']), 3)
            ),
            'orientation_mode': profile['orientation_mode'],
            'gripper_axis': profile['gripper_axis'],
            'hover_offset_mm': 50.0,
            'sample_count': len(self.samples),
            'max_jitter_mm': round(float(summary['max_position_jitter_mm']), 4),
            'max_axis_angle_jitter_deg': round(
                float(summary['max_axis_angle_jitter_deg']), 4
            ),
            'detector_sequence_first': int(self.first_sequence),
            'detector_sequence_last': int(latest['sequence']),
            'source_state_timestamp_ros_ns': int(latest['timestamp_ros_ns']),
            'registration_timestamp_ros_ns': int(
                registration_status['timestamp_ros_ns']
            ),
            'registration_state': registration_status['state'],
            'tray_at_home': True,
            'base_transform_status': 'VALID_COORDINATES_ONLY',
            'coordinate_frame': 'base_link',
            'position_units': 'mm',
            'live_part_count': int(latest['live_count']),
            'minimum_observation_frames': min(
                int(sample['observation_frames']) for sample in self.samples
            ),
            'source_state_topic': self.args.state_topic,
            'source_registration_topic': self.args.registration_topic,
            'depth_basis': (
                'running tray detector aligned D435 depth -> camera XYZ -> '
                'Hand-Eye -> base_link'
            ),
            'contract_file': str(self.args.config),
            'contract_sha256': hashlib.sha256(self.args.config.read_bytes()).hexdigest(),
            'robot_motion_authorized': False,
            'contact_pick_authorized': False,
        }

    def save_output(self, payload):
        self.args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.args.output.with_suffix(self.args.output.suffix + '.tmp')
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        temporary.replace(self.args.output)
        print('Frozen Base surface [mm]:', payload['part_center_base_mm'])
        print('Saved:', self.args.output)

    def timeout_cb(self):
        if time.monotonic() - self.started <= self.args.timeout_sec:
            return
        self.last_rejection = (
            f'timed out after {self.args.timeout_sec:.1f} s; last reason: '
            f'{self.last_rejection}'
        )
        rclpy.shutdown()


def parse_args(argv=None):
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=root / 'config/tray_hover_5cm.json')
    parser.add_argument('--part-type', required=True)
    parser.add_argument('--instance', type=int, default=1)
    parser.add_argument('--frames', type=int)
    parser.add_argument('--max-jitter-mm', type=float)
    parser.add_argument('--max-angle-jitter-deg', type=float)
    parser.add_argument('--timeout-sec', type=float)
    parser.add_argument('--max-state-age-sec', type=float)
    parser.add_argument('--state-topic')
    parser.add_argument('--registration-topic')
    parser.add_argument(
        '--output',
        type=Path,
        default=root / 'data/tray_hover_target_last.json',
    )
    args = parser.parse_args(argv)
    try:
        contract = load_contract(args.config)
        part_type = normalize_part_type(args.part_type, contract)
    except TrayHoverContractError as exc:
        parser.error(str(exc))
    capture = contract['capture']
    maximum_position_jitter = float(capture['max_position_jitter_mm'])
    maximum_angle_jitter = float(capture['max_axis_angle_jitter_deg'])
    maximum_state_age = float(contract['required_state']['maximum_state_age_sec'])
    topics = contract['source_topics']
    args.frames = int(args.frames if args.frames is not None else capture['frames'])
    args.max_jitter_mm = float(
        args.max_jitter_mm
        if args.max_jitter_mm is not None
        else capture['max_position_jitter_mm']
    )
    args.max_angle_jitter_deg = float(
        args.max_angle_jitter_deg
        if args.max_angle_jitter_deg is not None
        else capture['max_axis_angle_jitter_deg']
    )
    args.timeout_sec = float(
        args.timeout_sec if args.timeout_sec is not None else capture['timeout_sec']
    )
    if args.max_state_age_sec is not None:
        if not 0 < args.max_state_age_sec <= maximum_state_age:
            parser.error(
                f'--max-state-age-sec must be in (0, {maximum_state_age:g}]'
            )
        contract['required_state']['maximum_state_age_sec'] = float(
            args.max_state_age_sec
        )
    contract['capture']['max_position_jitter_mm'] = args.max_jitter_mm
    contract['capture']['max_axis_angle_jitter_deg'] = args.max_angle_jitter_deg
    args.state_topic = args.state_topic or topics['unity_state']
    args.registration_topic = args.registration_topic or topics['registration']
    if args.instance < 1:
        parser.error('--instance must be at least 1')
    if not 5 <= args.frames <= 15:
        parser.error('--frames must be in [5, 15]')
    if not 0 < args.max_jitter_mm <= maximum_position_jitter:
        parser.error(
            f'--max-jitter-mm must be in (0, {maximum_position_jitter:g}]'
        )
    if not 0 < args.max_angle_jitter_deg <= maximum_angle_jitter:
        parser.error(
            '--max-angle-jitter-deg must be in '
            f'(0, {maximum_angle_jitter:g}]'
        )
    if not 0 < args.timeout_sec <= 60.0:
        parser.error('--timeout-sec must be in (0, 60]')
    return args, contract, part_type


def main(argv=None):
    args, contract, part_type = parse_args(argv)
    print(
        f'LIVE RGB-D TRAY TARGET: {part_type} #{args.instance}; '
        f'{args.frames} fresh samples; no robot/gripper command',
        flush=True,
    )
    rclpy.init()
    node = LiveTargetCollector(args, contract, part_type)
    try:
        rclpy.spin(node)
    finally:
        completed = node.completed_payload is not None
        failure = node.last_rejection
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    if not completed:
        print(f'ERROR: {failure}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
