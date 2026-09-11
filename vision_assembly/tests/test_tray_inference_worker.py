"""Production callback keeps one native worker and never queues stale frames."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading
import traceback
import pytest
from test_tray_observation_snapshot import load_detector


@pytest.fixture
def worker():
    cls = load_detector()
    cls.inference_worker.__globals__['traceback'] = traceback
    node = cls.__new__(cls)
    node.a = SimpleNamespace(display_hz=0)
    node.processing_lock = threading.Lock()
    node.inference_pool = ThreadPoolExecutor(max_workers=1)
    node.processing_errors = 0
    node.errors = []
    node.get_logger = lambda: SimpleNamespace(error=node.errors.append)
    yield node
    node.inference_pool.shutdown(wait=True)


def drain(node):
    node.inference_pool.submit(lambda: None).result(timeout=5)


def test_reuses_same_native_worker_across_frames(worker):
    threads = []
    worker.process_color = lambda frame: threads.append(threading.current_thread())
    for i in range(100):
        worker.color_cb(i)
        drain(worker)
    assert len(threads) == 100
    assert all(t is threads[0] for t in threads)
    assert threads[0] is not threading.current_thread()


def test_busy_frames_are_dropped_and_next_fresh_frame_runs(worker):
    entered, release = threading.Event(), threading.Event()
    seen = []
    def process(frame):
        seen.append(frame)
        entered.set()
        assert release.wait(5)
    worker.process_color = process
    worker.color_cb('first')
    try:
        assert entered.wait(5)
        for i in range(1000):
            worker.color_cb(i)
    finally:
        release.set()
    drain(worker)
    assert seen == ['first']
    worker.color_cb('fresh')
    drain(worker)
    assert seen == ['first', 'fresh']


def test_frame_error_does_not_lock_out_next_frame(worker):
    def fail(frame):
        raise ValueError('bad frame')
    worker.process_color = fail
    worker.color_cb(None)
    drain(worker)
    assert worker.processing_errors == 1
    assert 'bad frame' in worker.errors[0]
    seen = []
    worker.process_color = seen.append
    worker.color_cb('recovered')
    drain(worker)
    assert seen == ['recovered']
    assert worker.processing_errors == 0


def test_submission_after_shutdown_releases_admission_lock(worker):
    worker.inference_pool.shutdown(wait=True)
    with pytest.raises(RuntimeError):
        worker.color_cb(None)
    assert not worker.processing_lock.locked()
