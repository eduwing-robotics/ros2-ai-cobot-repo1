import sys
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from conveyor_inspection_trigger import TriggerGate  # noqa: E402


def test_trigger_fires_once_while_latched_true():
    gate = TriggerGate()
    assert gate.update_trigger(False, 0.0) is False
    assert gate.update_trigger(True, 1.0) is True
    assert gate.update_trigger(True, 1.1) is False
    assert gate.update_trigger(True, 1.2) is False


def test_capture_pause_false_does_not_rearm_same_board():
    gate = TriggerGate()
    assert gate.update_trigger(True, 0.0) is True
    gate.update_distance(3.0, 0.0)
    gate.update_trigger(False, 1.0)
    gate.finish()
    assert gate.maybe_rearm(1.1) is False
    assert gate.maybe_rearm(2.0) is False


def test_fresh_upstream_board_rearms_then_triggers_once():
    gate = TriggerGate(rearm_hold_seconds=0.5)
    assert gate.update_trigger(True, 0.0) is True
    gate.finish()
    gate.update_trigger(False, 2.0)
    gate.update_distance(35.0, 2.0)
    assert gate.maybe_rearm(2.0) is False
    gate.update_distance(34.0, 2.4)
    assert gate.maybe_rearm(2.4) is False
    gate.update_distance(33.0, 2.6)
    assert gate.maybe_rearm(2.6) is True
    assert gate.update_trigger(True, 2.7) is True


def test_stale_distance_cannot_rearm():
    gate = TriggerGate(distance_fresh_seconds=0.5)
    assert gate.update_trigger(True, 0.0) is True
    gate.finish()
    gate.update_trigger(False, 1.0)
    gate.update_distance(40.0, 1.0)
    assert gate.maybe_rearm(2.0) is False
