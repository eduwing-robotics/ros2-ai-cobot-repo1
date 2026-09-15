"""Offline callbacks only: no ROS Node, executor, publisher, or equipment."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import vision_server.conveyor_controller as controller_module
from vision_server.conveyor_controller import ConveyorController, heartbeat_is_fresh


NOW = 100.0


class ControllerHarness:
    control_tick = ConveyorController.control_tick
    ready_callback = ConveyorController.ready_callback
    trigger_callback = ConveyorController.trigger_callback
    request_stop = ConveyorController.request_stop

    def __init__(self):
        self.trigger = False
        self.ready = True
        self.last_ready_time = NOW
        self.last_trigger_time = NOW
        self.started_at = NOW - 1.0
        self.timeout = 15.0
        self.heartbeat_timeout = 0.15
        self.stopped = False
        self.stop_reason = ''
        self.stop_publish_count = 0
        self.station = 'assembly'
        self.command_speed = -0.10
        self.publish_speed = Mock()
        self.get_logger = Mock(return_value=Mock())


@pytest.fixture
def controller(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('offline conveyor tests must never initialize ROS')

    monkeypatch.setattr(controller_module.rclpy, 'init', forbidden)
    monkeypatch.setattr(controller_module.Node, '__init__', forbidden)
    monkeypatch.setattr(controller_module.rclpy, 'shutdown', Mock())
    monkeypatch.setattr(controller_module.time, 'monotonic', lambda: NOW)
    return ControllerHarness()


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf'), NOW + 1.0, -1.0])
@pytest.mark.parametrize('field', ['last_ready_time', 'last_trigger_time'])
def test_legacy_status_timestamps_do_not_stop_ready_motion(controller, field, bad):
    setattr(controller, field, bad)
    controller.control_tick()
    assert not controller.stopped
    controller.publish_speed.assert_called_once_with(-0.10)


def test_ready_false_then_true_between_ticks_cannot_cancel_stop(controller):
    controller.ready_callback(SimpleNamespace(data=False))
    controller.publish_speed.assert_called_once_with(0.0)
    controller.ready_callback(SimpleNamespace(data=True))
    controller.control_tick()
    assert controller.stopped
    assert all(call.args == (0.0,) for call in controller.publish_speed.call_args_list)


def test_stop_trigger_is_immediate_and_repeated_zero_shutdown_is_preserved(controller):
    controller.trigger_callback(SimpleNamespace(data=True))
    controller.trigger_callback(SimpleNamespace(data=False))
    for _ in range(9):
        controller.control_tick()
    assert controller.stopped
    assert controller.stop_publish_count == 10
    assert all(call.args == (0.0,) for call in controller.publish_speed.call_args_list)
    controller_module.rclpy.shutdown.assert_called_once_with()


def test_ready_status_and_unexpired_timeout_preserve_speed(controller):
    controller.control_tick()
    controller.publish_speed.assert_called_once_with(-0.10)
    assert not controller.stopped


def test_ready_false_waits_without_startup_heartbeat_timeout(controller):
    controller.ready = False
    controller.control_tick()
    assert not controller.stopped
    controller.publish_speed.assert_called_once_with(0.0)
    controller.started_at = NOW - 3.01
    controller.control_tick()
    assert not controller.stopped
    assert all(call.args == (0.0,) for call in controller.publish_speed.call_args_list)


def test_disabled_motion_timeout_does_not_reenable_heartbeat_watchdog(controller):
    controller.timeout = 0.0
    controller.started_at = NOW - 50.0
    controller.control_tick()
    controller.publish_speed.assert_called_once_with(-0.10)
    controller.last_ready_time = NOW - 0.151
    controller.control_tick()
    assert not controller.stopped
    assert controller.publish_speed.call_args.args == (-0.10,)


def test_elapsed_motion_timeout_stops_with_fresh_heartbeats(controller):
    controller.started_at = NOW - controller.timeout
    controller.control_tick()
    assert controller.stop_reason == 'safety timeout'
    controller.publish_speed.assert_called_once_with(0.0)


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), NOW + 1.0])
def test_invalid_start_clock_stops(controller, bad):
    controller.started_at = bad
    controller.control_tick()
    assert controller.stop_reason == 'invalid motion clock'
    controller.publish_speed.assert_called_once_with(0.0)


def test_freshness_boundary_and_invalid_window():
    assert heartbeat_is_fresh(NOW - 0.15, NOW, 0.15)
    assert not heartbeat_is_fresh(NOW - 0.151, NOW, 0.15)
    assert not heartbeat_is_fresh(NOW, NOW, float('inf'))
    assert not heartbeat_is_fresh(NOW, NOW, 0.0)
