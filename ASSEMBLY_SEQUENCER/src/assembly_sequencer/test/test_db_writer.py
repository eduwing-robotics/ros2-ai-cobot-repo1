"""Checks for DB retry and the conveyor-inspection-transfer gate."""

import json
import random
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assembly_sequencer.db import DbQueueFull, DbWriter
from assembly_sequencer.mock_node import MockAssemblySequencer


JOB_ID = "12345678-1234-5678-1234-567812345678"


class FakeStore:
    FINAL_JOB_STATUSES = ("COMPLETED", "FAILED", "CANCELLED")

    def __init__(self):
        self.calls = []
        self.fail_first_assembly = True

    def claim_job(self, job_id, product_code, product_version, recipe_version):
        self.calls.append((
            "claim", job_id, product_code, product_version, recipe_version
        ))
        return {"job_id": job_id, "unit_id": 22}

    def complete_assembly_and_consume_stock(self, unit_id):
        self.calls.append(("assembly", unit_id))
        if self.fail_first_assembly:
            self.fail_first_assembly = False
            raise RuntimeError("temporary DB outage")

    def record_inspection(self, unit_id, result, defects, image_path=None):
        self.calls.append(("inspection", unit_id, result, defects, image_path))

    def finish_job(self, job_id, final_status):
        self.calls.append(("finish", job_id, final_status))


class DbWriterTest(unittest.TestCase):
    def test_claim_and_fifo_retry(self):
        store = FakeStore()
        writer = DbWriter(
            store=store, retry_initial_seconds=0.001, retry_max_seconds=0.002
        )
        self.addCleanup(writer.close, 0.5)

        work = writer.claim(JOB_ID, "PRODUCT", "v1", "recipe-v1")
        writer.assembly_completed(work["unit_id"])
        writer.inspection_recorded(work["unit_id"], "PASS", [])
        writer.finish(work["job_id"], "COMPLETED")

        self.assertTrue(writer.flush(1.0))
        self.assertEqual(
            [call[0] for call in store.calls],
            ["claim", "assembly", "assembly", "inspection", "finish"],
        )
        self.assertEqual(writer.sync_state, "SYNCED")

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
        writer.finish(JOB_ID, "FAILED")
        with self.assertRaises(DbQueueFull):
            writer.finish("87654321-4321-8765-4321-876543218765", "FAILED")
        self.assertEqual(writer.sync_state, "FAILED")


