"""Small checks for FIFO retry and explicit overflow handling."""

import sys
import threading
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assembly_sequencer.db import DbQueueFull, DbWriter, WorkReservation


REQUEST_ID = "12345678-1234-5678-1234-567812345678"


class FakeStore:
    def __init__(self):
        self.calls = []
        self.fail_first_assembly = True

    def reserve_work(self, product_code, product_version, quantity, recipe_version):
        self.calls.append((
            "reserve", product_code, product_version, quantity, recipe_version
        ))
        return WorkReservation(11, 22)

    def get_active_job_state(self):
        return None

    def get_product_slot_codes(self, job_id):
        return ["SLOT-01"]

    def complete_assembly_and_consume_stock(self, unit_id):
        self.calls.append(("assembly", unit_id))
        if self.fail_first_assembly:
            self.fail_first_assembly = False
            raise RuntimeError("temporary DB outage")

    def record_inspection(self, unit_id, result, defects, image_path=None):
        self.calls.append((
            "inspection", unit_id, result, defects, image_path
        ))

    def finish_job(self, job_id, final_status):
        self.calls.append(("finish", job_id, final_status))


class DbWriterTest(unittest.TestCase):
    def test_reserve_and_fifo_retry(self):
        store = FakeStore()
        writer = DbWriter(
            store=store,
            retry_initial_seconds=0.001,
            retry_max_seconds=0.002,
        )
        self.addCleanup(writer.close, 0.5)

        reservation = writer.reserve(
            REQUEST_ID, "PRODUCT", "v1", "recipe-v1"
        )
        self.assertEqual(reservation, WorkReservation(11, 22))
        writer.assembly_completed(reservation.unit_id)
        writer.inspection_recorded(reservation.unit_id, "PASS", [])
        writer.finish(reservation.job_id, "COMPLETED")

        self.assertTrue(writer.flush(1.0))
        self.assertEqual(
            [call[0] for call in store.calls],
            ["reserve", "assembly", "assembly", "inspection", "finish"],
        )
        self.assertEqual(writer.sync_state, "SYNCED")
        self.assertEqual(writer.pending_count, 0)

    def test_queue_overflow_is_reported(self):
        started = threading.Event()
        release = threading.Event()

        class BlockingStore(FakeStore):
            def complete_assembly_and_consume_stock(self, unit_id):
                self.calls.append(("assembly", unit_id))
                started.set()
                release.wait(1.0)

        store = BlockingStore()
        writer = DbWriter(store=store, queue_size=1)
        self.addCleanup(writer.close, 0.5)
        self.addCleanup(release.set)

        writer.assembly_completed(22)
        self.assertTrue(started.wait(1.0))
        writer.finish(11, "FAILED")
        with self.assertRaises(DbQueueFull):
            writer.finish(12, "FAILED")
        self.assertEqual(writer.sync_state, "FAILED")

        release.set()
        self.assertTrue(writer.flush(1.0))
        self.assertEqual(writer.sync_state, "FAILED")
        with self.assertRaises(RuntimeError):
            writer.finish(13, "FAILED")


if __name__ == "__main__":
    unittest.main()
