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
from assembly_sequencer.mock_backend import MockBackend
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


class BackendFeedbackTest(unittest.TestCase):
    def test_matching_operation_feedback_completes_the_pending_call(self):
        completed = []

        class Future:
            def done(self):
                return False

            def set_result(self, value):
                completed.append(value)

        backend = SimpleNamespace(
            _operation_id="87654321-4321-8765-4321-876543218765",
            _operation_job_id=JOB_ID,
            _operation_future=Future(),
            _node=SimpleNamespace(),
        )
        accepted = MockBackend.accept_operation_feedback(backend, {
            "job_id": JOB_ID,
            "operation_id": backend._operation_id,
            "state": "COMPLETED",
            "message": "",
        })

        self.assertTrue(accepted)
        self.assertEqual(completed, [None])


class PendingJobTest(unittest.IsolatedAsyncioTestCase):
    async def test_db_job_starts_only_after_matching_observations(self):
        starts = []

        class Writer:
            def get_next_runnable_job(self, product_code, product_version, recipe_version):
                return {"job_id": JOB_ID}

        class Backend:
            def is_available(self):
                return True

        async def start_job(command, response):
            starts.append(command["job_id"])
            return MockAssemblySequencer.set_response(response, True, JOB_ID)

        sequencer = SimpleNamespace(
            active=None,
            recipe_version="assembly-r1",
            db_writer=Writer(),
            backend=Backend(),
            pending_observations={},
            start_job=start_job,
        )
        await MockAssemblySequencer.on_pending_job(sequencer)
        self.assertEqual(starts, [])

        sequencer.pending_observations[JOB_ID] = {"job_id": JOB_ID}
        await MockAssemblySequencer.on_pending_job(sequencer)
        self.assertEqual(starts, [JOB_ID])
        self.assertEqual(sequencer.pending_observations, {})


