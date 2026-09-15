from collections import deque
import time

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger

from vision_interfaces.msg import Detections, Inspection

from .config_utils import default_path, load_yaml
from .inspection_rules import evaluate_parts, RuleResult


class AssemblyInspector(Node):
    def __init__(self) -> None:
        super().__init__('assembly_inspector')
        self.declare_parameter('parts_config', default_path('config/parts.yaml'))
        self.declare_parameter('inspection_config', default_path('config/inspection.yaml'))
        self.declare_parameter('auto', False)

        self._catalog = load_yaml(self.get_parameter('parts_config').value)['parts']
        rules = load_yaml(self.get_parameter('inspection_config').value)['inspection']
        self._camera = str(rules['camera'])
        self._exact_count = bool(rules.get('exact_count', True))
        self._unknown_class = str(rules.get('unknown_class', 'fail'))
        self._stable_frames = max(1, int(rules.get('stable_frames', 3)))
        self._max_age = max(0.1, float(rules.get('max_age_sec', 2.0)))
        self._auto = bool(self.get_parameter('auto').value)
        self._history = deque(maxlen=self._stable_frames)
        self._auto_published_for_window = False

        self._result_publisher = self.create_publisher(
            Inspection, str(rules['result_topic']), 10
        )
        self.create_subscription(
            Detections,
            str(rules['detection_topic']),
            self._on_detections,
            10,
        )
        self.create_service(Trigger, str(rules['service']), self._on_service)
        self.get_logger().info(
            f'Inspection camera={self._camera}, stable_frames={self._stable_frames}, '
            f'expected_total={sum(int(v["expected"]) for v in self._catalog.values())}'
        )

    def _on_detections(self, message: Detections) -> None:
        if message.camera != self._camera:
            return
        now = time.monotonic()
        if self._history and now - self._history[-1][0] > self._max_age:
            self._history.clear()
            self._auto_published_for_window = False
        evaluated = evaluate_parts(
            message.parts,
            self._catalog,
            exact_count=self._exact_count,
            unknown_class=self._unknown_class,
        )
        self._history.append((now, message, evaluated))
        if self._auto and len(self._history) == self._stable_frames:
            signatures = [entry[2].signature for entry in self._history]
            stable = all(signature == signatures[-1] for signature in signatures[:-1])
            if not stable:
                self._auto_published_for_window = False
            elif not self._auto_published_for_window:
                self._run_check()
                self._auto_published_for_window = True

    def _on_service(self, _request, response):
        status, message = self._run_check()
        response.success = status in ('PASS', 'FAIL')
        response.message = message
        return response

    def _run_check(self):
        if not self._history:
            self._publish_empty('WAIT', ['NO_DETECTION'])
            return 'WAIT', 'No S22 detection is available'

        receipt_time, detection, evaluated = self._history[-1]
        now = time.monotonic()
        if now - receipt_time > self._max_age:
            self._publish(detection, evaluated, 'WAIT', ['STALE_DETECTION'])
            return 'WAIT', 'The latest detection is stale'

        if len(self._history) < self._stable_frames:
            error = f'NEED_STABLE_FRAMES:{len(self._history)}/{self._stable_frames}'
            self._publish(detection, evaluated, 'WAIT', [error])
            return 'WAIT', error

        if any(now - entry[0] > self._max_age for entry in self._history):
            self._publish(detection, evaluated, 'WAIT', ['STALE_HISTORY'])
            return 'WAIT', 'The stable-frame history contains stale detections'

        signatures = [entry[2].signature for entry in self._history]
        if any(signature != signatures[-1] for signature in signatures[:-1]):
            self._publish(detection, evaluated, 'UNCERTAIN', ['UNSTABLE_COUNTS'])
            return 'UNCERTAIN', 'Part counts are not stable yet'

        self._publish(detection, evaluated, evaluated.status, evaluated.errors)
        summary = f'{evaluated.status}: {evaluated.found_total}/{evaluated.expected_total}'
        self.get_logger().info(summary)
        return evaluated.status, summary

    def _publish(
        self,
        detection: Detections,
        evaluated: RuleResult,
        status: str,
        errors,
    ) -> None:
        result = Inspection()
        result.header = detection.header
        result.camera = detection.camera
        result.board_id = ''
        result.recipe_id = 'default_assembly_25'
        result.status = status
        result.expected_total = evaluated.expected_total
        result.found_total = evaluated.found_total
        result.names = evaluated.names
        result.expected = evaluated.expected
        result.found = evaluated.found
        result.slot_ids = []
        result.slot_status = []
        result.errors = list(errors)
        self._result_publisher.publish(result)

    def _publish_empty(self, status: str, errors) -> None:
        names = list(self._catalog.keys())
        evaluated = RuleResult(
            status=status,
            names=names,
            expected=[int(self._catalog[name]['expected']) for name in names],
            found=[0] * len(names),
            errors=list(errors),
        )
        detection = Detections()
        detection.header.stamp = self.get_clock().now().to_msg()
        detection.camera = self._camera
        self._publish(detection, evaluated, status, errors)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = AssemblyInspector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
