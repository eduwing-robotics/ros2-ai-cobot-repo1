#!/usr/bin/env python3
"""Example ROS 2 subscriber for a DB/Main Server conveyor event adapter."""

import json
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from std_msgs.msg import String


STATE_TOPIC = '/conveyor/state'
STATE_TIMEOUT_SECONDS = 0.30


def persist_event(event: dict) -> None:
    """Replace this print with an idempotent DB insert/transaction."""
    print(json.dumps(event, ensure_ascii=False, separators=(',', ':')))


class ConveyorEventSubscriber(Node):
    """Convert conveyor state transitions and heartbeat loss into DB events."""

    def __init__(self) -> None:
        super().__init__('conveyor_event_subscriber')
        self.previous_state = None
        self.previous_arrival_id = None
        self.last_state_at = 0.0
        self.timeout_reported = False
        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(String, STATE_TOPIC, self.on_state, qos)
        self.create_timer(0.05, self.check_timeout)

    def on_state(self, message: String) -> None:
        received_at_ns = time.time_ns()
        try:
            state = json.loads(message.data)
        except json.JSONDecodeError as error:
            self.get_logger().error(f'Invalid conveyor state JSON: {error}')
            return
        if state.get('schema_version') != 1:
            self.get_logger().error('Unsupported conveyor state schema')
            return

        self.last_state_at = time.monotonic()
        self.timeout_reported = False
        current = state.get('state')
        if current != self.previous_state:
            persist_event({
                'event_type': 'CONVEYOR_STATE_CHANGED',
                'received_at_ns': received_at_ns,
                'previous_state': self.previous_state,
                'state': current,
                'reason': state.get('reason'),
                'target_station': state.get('target_station'),
                'source_timestamp_ns': state.get('timestamp_ns'),
            })
        arrival = state.get('arrival') or {}
        arrival_id = arrival.get('motion_id')
        station = {'ASSEMBLY_STOP':'assembly','INSPECTION_STOP':'inspection'}.get(current)
        new_arrival = (arrival_id != self.previous_arrival_id if arrival_id
                       else current != self.previous_state)
        if (station and state.get('moving') is False and new_arrival
                and (not arrival or arrival.get('station') == station)):
            persist_event({
                'event_type': 'STATION_REACHED',
                'received_at_ns': received_at_ns,
                'station': station,
                'motion_id': arrival_id,
                'source_timestamp_ns': arrival.get('timestamp_ns',state.get('timestamp_ns')),
                'basis': arrival.get('basis','VISION_COMMAND_STATE_NOT_ENCODER_FEEDBACK'),
            })
            self.previous_arrival_id = arrival_id
        self.previous_state = current

    def check_timeout(self) -> None:
        if not self.last_state_at:
            return
        age = time.monotonic() - self.last_state_at
        if age <= STATE_TIMEOUT_SECONDS or self.timeout_reported:
            return
        self.timeout_reported = True
        persist_event({
            'event_type': 'CONVEYOR_STATE_HEARTBEAT_TIMEOUT',
            'received_at_ns': time.time_ns(),
            'last_state': self.previous_state,
            'age_ms': round(age * 1000.0, 1),
        })


def main() -> None:
    """Run the DB adapter example until interrupted."""
    rclpy.init()
    node = ConveyorEventSubscriber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
