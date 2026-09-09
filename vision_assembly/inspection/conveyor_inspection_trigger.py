#!/usr/bin/env python3
"""Run one configured S22 pipeline for each inspection-station arrival."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import fcntl
import json
import math
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, Float32, String


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_PIPELINE = Path(__file__).resolve().parent / "triggered_inspection_once.py"
DEFAULT_EVENT = PROJECT_DIR / "runtime/inspection/auto_inspection_latest.json"
DEFAULT_LOCK = PROJECT_DIR / "runtime/s22_camera_control/auto_inspection_trigger.lock"


@dataclass
class TriggerGate:
    """One-shot gate that rearms only when a new upstream board is observed."""

    rearm_distance_px: float = 20.0
    rearm_hold_seconds: float = 0.5
    distance_fresh_seconds: float = 0.75
    armed: bool = True
    running: bool = False
    trigger: bool | None = None
    distance_px: float | None = None
    distance_at: float | None = None
    rearm_started_at: float | None = None

    def update_trigger(self, value: bool, now: float) -> bool:
        self.trigger = bool(value)
        if self.trigger:
            self.rearm_started_at = None
            if self.armed and not self.running:
                self.armed = False
                self.running = True
                return True
        return False

    def update_distance(self, value: float, now: float) -> None:
        if math.isfinite(value):
            self.distance_px = float(value)
            self.distance_at = float(now)

    def finish(self) -> None:
        self.running = False
        self.rearm_started_at = None

    def maybe_rearm(self, now: float) -> bool:
        if self.armed or self.running or self.trigger is not False:
            self.rearm_started_at = None
            return False
        fresh_distance = (
            self.distance_px is not None
            and self.distance_at is not None
            and now - self.distance_at <= self.distance_fresh_seconds
        )
        if not fresh_distance or self.distance_px < self.rearm_distance_px:
            self.rearm_started_at = None
            return False
        if self.rearm_started_at is None:
            self.rearm_started_at = now
            return False
        if now - self.rearm_started_at < self.rearm_hold_seconds:
            return False
        self.armed = True
        self.rearm_started_at = None
        return True


class ProcessLock:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._file.close()
            raise RuntimeError(
                f"another automatic inspection trigger is already running: {path}"
            ) from exc
        self._file.seek(0)
        self._file.truncate()
        self._file.write(f"{os.getpid()}\n")
        self._file.flush()

    def close(self) -> None:
        if self._file.closed:
            return
        fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        self._file.close()


class ConveyorInspectionTrigger(Node):
    def __init__(self, args: argparse.Namespace):
        super().__init__("conveyor_auto_inspector")
        self._args = args
        self._gate = TriggerGate(
            rearm_distance_px=args.rearm_distance_px,
            rearm_hold_seconds=args.rearm_hold_seconds,
            distance_fresh_seconds=args.distance_fresh_seconds,
        )
        self._gate_lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._process: subprocess.Popen | None = None
        self._process_lock = threading.Lock()
        self._results: queue.SimpleQueue[dict] = queue.SimpleQueue()

        result_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self._armed_pub = self.create_publisher(
            Bool, "/vision/inspection/auto/armed", result_qos
        )
        self._running_pub = self.create_publisher(
            Bool, "/vision/inspection/auto/running", result_qos
        )
        self._completed_pub = self.create_publisher(
            Bool, "/vision/inspection/auto/completed", result_qos
        )
        self._status_pub = self.create_publisher(
            String, "/vision/inspection/auto/status", result_qos
        )
        self._report_pub = self.create_publisher(
            String, "/vision/inspection/auto/report_path", result_qos
        )
        self._result_pub = self.create_publisher(
            String, "/vision/inspection/auto/result", result_qos
        )

        self.create_subscription(
            Bool, args.trigger_topic, self._trigger_callback, 10
        )
        self.create_subscription(
            Float32, args.distance_topic, self._distance_callback, 10
        )
        self.create_timer(0.1, self._tick)
        self._publish_state("ARMED", armed=True, running=False, completed=False)
        self.get_logger().info(
            f"Automatic S22 station pipeline armed: trigger={args.trigger_topic}, "
            f"distance={args.distance_topic}, settle={args.settle_seconds:.2f}s"
        )

    def _publish_state(
        self,
        status: str,
        *,
        armed: bool,
        running: bool,
        completed: bool,
    ) -> None:
        self._armed_pub.publish(Bool(data=armed))
        self._running_pub.publish(Bool(data=running))
        self._completed_pub.publish(Bool(data=completed))
        self._status_pub.publish(String(data=status))

    def _trigger_callback(self, message: Bool) -> None:
        now = time.monotonic()
        with self._gate_lock:
            should_start = self._gate.update_trigger(bool(message.data), now)
        if not should_start:
            return
        self.get_logger().warning(
            "VISION INSPECTION STATION REACHED: stopping settle timer started"
        )
        self._publish_state(
            "SETTLING", armed=False, running=True, completed=False
        )
        self._worker = threading.Thread(
            target=self._run_pipeline,
            name="s22-auto-inspection",
            daemon=True,
        )
        self._worker.start()

    def _distance_callback(self, message: Float32) -> None:
        with self._gate_lock:
            self._gate.update_distance(float(message.data), time.monotonic())

    def _run_pipeline(self) -> None:
        if self._shutdown_event.wait(self._args.settle_seconds):
            return
        self._results.put({"kind": "started"})
        command = [
            sys.executable,
            str(self._args.pipeline),
            "--event-output",
            str(self._args.event_file),
            "--source-topic",
            self._args.trigger_topic,
        ]
        try:
            process = subprocess.Popen(command, start_new_session=True)
            with self._process_lock:
                self._process = process
            return_code = process.wait()
            with self._process_lock:
                self._process = None
            event = self._read_event()
            if return_code != 0:
                event.setdefault(
                    "error", f"inspection pipeline exited with code {return_code}"
                )
                event["pipeline_status"] = "ERROR"
                event["final_status"] = "ERROR"
            self._results.put({"kind": "finished", "event": event})
        except BaseException as exc:
            with self._process_lock:
                self._process = None
            self._results.put(
                {
                    "kind": "finished",
                    "event": {
                        "pipeline_status": "ERROR",
                        "final_status": "ERROR",
                        "report": None,
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                }
            )

    def _read_event(self) -> dict:
        try:
            return json.loads(self._args.event_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
            return {
                "pipeline_status": "ERROR",
                "final_status": "ERROR",
                "report": None,
                "error": f"could not read pipeline event: {exc}",
            }

    def _tick(self) -> None:
        while True:
            try:
                result = self._results.get_nowait()
            except queue.Empty:
                break
            if result["kind"] == "started":
                self._publish_state(
                    "CAPTURING", armed=False, running=True, completed=False
                )
                self.get_logger().info(
                    "Capturing S22 telephoto image and running the configured station pipeline."
                )
                continue

            event = result["event"]
            final_status = str(event.get("final_status", "ERROR"))
            report = str(event.get("report") or "")
            error = str(event.get("error") or "")
            with self._gate_lock:
                self._gate.finish()
            self._publish_state(
                final_status, armed=False, running=False, completed=True
            )
            self._report_pub.publish(String(data=report))
            self._result_pub.publish(
                String(data=json.dumps(event, ensure_ascii=False))
            )
            if final_status == "ERROR":
                self.get_logger().error(f"Automatic inspection failed: {error}")
            else:
                self.get_logger().warning(
                    f"AUTOMATIC STATION RESULT: {final_status}; report={report}"
                )
            if self._args.once:
                self.get_logger().info("--once complete; shutting down trigger node.")
                rclpy.shutdown()

        with self._gate_lock:
            rearmed = self._gate.maybe_rearm(time.monotonic())
        if rearmed:
            self._publish_state(
                "ARMED", armed=True, running=False, completed=False
            )
            self.get_logger().info(
                "New upstream board confirmed; automatic inspection rearmed."
            )

    def close(self) -> None:
        self._shutdown_event.set()
        with self._process_lock:
            process = self._process
        if process is not None and process.poll() is None:
            self.get_logger().warning("Stopping active inspection pipeline.")
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=8.0)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2.0)
        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=2.0)


def positive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise argparse.ArgumentTypeError("value must be finite and > 0")
    return number


def nonnegative_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise argparse.ArgumentTypeError("value must be finite and >= 0")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Subscribe to the conveyor inspection stop trigger and run one "
            "configured S22 station pipeline per arriving PCB."
        )
    )
    parser.add_argument(
        "--trigger-topic",
        default="/vision/conveyor/inspection/stop_trigger",
    )
    parser.add_argument(
        "--distance-topic",
        default="/vision/conveyor/inspection/distance_to_stop_px",
    )
    parser.add_argument(
        "--settle-seconds",
        type=nonnegative_float,
        default=0.35,
        help="delay after stop trigger before opening Samsung Camera",
    )
    parser.add_argument(
        "--rearm-distance-px",
        type=positive_float,
        default=20.0,
        help="minimum upstream distance required before accepting the next PCB",
    )
    parser.add_argument(
        "--rearm-hold-seconds",
        type=positive_float,
        default=0.5,
    )
    parser.add_argument(
        "--distance-fresh-seconds",
        type=positive_float,
        default=0.75,
    )
    parser.add_argument("--pipeline", type=Path, default=DEFAULT_PIPELINE)
    parser.add_argument("--event-file", type=Path, default=DEFAULT_EVENT)
    parser.add_argument(
        "--once",
        action="store_true",
        help="exit after the first inspection (default keeps monitoring)",
    )
    parser.add_argument("--lock-file", type=Path, default=DEFAULT_LOCK)
    args = parser.parse_args()
    args.pipeline = args.pipeline.expanduser().resolve()
    args.event_file = args.event_file.expanduser().resolve()
    args.lock_file = args.lock_file.expanduser().resolve()
    return args


def main() -> int:
    args = parse_args()
    if not args.pipeline.is_file():
        raise SystemExit(f"inspection pipeline is missing: {args.pipeline}")
    try:
        process_lock = ProcessLock(args.lock_file)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    rclpy.init()
    node = ConveyorInspectionTrigger(args)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Ctrl+C received; stopping automatic inspection.")
    except ExternalShutdownException:
        # Expected when --once asks rclpy to stop from the result timer.
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        process_lock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
