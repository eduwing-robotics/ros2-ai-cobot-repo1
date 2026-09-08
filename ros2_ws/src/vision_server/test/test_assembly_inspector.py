"""Exercise actual inspector callbacks without constructing a ROS node."""
from collections import deque
from types import SimpleNamespace

import pytest

from vision_server.assembly_inspector import AssemblyInspector


@pytest.fixture
def inspector(monkeypatch):
    clock = SimpleNamespace(monotonic=5.0, source_ns=10_000_000_000)
    monkeypatch.setattr('vision_server.assembly_inspector.time.monotonic', lambda: clock.monotonic)
    node = object.__new__(AssemblyInspector)
    node._camera = 's22'
    node._catalog = {'gpu': {'expected': 1, 'min_score': .6}}
    node._exact_count = True
    node._unknown_class = 'fail'
    node._stable_frames = 3
    node._max_age = 2.0
    node._auto = False
    node._history = deque(maxlen=3)
    node._last_source_ns = None
    node._input_error = None
    node._auto_published_for_window = False
    node.get_clock = lambda: SimpleNamespace(now=lambda: SimpleNamespace(nanoseconds=clock.source_ns))
    node.get_logger = lambda: SimpleNamespace(info=lambda _: None)
    published = []
    node._publish = lambda d, e, status, errors: published.append((status, errors))
    node._publish_empty = lambda status, errors: published.append((status, errors))
    return node, clock, published


def detection(stamp_ns=9_800_000_000, score=.9):
    return SimpleNamespace(camera='s22', parts=[{'name': 'gpu', 'score': score}],
        header=SimpleNamespace(stamp=SimpleNamespace(
            sec=stamp_ns // 1_000_000_000, nanosec=stamp_ns % 1_000_000_000)))


def fill(node):
    for stamp in (9_700_000_000, 9_800_000_000, 9_900_000_000):
        node._on_detections(detection(stamp))


def test_three_distinct_fresh_frames_pass(inspector):
    node, _, _ = inspector
    fill(node)
    assert node._run_check()[0] == 'PASS'


@pytest.mark.parametrize('stamp,reason', [
    (1_000_000_000, 'STALE_SOURCE_FRAME'),
    (0, 'INVALID_SOURCE_STAMP'),
    (10_000_000_001, 'FUTURE_SOURCE_FRAME'),
])
def test_repeated_old_zero_and_future_frames_cannot_pass(inspector, stamp, reason):
    node, _, published = inspector
    for _ in range(3):
        node._on_detections(detection(stamp))
    assert node._run_check()[0] == 'WAIT'
    assert published[-1] == ('WAIT', [reason])


@pytest.mark.parametrize('stamp,reason', [
    (9_900_000_000, 'DUPLICATE_SOURCE_FRAME'),
    (9_850_000_000, 'REVERSED_SOURCE_FRAME'),
])
def test_duplicate_or_reversal_invalidates_an_existing_pass(inspector, stamp, reason):
    node, _, _ = inspector
    fill(node)
    assert node._run_check()[0] == 'PASS'
    node._on_detections(detection(stamp))
    assert node._run_check() == ('WAIT', reason)
    for fresh in (9_910_000_000, 9_920_000_000):
        node._on_detections(detection(fresh))
        assert node._run_check()[0] == 'WAIT'
    node._on_detections(detection(9_930_000_000))
    assert node._run_check()[0] == 'PASS'


def test_fresh_receipt_cannot_hide_expired_source_frames(inspector):
    node, clock, _ = inspector
    fill(node)
    clock.source_ns += 2_000_000_000
    # All receipt ages are still zero; the source window has expired.
    assert node._run_check()[0] == 'WAIT'


def test_expired_receipt_cannot_be_revived_by_source_clock_reversal(inspector):
    node, clock, _ = inspector
    fill(node)
    clock.monotonic += 3
    assert node._run_check()[0] == 'WAIT'


@pytest.mark.parametrize('score', [float('nan'), float('inf'), -float('inf'), -0.01, 1.01, None, 'bad'])
def test_invalid_score_cannot_form_stable_success_window(inspector, score):
    node, _, _ = inspector
    fill(node)
    node._on_detections(detection(9_950_000_000, score))
    assert node._run_check() == ('WAIT', 'INVALID_DETECTION_SCORE')
    node._on_detections(detection(9_960_000_000))
    assert node._run_check()[0] == 'WAIT'


def test_auto_mode_publishes_wait_when_repeated_frame_invalidates_pass(inspector):
    node, _, published = inspector
    node._auto = True
    fill(node)
    assert published[-1][0] == 'PASS'
    node._on_detections(detection(9_900_000_000))
    assert published[-1] == ('WAIT', ['DUPLICATE_SOURCE_FRAME'])