class TransferSequenceTest(unittest.IsolatedAsyncioTestCase):
    async def test_recipe_workflow_dispatches_semantic_operations_in_order(self):
        calls = []
        recipe = {
            "frame": "base_link",
            "joint_points": {
                "home": [0] * 6,
                "item_ready": [1] * 6,
                "assembly_ready": [2] * 6,
            },
            "motion": {"approach_dz_mm": 100, "retract_dz_mm": 120},
            "workflow": {
                "before_all": [
                    {"conveyor.move_to": "ASSEMBLY"},
                    {"vision.resolve_targets": "recipe_steps"},
                ],
                "per_step": [
                    {"robot.move_joint": "home"},
                    {"robot.move_joint": "item_ready"},
                    {"robot.pick": "current_part"},
                    {"robot.move_joint": "home"},
                    {"robot.move_joint": "assembly_ready"},
                    {"robot.place": "current_slot"},
                ],
            },
        }

        class Backend:
            async def move_joint(self, job_id, joint_point):
                calls.append(("move_joint", joint_point[0]))

            async def pick(self, job_id, step, frame, source, motion, gripper):
                calls.append(("pick", step["order"]))

            async def place(self, job_id, step, frame, target, motion, gripper):
                calls.append(("place", step["order"]))

        active = {
            "job_id": JOB_ID,
            "state": "STARTED",
            "resolved_steps": [{
                "step": {"order": 1, "part_id": "PART", "slot_code": "SLOT"},
                "source": {},
                "target": {},
                "gripper_grasp_opening_percent": 20,
                "gripper_release_opening_percent": 30,
            }],
        }
        sequencer = SimpleNamespace(
            active=active,
            recipe=recipe,
            backend=Backend(),
            db_writer=SimpleNamespace(sync_state="SYNCED"),
            arm_conveyor_timeout=lambda: calls.append(("arm",)),
            publish=lambda payload: calls.append(("publish", payload["state"])),
            fail_active=lambda *args: self.fail(str(args)),
        )

        await MockAssemblySequencer.run_assembly_workflow(sequencer, active)

        self.assertEqual(calls, [
            ("move_joint", 0),
            ("move_joint", 1),
            ("pick", 1),
            ("move_joint", 0),
            ("move_joint", 2),
            ("place", 1),
            ("arm",),
            ("publish", "ASSEMBLY_COMPLETED"),
        ])
        self.assertEqual(active["state"], "ASSEMBLY_COMPLETED")

    async def test_inspection_precedes_assembled_pcb_transfer(self):
        calls = []

        class Writer:
            def assembly_completed(self, unit_id):
                calls.append(("assembly", unit_id))

            def inspection_recorded(self, unit_id, result, defects, image_path):
                calls.append(("inspection", unit_id, result))

        class Backend:
            async def transfer_assembled_pcb(
                self, job_id, frame, assembled_pcb, motion, gripper
            ):
                calls.append(("transfer", job_id))

        active = {
            "job_id": JOB_ID,
            "unit_id": 22,
            "slot_codes": ["SLOT-01"],
            "inspection_result": "",
            "assembled_pcb": {
                "source": {"xyz_mm": [0, 0, 0], "xyzw": [0, 0, 0, 1]},
                "target": {"xyz_mm": [0, 0, 0], "xyzw": [0, 0, 0, 1]},
            },
        }
        sequencer = SimpleNamespace(
            active=active,
            recipe={
                "frame": "base_link",
                "motion": {},
                "gripper": {"assembled_pcb": {}},
                "workflow": {"after_all": [
                    {"conveyor.move_to": "INSPECTION"},
                    {"inspection.run": "assembled_pcb"},
                    {"robot.transfer": "assembled_pcb"},
                ]},
            },
            rng=random.Random(1),
            fail_probability=0.0,
            db_writer=Writer(),
            backend=Backend(),
            finish_active_unit=lambda current: calls.append(("finish",)),
            fail_active=lambda *args: self.fail(str(args)),
        )

        await MockAssemblySequencer.run_transfer_workflow(sequencer, active)

        self.assertEqual(
            [call[0] for call in calls],
            ["assembly", "inspection", "transfer", "finish"],
        )
        self.assertEqual(active["inspection_result"], "PASS")

    async def test_transfer_request_requires_completed_assembly(self):
        active = {
            "job_id": JOB_ID,
            "state": "PLACED",
            "transfer_requested": False,
        }
        sequencer = SimpleNamespace(
            active=active,
            recipe_version="assembly-r1",
            set_response=MockAssemblySequencer.set_response,
        )
        request = SimpleNamespace(cmd_str=json.dumps({
            "command": "transfer_assembled_pcb",
            "job_id": JOB_ID,
            "assembled_pcb": {
                "source": {"xyz_mm": [0, 0, 0], "xyzw": [0, 0, 0, 1]},
                "target": {"xyz_mm": [0, 0, 0], "xyzw": [0, 0, 0, 1]},
            },
        }))

        response = await MockAssemblySequencer.on_external_request(
            sequencer, request, SimpleNamespace(cmd_res="")
        )

        self.assertFalse(json.loads(response.cmd_res)["accepted"])

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
            async def start(self, job_id, recipe_version, expected_step_count):
                calls.append(("start", job_id, recipe_version, expected_step_count))

        async def workflow(active):
            return None

        class Executor:
            def create_task(self, coroutine):
                calls.append(("workflow",))
                coroutine.close()

        active = {
            "job_id": JOB_ID,
            "state": "CONVEYOR_MOVING",
            "expected_step_count": 1,
        }
        sequencer = SimpleNamespace(
            active=active,
            recipe_version="assembly-r1",
            backend=Backend(),
            db_writer=SimpleNamespace(sync_state="SYNCED"),
            set_response=MockAssemblySequencer.set_response,
            conveyor_deadline=1.0,
            publish=lambda payload: calls.append(("publish", payload["state"])),
            executor=Executor(),
            run_assembly_workflow=workflow,
        )
        response = await MockAssemblySequencer.conveyor_arrived(
            sequencer, {"job_id": JOB_ID}, SimpleNamespace(cmd_res="")
        )

        self.assertTrue(json.loads(response.cmd_res)["accepted"])
        self.assertEqual(active["state"], "STARTED")
        self.assertEqual(calls, [
            ("start", JOB_ID, "assembly-r1", 1),
            ("publish", "STARTED"),
            ("workflow",),
        ])

    async def test_conveyor_failure_finalizes_the_active_job(self):
        failures = []
        sequencer = SimpleNamespace(
            active={"job_id": JOB_ID, "state": "CONVEYOR_MOVING"},
            set_response=MockAssemblySequencer.set_response,
            fail_active=lambda *args, **kwargs: failures.append((args, kwargs)),
        )
        response = MockAssemblySequencer.conveyor_failed(
            sequencer,
            {"job_id": JOB_ID, "message": "belt timeout"},
            SimpleNamespace(cmd_res=""),
        )

        self.assertTrue(json.loads(response.cmd_res)["accepted"])
        self.assertEqual(failures, [(
            ("CONVEYOR_FAILED", "belt timeout"), {"immediate": True}
        )])

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
                return {"job_id": job_id, "unit_id": 23}

        active = {
            "job_id": JOB_ID,
            "unit_id": 22,
            "recipe_version": "assembly-r1",
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
            conveyor_deadline=None,
            arm_conveyor_timeout=lambda: calls.append(("arm",)),
            publish=lambda payload: calls.append(("publish", payload["state"])),
        )

        MockAssemblySequencer.finish_active_unit(sequencer, active)

        self.assertEqual(active["unit_id"], 23)
        self.assertEqual(active["state"], "CONVEYOR_MOVING")
        self.assertFalse(active["transfer_requested"])
        self.assertEqual(
            [call[0] for call in calls], ["flush", "claim", "arm", "publish"]
        )

    def test_missing_conveyor_signal_fails_the_active_job(self):
        failures = []
        sequencer = SimpleNamespace(
            active={"job_id": JOB_ID, "state": "CONVEYOR_MOVING"},
            conveyor_deadline=0.0,
            fail_active=lambda *args, **kwargs: failures.append((args, kwargs)),
        )

        MockAssemblySequencer.on_conveyor_timeout(sequencer)

        self.assertEqual(failures, [(
            ("CONVEYOR_FAILED",
             "conveyor completion was not reported within 60 seconds"),
            {"immediate": True},
        )])


if __name__ == "__main__":
    unittest.main()
