#!/usr/bin/env python3
"""Read-only S22 arrival probe: subscribe to images/state, never call motion services.

Uses the same raw-frame adapter as the ROI node. No stop-trigger, ready, cmd_vel,
arrival-observation or controller-state publisher is created by this probe.
"""
import argparse
from collections import Counter
import inspect
import json
from pathlib import Path
import time

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String

from vision_server.config_utils import load_yaml
from vision_server.conveyor_arrival import LiveArrival
from vision_server.conveyor_roi import (
    ConveyorStopLine, SENSOR_QOS, detect_dark_boards, spacing_is_safe,
    station_separation_px, timestamp_age_seconds,
)


class Probe(Node):
    _update_arrivals = ConveyorStopLine._update_arrivals

    def __init__(self, config):
        super().__init__('conveyor_arrival_readonly_probe', enable_rosout=False,
                         start_parameter_services=False)
        cv2.setNumThreads(2)
        self.config = config
        self._empty_belt_region = config.get("empty_belt_region")
        self._arrival = LiveArrival(max_age=config['max_frame_age_seconds'],
                                   **config.get('arrival_observation', {}))
        detector = config['board_detection']
        self._travel_direction = detector['travel_direction']
        self._stations = {name: ConveyorStopLine._make_station(name, name, line, (0, 0, 0))
                          for name, line in config['stop_lines'].items()}
        allowed = inspect.signature(detect_dark_boards).parameters
        self.detector = {k:v for k,v in detector.items() if k in allowed}
        self.detector['search_bounds'] = tuple(detector[k] for k in
            ('search_x_start', 'search_x_end', 'search_y_start', 'search_y_end'))
        self.counts = Counter()
        self.latest = {}
        self.rows = []
        self.last_motor_input = None
        self.create_subscription(String, '/conveyor/state', self._arrival_motor_callback, 1)
        self.create_subscription(CompressedImage, config['image_topic'], self.image, SENSOR_QOS)
        self.create_timer(.05, self._publish_arrivals)

    def _arrival_motor_callback(self, message):
        self.counts['motor_messages'] += 1
        try:
            state = json.loads(message.data)
            self.last_motor_input = {k: state.get(k) for k in
                ('timestamp_ns', 'state', 'moving', 'command_linear_x_mps',
                 'server_instance_id', 'motion_id', 'armed')}
        except (ValueError, TypeError, AttributeError):
            self.last_motor_input = {'parse_error': True}
        ConveyorStopLine._arrival_motor_callback(self, message)

    def _publish_arrivals(self):
        now = self.get_clock().now().nanoseconds
        self.latest = {name: self._arrival.snapshot(name, now) for name in self._stations}

    def image(self, msg):
        self.counts['received_images'] += 1
        now = self.get_clock().now().nanoseconds
        age = timestamp_age_seconds(now, msg.header.stamp.sec, msg.header.stamp.nanosec)
        if not np.isfinite(age) or age > self._arrival.max_age:
            self._arrival.invalidate('STALE_INPUT_IMAGE')
            self.counts['stale_images'] += 1
            return
        try:
            img = cv2.imdecode(np.frombuffer(msg.data, np.uint8), cv2.IMREAD_COLOR)
        except cv2.error:
            img = None
        if img is None:
            self._arrival.invalidate('DECODE_FAILED')
            return
        max_width = self.config['processing_max_width']
        if img.shape[1] > max_width:
            img = cv2.resize(img, (max_width, round(img.shape[0]*max_width/img.shape[1])),
                             interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
        boards = detect_dark_boards(img, **self.detector)
        spacing = self.config['station_spacing']
        separation = station_separation_px(self._stations['assembly'].line,
                                           self._stations['inspection'].line, w, h)
        valid = not boards or spacing_is_safe(separation, max(b.travel_length_px for b in boards),
            spacing['minimum_board_lengths'], spacing['minimum_clearance_px'])[0]
        self._update_arrivals(msg, boards, w, h, valid, img)
        self.rows.append(dict(source_timestamp_ns=self._arrival.last_frame,
                              board_count=len(boards), observations=self.latest))
        for name, state in self.latest.items():
            self.counts[f'{name}:{state["status"]}'] += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('ros2_ws/src/vision_server/config/conveyor_roi.yaml'))
    parser.add_argument('--seconds', type=float, default=15)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 0 < args.seconds <= 60 or args.output.exists():
        parser.error('Use 0 < seconds <= 60 and a new output file')
    rclpy.init()
    node = Probe(load_yaml(args.config)['conveyor_roi'])
    try:
        end = time.monotonic()+args.seconds
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=.05)
        payload = dict(mode='READ_ONLY_NO_MOTION', counts=dict(node.counts), latest=node.latest,
                       last_motor_input=node.last_motor_input,
                       motor_publishers=[dict(node=p.node_name, namespace=p.node_namespace)
                                         for p in node.get_publishers_info_by_topic('/conveyor/state')],
                       frames=node.rows, robot_command_sent=False, conveyor_command_sent=False)
        with args.output.open('x') as stream:
            json.dump(payload, stream, indent=2, allow_nan=False)
        print(json.dumps({k:v for k,v in payload.items() if k != 'frames'}, indent=2))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