class TransferSequenceTest(unittest.IsolatedAsyncioTestCase):
    async def test_inspection_precedes_assembled_pcb_transfer(self):
        calls = []

        class Writer:
            sync_state = "SYNCED"

            def assembly_completed(self, unit_id):
                calls.append(("assembly", unit_id))

            def inspection_recorded(self, unit_id, result, defects, image_path):
                calls.append(("inspection", unit_id, result))

        class Backend:
            async def transfer_assembled_pcb(self, job_id, assembled_pcb):
                calls.append(("transfer", job_id, assembled_pcb))

        active = {
            "job_id": JOB_ID,
            "state": "PLACED",
            "unit_id": 22,
            "slot_codes": ["SLOT-01"],
            "transfer_requested": False,
            "inspection_result": "",
            "assembled_pcb": {},
        }
        sequencer = SimpleNamespace(
            active=active,
            recipe_version="assembly-r1",
            rng=random.Random(1),
            fail_probability=0.0,
            db_writer=Writer(),
            backend=Backend(),
            set_response=MockAssemblySequencer.set_response,
        )
        request = SimpleNamespace(cmd_str=json.dumps({
            "command": "transfer_assembled_pcb",
            "job_id": JOB_ID,
            "assembled_pcb": {"source": {}, "target": {}},
        }))

        busy = await MockAssemblySequencer.on_external_request(
            sequencer, request, SimpleNamespace(cmd_res="")
        )
        self.assertFalse(json.loads(busy.cmd_res)["accepted"])
        self.assertEqual(calls, [])

        active["state"] = "ASSEMBLY_COMPLETED"
        accepted = await MockAssemblySequencer.on_external_request(
            sequencer, request, SimpleNamespace(cmd_res="")
        )
        self.assertTrue(json.loads(accepted.cmd_res)["accepted"])
        self.assertEqual(
            [call[0] for call in calls], ["assembly", "inspection", "transfer"]
        )

    async def test_pause_is_forwarded_without_changing_job_state(self):
        calls = []

        class Backend:
            async def set_paused(self, job_id, paused):
                calls.append((job_id, paused))

        sequencer = SimpleNamespace(
            active={"job_id": JOB_ID, "state": "STARTED"},
            recipe_version="assembly-r1",
            backend=Backend(),
            set_response=MockAssemblySequencer.set_response,
        )
        for command, paused in (("pause", True), ("resume", False)):
            response = await MockAssemblySequencer.on_external_request(
                sequencer,
                SimpleNamespace(cmd_str=json.dumps({
                    "command": command, "job_id": JOB_ID,
                })),
                SimpleNamespace(cmd_res=""),
            )
            self.assertTrue(json.loads(response.cmd_res)["accepted"])
            self.assertEqual(sequencer.active["state"], "STARTED")
            self.assertEqual(calls[-1], (JOB_ID, paused))

    async def test_backend_waits_for_conveyor_arrival(self):
        calls = []

        class Backend:
            async def start(self, command):
                calls.append(("start", command))

        active = {
            "job_id": JOB_ID,
            "state": "CONVEYOR_MOVING",
            "backend_command": {"command": "start"},
        }
        sequencer = SimpleNamespace(
            active=active,
            recipe_version="assembly-r1",
            backend=Backend(),
            set_response=MockAssemblySequencer.set_response,
        )
        self.assertEqual(calls, [])
        response = await MockAssemblySequencer.on_external_request(
            sequencer,
            SimpleNamespace(cmd_str=json.dumps({
                "command": "conveyor_arrived", "job_id": JOB_ID,
            })),
            SimpleNamespace(cmd_res=""),
        )

        self.assertTrue(json.loads(response.cmd_res)["accepted"])
        self.assertEqual(active["state"], "STARTED")
        self.assertEqual(calls, [("start", {"command": "start"})])

    async def test_conveyor_failure_finalizes_the_active_job(self):
        failures = []
        sequencer = SimpleNamespace(
            active={"job_id": JOB_ID, "state": "CONVEYOR_MOVING"},
            recipe_version="assembly-r1",
            set_response=MockAssemblySequencer.set_response,
            fail_active=lambda *args, **kwargs: failures.append((args, kwargs)),
        )
        response = await MockAssemblySequencer.on_external_request(
            sequencer,
            SimpleNamespace(cmd_str=json.dumps({
                "command": "conveyor_failed",
                "job_id": JOB_ID,
                "message": "belt timeout",
            })),
            SimpleNamespace(cmd_res=""),
        )

        self.assertTrue(json.loads(response.cmd_res)["accepted"])
        self.assertEqual(failures, [(("CONVEYOR_FAILED", "belt timeout"), {"immediate": True})])

    async def test_incomplete_pass_target_reuses_job_for_next_unit(self):
        calls = []

        class Writer:
            sync_state = "SYNCED"
            last_error = ""

            def flush(self, timeout_seconds):
                calls.append(("flush", timeout_seconds))
                return True

            def get_job(self, job_id):
                return {"completed_quantity": 1, "requested_quantity": 2}

            def claim(self, job_id, product_code, product_version, recipe_version):
                calls.append(("claim", job_id))
                return {
                    "job_id": job_id,
                    "unit_id": 23,
                    "requested_quantity": 2,
                }

        class Backend:
            async def start(self, next_command):
                calls.append(("start", next_command))

        active = {
            "job_id": JOB_ID,
            "unit_id": 22,
            "recipe_version": "assembly-r1",
            "backend_command": {"command": "start", "execution_plan": {}},
            "state": "PCB_PLACED",
            "placed_count": 1,
            "expected_step_count": 1,
            "held_step_order": 0,
            "held_part_id": "",
            "held_slot_code": "",
            "transfer_requested": True,
            "inspection_result": "PASS",
        }
        sequencer = SimpleNamespace(
            active=active,
            recipe_version="assembly-r1",
            db_writer=Writer(),
            backend=Backend(),
            fail_active=lambda *args, **kwargs: self.fail(str(args)),
        )
        feedback = SimpleNamespace(data=json.dumps({
            "job_id": JOB_ID,
            "state": "COMPLETED",
            "step_order": 0,
            "part_id": "",
            "slot_code": "",
            "error_code": "",
            "message": "",
        }))

        await MockAssemblySequencer.on_internal_feedback(sequencer, feedback)

        self.assertEqual(active["unit_id"], 23)
        self.assertEqual(active["state"], "STARTED")
        self.assertFalse(active["transfer_requested"])
        self.assertEqual([call[0] for call in calls], ["flush", "claim", "start"])


if __name__ == "__main__":
    unittest.main()
