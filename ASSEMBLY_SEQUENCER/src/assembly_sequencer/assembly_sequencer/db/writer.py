"""One-line production writes backed by a bounded in-process FIFO worker."""

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import production_store


ASSEMBLY_COMPLETED = "ASSEMBLY_COMPLETED"
INSPECTION_RECORDED = "INSPECTION_RECORDED"
JOB_FINISHED = "JOB_FINISHED"


class DbQueueFull(RuntimeError):
    """The writer cannot accept another DB update without dropping data."""


@dataclass
class DbUpdateEvent:
    event_id: str
    event_type: str
    job_id: int | None = None
    unit_id: int | None = None
    payload: dict = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    attempt_count: int = 0
    next_retry_at: float = 0.0
    last_error: str = ""


class DbWriter:
    """Reserve synchronously, then serialize lifecycle updates off callbacks."""

    def __init__(
        self,
        store=production_store,
        queue_size=128,
        retry_initial_seconds=0.25,
        retry_max_seconds=5.0,
    ):
        if (
            isinstance(queue_size, bool)
            or not isinstance(queue_size, int)
            or queue_size <= 0
        ):
            raise ValueError("queue_size must be a positive integer")
        if retry_initial_seconds <= 0 or retry_max_seconds < retry_initial_seconds:
            raise ValueError("retry delays must be positive and ordered")

        self._store = store
        self._queue = queue.Queue(maxsize=queue_size)
        self._retry_initial_seconds = float(retry_initial_seconds)
        self._retry_max_seconds = float(retry_max_seconds)
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._pending_count = 0
        self._sync_state = "NOT_STARTED"
        self._last_error = ""
        self._fatal_error = False
        self._thread = threading.Thread(
            target=self._run,
            name="assembly-db-writer",
            daemon=True,
        )
        self._thread.start()

    @property
    def sync_state(self):
        with self._condition:
            return self._sync_state

    @property
    def last_error(self):
        with self._condition:
            return self._last_error

    @property
    def pending_count(self):
        with self._condition:
            return self._pending_count

    def reserve(
        self,
        request_id,
        product_code,
        product_version,
        recipe_version,
        quantity=1,
    ):
        with self._condition:
            if self._stop.is_set():
                raise RuntimeError("DB writer is stopped")
            if self._fatal_error:
                raise RuntimeError(self._last_error)
        try:
            uuid.UUID(request_id)
        except (TypeError, ValueError, AttributeError) as error:
            raise ValueError("request_id must be a UUID string") from error
        return self._store.reserve_work(
            product_code, product_version, quantity, recipe_version
        )

    def abort(self, job_id):
        """Synchronously close a reservation rejected before robot acceptance."""
        self._store.finish_job(job_id, "FAILED")

    def get_active(self):
        return self._store.get_active_job_state()

    def get_product_slot_codes(self, job_id):
        return self._store.get_product_slot_codes(job_id)

    def assembly_completed(self, unit_id):
        self._positive_id(unit_id, "unit_id")
        return self._submit(DbUpdateEvent(
            event_id=str(uuid.uuid4()),
            event_type=ASSEMBLY_COMPLETED,
            unit_id=unit_id,
        ))

    def inspection_recorded(self, unit_id, result, defects, image_path=None):
        self._positive_id(unit_id, "unit_id")
        if image_path is not None and not isinstance(image_path, str):
            raise ValueError("image_path must be a string or None")
        normalized = production_store.normalize_defects(result, defects)
        snapshot = [
            {"slot_code": slot_code, "defect_type": defect_type}
            for slot_code, defect_type in normalized
        ]
        return self._submit(DbUpdateEvent(
            event_id=str(uuid.uuid4()),
            event_type=INSPECTION_RECORDED,
            unit_id=unit_id,
            payload={
                "result": result,
                "defects": snapshot,
                "image_path": image_path,
            },
        ))

    def finish(self, job_id, final_status):
        self._positive_id(job_id, "job_id")
        if final_status not in production_store.FINAL_JOB_STATUSES:
            raise ValueError("final_status must be COMPLETED, FAILED or CANCELLED")
        return self._submit(DbUpdateEvent(
            event_id=str(uuid.uuid4()),
            event_type=JOB_FINISHED,
            job_id=job_id,
            payload={"final_status": final_status},
        ))

    def flush(self, timeout_seconds):
        deadline = time.monotonic() + timeout_seconds
        with self._condition:
            while self._pending_count:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True

    def close(self, timeout_seconds=5.0):
        drained = self.flush(timeout_seconds)
        self._stop.set()
        self._thread.join(timeout_seconds)
        if not drained:
            with self._condition:
                self._sync_state = "FAILED"
                self._last_error = (
                    f"writer stopped with {self._pending_count} pending event(s)"
                )
        return drained and not self._thread.is_alive() and not self._fatal_error

    @staticmethod
    def _positive_id(value, label):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{label} must be a positive integer")

    def _submit(self, event):
        with self._condition:
            if self._stop.is_set():
                raise RuntimeError("DB writer is stopped")
            if self._fatal_error:
                raise RuntimeError(self._last_error)
            try:
                self._queue.put_nowait(event)
            except queue.Full as error:
                self._fatal_error = True
                self._sync_state = "FAILED"
                self._last_error = "DB update queue is full"
                raise DbQueueFull(self._last_error) from error
            self._pending_count += 1
            self._sync_state = "PENDING"
            self._last_error = ""
            self._condition.notify_all()
        return event.event_id

    def _run(self):
        while not self._stop.is_set():
            try:
                event = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            delay = self._retry_initial_seconds
            while not self._stop.is_set():
                try:
                    self._dispatch(event)
                except Exception as error:
                    event.attempt_count += 1
                    event.last_error = str(error)
                    event.next_retry_at = time.time() + delay
                    with self._condition:
                        if not self._fatal_error:
                            self._sync_state = "PENDING"
                            self._last_error = event.last_error
                    if self._stop.wait(delay):
                        return
                    delay = min(delay * 2, self._retry_max_seconds)
                    continue

                self._queue.task_done()
                with self._condition:
                    self._pending_count -= 1
                    if not self._fatal_error:
                        self._sync_state = (
                            "SYNCED" if self._pending_count == 0 else "PENDING"
                        )
                        self._last_error = ""
                    self._condition.notify_all()
                break

    def _dispatch(self, event):
        if event.event_type == ASSEMBLY_COMPLETED:
            self._store.complete_assembly_and_consume_stock(event.unit_id)
            return
        if event.event_type == INSPECTION_RECORDED:
            self._store.record_inspection(event.unit_id, **event.payload)
            return
        if event.event_type == JOB_FINISHED:
            self._store.finish_job(event.job_id, event.payload["final_status"])
            return
        raise RuntimeError(f"unsupported DB event: {event.event_type}")
