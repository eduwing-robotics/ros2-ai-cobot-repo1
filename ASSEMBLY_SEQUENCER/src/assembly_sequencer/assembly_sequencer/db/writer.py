"""One-line production writes backed by a bounded in-process FIFO worker."""

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field

import psycopg

from . import production_store


ASSEMBLY_COMPLETED = "ASSEMBLY_COMPLETED"
INSPECTION_RECORDED = "INSPECTION_RECORDED"
JOB_FINISHED = "JOB_FINISHED"
DB_SYNC_TIMEOUT_SECONDS = 5.0


class DbQueueFull(RuntimeError):
    """The writer cannot accept another DB update without dropping data."""


@dataclass
class DbUpdateEvent:
    event_type: str
    job_id: str | None = None
    unit_id: int | None = None
    payload: dict = field(default_factory=dict)
    last_error: str = ""


class DbWriter:
    """Claim synchronously, then serialize lifecycle updates off callbacks."""

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

    def claim(
        self,
        job_id,
        product_code,
        product_version,
        recipe_version,
    ):
        with self._condition:
            if self._fatal_error:
                raise RuntimeError(self._last_error)
            if self._stop.is_set():
                raise RuntimeError("DB writer is stopped")
        return self._store.claim_job(
            self._job_id(job_id), product_code, product_version, recipe_version
        )

    def recover_interrupted(self):
        return self._store.recover_interrupted_units()

    def abort(self, job_id):
        """Synchronously close a Job rejected before robot acceptance."""
        with self._condition:
            if self._fatal_error:
                raise RuntimeError(self._last_error)
        self._store.finish_job(job_id, "FAILED")

    def get_job(self, job_id):
        return self._store.get_job_state(self._job_id(job_id))

    def get_product_slots(self, job_id):
        return self._store.get_product_slots(self._job_id(job_id))

    def get_next_runnable_job(self, product_code, product_version, recipe_version):
        return self._store.get_next_runnable_job(
            product_code, product_version, recipe_version
        )

    def assembly_completed(self, unit_id):
        self._positive_id(unit_id, "unit_id")
        return self._submit(DbUpdateEvent(
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
            event_type=INSPECTION_RECORDED,
            unit_id=unit_id,
            payload={
                "result": result,
                "defects": snapshot,
                "image_path": image_path,
            },
        ))

    def finish(self, job_id, final_status):
        job_id = self._job_id(job_id)
        if final_status not in production_store.FINAL_JOB_STATUSES:
            raise ValueError("final_status must be COMPLETED, FAILED or CANCELLED")
        return self._submit(DbUpdateEvent(
            event_type=JOB_FINISHED,
            job_id=job_id,
            payload={"final_status": final_status},
        ))

    def flush(self, timeout_seconds):
        deadline = time.monotonic() + timeout_seconds
        with self._condition:
            while True:
                if self._fatal_error:
                    raise RuntimeError(self._last_error)
                if not self._pending_count:
                    return True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._fail("DB synchronization timed out; " + self._last_error)
                    raise RuntimeError(self._last_error)
                self._condition.wait(remaining)

    def close(self, timeout_seconds=5.0):
        try:
            drained = self.flush(timeout_seconds)
        except RuntimeError:
            drained = False
        self._stop.set()
        self._thread.join(timeout_seconds)
        return drained and not self._thread.is_alive() and not self._fatal_error

    def _fail(self, message):
        with self._condition:
            if not self._fatal_error:
                self._fatal_error = True
                self._sync_state = "FAILED"
                self._last_error = message
            self._stop.set()
            self._condition.notify_all()

    @staticmethod
    def _job_id(value):
        try:
            return str(uuid.UUID(str(value)))
        except (TypeError, ValueError, AttributeError) as error:
            raise ValueError("job_id must be a UUID") from error

    @staticmethod
    def _positive_id(value, label):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{label} must be a positive integer")

    def _submit(self, event):
        with self._condition:
            if self._fatal_error:
                raise RuntimeError(self._last_error)
            if self._stop.is_set():
                raise RuntimeError("DB writer is stopped")
            try:
                self._queue.put_nowait(event)
            except queue.Full as error:
                self._fail("DB update queue is full")
                raise DbQueueFull(self._last_error) from error
            self._pending_count += 1
            self._sync_state = "PENDING"
            self._last_error = ""
            self._condition.notify_all()

    def _run(self):
        while not self._stop.is_set():
            try:
                event = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            delay = self._retry_initial_seconds
            deadline = time.monotonic() + DB_SYNC_TIMEOUT_SECONDS
            while not self._stop.is_set():
                if time.monotonic() >= deadline:
                    self._fail("DB retry deadline exceeded; " + event.last_error)
                    return
                try:
                    self._dispatch(event)
                except Exception as error:
                    event.last_error = f"{type(error).__name__}: {error}"
                    sqlstate = getattr(error, "sqlstate", None)
                    # These lifecycle transactions are idempotent: a lost commit
                    # response may mean the write already succeeded.
                    retryable = isinstance(error, psycopg.OperationalError) and (
                        sqlstate is None or sqlstate.startswith("08")
                        or sqlstate in {"40001", "40P01", "57P01", "57P02", "57P03"}
                    )
                    if not retryable:
                        self._fail(event.last_error)
                        return
                    with self._condition:
                        if not self._fatal_error:
                            self._sync_state = "PENDING"
                            self._last_error = event.last_error
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        self._fail("DB retry deadline exceeded; " + event.last_error)
                        return
                    if self._stop.wait(min(delay, remaining)):
                        return
                    delay = min(delay * 2, self._retry_max_seconds)
                    continue

                self._queue.task_done()
                with self._condition:
                    # An in-flight transaction can commit after flush times out.
                    # Keep the failure latched and never dispatch later events.
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
