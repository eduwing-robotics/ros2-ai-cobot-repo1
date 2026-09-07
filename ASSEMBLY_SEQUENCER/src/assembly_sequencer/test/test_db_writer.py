"""Checks for DB retry and YAML-driven Mock workflow gates."""

import json
import random
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import psycopg


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assembly_sequencer.db import DbQueueFull, DbWriter
from assembly_sequencer.mock_backend import MockBackend
from assembly_sequencer.mock_node import MockAssemblySequencer
from assembly_sequencer.mock_contract import assembly_snapshot, load_recipe


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
            raise psycopg.OperationalError("temporary DB outage")

    def record_inspection(self, unit_id, result, defects, image_path=None):
        self.calls.append(("inspection", unit_id, result, defects, image_path))

    def finish_job(self, job_id, final_status):
        self.calls.append(("finish", job_id, final_status))


class DbWriterTest(unittest.TestCase):
    def test_permanent_errors_stop_fifo_and_preserve_first_error(self):
        for error in (
            psycopg.errors.InsufficientPrivilege("denied"),
            psycopg.errors.CheckViolation("bad status"),
            psycopg.errors.SyntaxError("bad SQL"),
            RuntimeError("unexpected failure"),
        ):
            with self.subTest(error=type(error).__name__):
                entered, release = threading.Event(), threading.Event()
                store = Mock()

                def fail(unit_id):
                    entered.set()
                    release.wait(1.0)
                    raise error

                store.complete_assembly_and_consume_stock.side_effect = fail
                writer = DbWriter(store=store)
                try:
                    writer.assembly_completed(22)
                    self.assertTrue(entered.wait(1.0))
                    writer.finish(JOB_ID, "FAILED")
                    release.set()
                    with self.assertRaisesRegex(RuntimeError, str(error)):
                        writer.flush(1.0)
                    first_error = writer.last_error
                    for operation in (
                        lambda: writer.assembly_completed(23),
                        lambda: writer.claim(JOB_ID, "P", "v1", "r1"),
                        lambda: writer.abort(JOB_ID),
                        lambda: writer.flush(1.0),
                    ):
                        with self.assertRaisesRegex(RuntimeError, str(error)):
                            operation()
                    self.assertFalse(writer.close(0.5))
                    self.assertEqual(writer.last_error, first_error)
                    self.assertEqual(writer.sync_state, "FAILED")
                    store.complete_assembly_and_consume_stock.assert_called_once()
                    store.finish_job.assert_not_called()
                    store.claim_job.assert_not_called()
                finally:
                    release.set()
                    writer.close(0.5)

    def test_transient_errors_retry_but_have_a_deadline(self):
        for error in (
            psycopg.OperationalError("connection lost"),
            psycopg.errors.DeadlockDetected("deadlock"),
            psycopg.errors.SerializationFailure("serialization"),
        ):
            with self.subTest(error=type(error).__name__):
                store = Mock()
                store.complete_assembly_and_consume_stock.side_effect = [error, None]
                writer = DbWriter(store=store, retry_initial_seconds=0.001)
                try:
                    writer.assembly_completed(22)
                    self.assertTrue(writer.flush(1.0))
                    self.assertEqual(store.complete_assembly_and_consume_stock.call_count, 2)
                finally:
                    writer.close(0.5)

        store = Mock()
        store.complete_assembly_and_consume_stock.side_effect = psycopg.OperationalError("offline")
        with patch("assembly_sequencer.db.writer.DB_SYNC_TIMEOUT_SECONDS", 0.03):
            writer = DbWriter(store=store, retry_initial_seconds=0.001,
                              retry_max_seconds=0.002)
            try:
                writer.assembly_completed(22)
                self.assertTrue(writer._stop.wait(1.0))
                with self.assertRaisesRegex(RuntimeError, "deadline exceeded"):
                    writer.flush(1.0)
                self.assertGreater(store.complete_assembly_and_consume_stock.call_count, 1)
            finally:
                writer.close(0.5)

    def test_flush_timeout_stays_failed_after_late_commit(self):
        entered, release = threading.Event(), threading.Event()
        store = Mock()

        def commit_late(unit_id):
            entered.set()
            release.wait(1.0)

        store.complete_assembly_and_consume_stock.side_effect = commit_late
        writer = DbWriter(store=store)
        try:
            writer.assembly_completed(22)
            self.assertTrue(entered.wait(1.0))
            writer.finish(JOB_ID, "COMPLETED")
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                writer.flush(0.01)
            release.set()
            self.assertFalse(writer.close(0.5))
            self.assertEqual(writer.sync_state, "FAILED")
            store.finish_job.assert_not_called()
        finally:
            release.set()
            writer.close(0.5)

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
    async def test_failed_writer_blocks_polling_and_failure_finalization(self):
        writer = Mock(sync_state="FAILED", last_error="permission denied")
        sequencer = SimpleNamespace(
            active=None, db_writer=writer, backend=Mock(),
            get_logger=lambda: Mock(),
        )
        await MockAssemblySequencer.on_pending_job(sequencer)
        error = MockAssemblySequencer.fail_job(sequencer, JOB_ID)
        self.assertIn("restart recovery required", str(error))
        self.assertEqual(writer.mock_calls, [])
        self.assertEqual(sequencer.backend.mock_calls, [])

        writer.sync_state = "PENDING"
        await MockAssemblySequencer.on_pending_job(sequencer)
        self.assertEqual(writer.mock_calls, [])
        writer.sync_state = "SYNCED"
        self.assertIsNone(MockAssemblySequencer.fail_job(sequencer, JOB_ID))
        writer.finish.assert_called_once_with(JOB_ID, "FAILED")
        writer.flush.assert_called_once_with(5.0)

    async def test_slot_mapping_and_rejection_before_db_or_equipment(self):
        recipe = load_recipe(str(Path(__file__).resolve().parents[1]
                                 / "config/recipes/assembly-r1.yaml"))
        pose = {"xyz_mm": [0, 0, 0], "xyzw": [0, 0, 0, 1]}
        observations = [
            dict(order=index, part_id=step["part_id"], slot_code=step["slot_code"],
                 source=dict(pose, xyz_mm=[index, 0, 0]),
                 target=dict(pose, xyz_mm=[0, index, 0]))
            for index, step in enumerate(reversed(recipe["steps"]), 1)
        ]
        command = dict(command="observations", job_id=JOB_ID,
                       recipe_version=recipe["recipe_version"], observations=observations)
        sequencer = SimpleNamespace(
            recipe=recipe, recipe_version=recipe["recipe_version"], active=None,
            pending_observations={}, set_response=MockAssemblySequencer.set_response,
            db_writer=Mock(), backend=Mock(), executor=Mock(),
        )
        sequencer.db_writer.get_job.return_value = {"job_status": "PENDING"}
        response = await MockAssemblySequencer.on_external_request(
            sequencer, SimpleNamespace(cmd_str=json.dumps(command)), SimpleNamespace())
        self.assertTrue(json.loads(response.cmd_res)["accepted"])
        resolved = sequencer.pending_observations[JOB_ID]["resolved_steps"]
        self.assertEqual([row["step"] for row in resolved], recipe["steps"])
        self.assertEqual(resolved[0]["source"]["xyz_mm"], [len(observations), 0, 0])
        self.assertEqual(resolved[0]["target"]["xyz_mm"], [0, len(observations), 0])
        sequencer.db_writer.claim.assert_not_called()
        self.assertEqual(sequencer.backend.mock_calls, [])

        for invalid in ("missing", "extra", "duplicate", "unknown", "wrong_part", "legacy", "blank"):
            with self.subTest(invalid=invalid):
                bad = json.loads(json.dumps(command))
                rows = bad["observations"]
                if invalid == "missing":
                    rows.pop()
                elif invalid == "extra":
                    rows.append(dict(rows[0], order=len(rows) + 1, slot_code="EXTRA-SLOT"))
                elif invalid == "duplicate":
                    rows[0]["slot_code"] = rows[1]["slot_code"]
                elif invalid == "unknown":
                    rows[0]["slot_code"] = "UNKNOWN-SLOT"
                elif invalid == "wrong_part":
                    rows[0]["part_id"] = "WRONG-PART"
                elif invalid == "legacy":
                    del rows[0]["slot_code"]
                else:
                    rows[0]["slot_code"] = " "
                sequencer.pending_observations.clear()
                sequencer.db_writer.reset_mock()
                response = await MockAssemblySequencer.on_external_request(
                    sequencer, SimpleNamespace(cmd_str=json.dumps(bad)), SimpleNamespace())
                outcome = json.loads(response.cmd_res)
                self.assertFalse(outcome["accepted"])
                self.assertEqual(outcome["error_code"], "INVALID_REQUEST")
                self.assertEqual(sequencer.db_writer.mock_calls, [])
                self.assertEqual(sequencer.backend.mock_calls, [])
                self.assertEqual(sequencer.executor.mock_calls, [])
                self.assertEqual(sequencer.pending_observations, {})

    def test_public_feedback_keeps_unit_identity_after_terminal_cleanup(self):
        publisher = Mock()
        sequencer = SimpleNamespace(active=dict(job_id=JOB_ID, unit_id=22),
                                    terminal_snapshot=None, external_publisher=publisher)
        payload = dict(job_id=JOB_ID, state="CONVEYOR_MOVING")
        MockAssemblySequencer.publish(sequencer, payload)
        self.assertEqual(json.loads(publisher.publish.call_args.args[0].data)["unit_id"], 22)
        self.assertNotIn("unit_id", payload)
        sequencer.terminal_snapshot = sequencer.active
        sequencer.active = None
        MockAssemblySequencer.publish(sequencer, dict(job_id=JOB_ID, state="COMPLETED"))
        self.assertEqual(json.loads(publisher.publish.call_args.args[0].data)["unit_id"], 22)
        MockAssemblySequencer.publish(sequencer, dict(job_id="different", state="FAILED"))
        self.assertEqual(json.loads(publisher.publish.call_args.args[0].data)["unit_id"], 0)

    def test_snapshot_contains_only_current_unit_placed_slots(self):
        active = dict(job_id=JOB_ID, unit_id=22, recipe_version="assembly-r1",
                      placed_count=1, expected_step_count=2,
                      slot_codes=["HBM-02", "HBM-01"], held_step_order=2,
                      held_part_id="HBM", held_slot_code="HBM-01")
        snapshot = assembly_snapshot(active, "PAUSED")
        self.assertEqual(snapshot["placed_slot_codes"], ["HBM-02"])
        self.assertEqual(snapshot["held_slot_code"], "HBM-01")
        active["placed_count"] = 0
        self.assertEqual(assembly_snapshot(active, "STARTED")["placed_slot_codes"], [])
        self.assertEqual(snapshot["placed_slot_codes"], ["HBM-02"])
        self.assertEqual(assembly_snapshot(active, "COMPLETED")["placed_slot_codes"],
                         ["HBM-02", "HBM-01"])

    async def test_db_job_starts_only_after_matching_observations(self):
        starts = []

        class Writer:
            sync_state = "SYNCED"

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
    async def test_recipe_workflow_waits_for_conveyor_then_follows_yaml(self):
        calls = []
        resolved_steps = [{
            "step": {"order": 1, "part_id": "PART", "slot_code": "SLOT"},
            "source": {},
            "target": {},
            "gripper_grasp_opening_percent": 20,
            "gripper_release_opening_percent": 30,
        }]
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
            async def start(self, job_id, recipe_version, expected_step_count):
                calls.append(("start", expected_step_count))

            async def move_joint(self, job_id, joint_point):
                calls.append(("move_joint", joint_point[0]))

            async def pick(self, job_id, step, frame, source, motion, gripper):
                calls.append(("pick", step["order"]))

            async def place(self, job_id, step, frame, target, motion, gripper):
                calls.append(("place", step["order"]))

        async def after_all(active):
            calls.append(("after_all",))

        active = {
            "job_id": JOB_ID,
            "state": "STARTED",
            "resolved_steps": resolved_steps,
            "before_action_index": 0,
            "backend_started": False,
            "conveyor_confirmed": False,
            "expected_step_count": 1,
        }
        sequencer = SimpleNamespace(
            active=active,
            recipe=recipe,
            recipe_version="assembly-r1",
            backend=Backend(),
            db_writer=SimpleNamespace(sync_state="SYNCED"),
            arm_conveyor_timeout=lambda: calls.append(("arm",)),
            publish=lambda payload: calls.append(("publish", payload["state"])),
            run_transfer_workflow=after_all,
            fail_active=lambda *args, **kwargs: self.fail(str((args, kwargs))),
        )

        await MockAssemblySequencer.run_assembly_workflow(sequencer, active)
        self.assertEqual(calls, [
            ("arm",),
            ("publish", "CONVEYOR_MOVING"),
        ])
        active["conveyor_confirmed"] = True
        await MockAssemblySequencer.run_assembly_workflow(sequencer, active)

        self.assertEqual(calls, [
            ("arm",),
            ("publish", "CONVEYOR_MOVING"),
            ("start", 1),
            ("publish", "STARTED"),
            ("move_joint", 0),
            ("move_joint", 1),
            ("pick", 1),
            ("move_joint", 0),
            ("move_joint", 2),
            ("place", 1),
            ("after_all",),
        ])
        self.assertEqual(active["state"], "STARTED")

    async def test_before_all_action_order_comes_from_recipe(self):
        calls = []
        active = {
            "job_id": JOB_ID,
            "state": "STARTED",
            "observations": [{"order": 1}],
            "resolved_steps": [],
            "before_action_index": 0,
            "backend_started": False,
            "conveyor_confirmed": False,
        }
        sequencer = SimpleNamespace(
            active=active,
            recipe={"workflow": {"before_all": [
                {"vision.resolve_targets": "recipe_steps"},
                {"conveyor.move_to": "ASSEMBLY"},
            ]}},
            db_writer=SimpleNamespace(sync_state="SYNCED"),
            arm_conveyor_timeout=lambda: calls.append(("arm",)),
            publish=lambda payload: calls.append(("publish", payload["state"])),
            fail_active=lambda *args, **kwargs: self.fail(str((args, kwargs))),
        )

        await MockAssemblySequencer.run_assembly_workflow(sequencer, active)

        self.assertEqual(calls, [
            ("arm",),
            ("publish", "CONVEYOR_MOVING"),
        ])
        self.assertEqual(active["before_action_index"], 2)

    async def test_inspection_precedes_assembled_pcb_transfer(self):
        calls = []

        class Writer:
            sync_state = "SYNCED"

            def flush(self, timeout_seconds):
                calls.append(("flush",))
                return True

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
            "state": "STARTED",
            "after_action_index": 0,
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
            arm_conveyor_timeout=lambda: calls.append(("arm",)),
            publish=lambda payload: calls.append(("publish", payload["state"])),
            finish_active_unit=lambda current: calls.append(("finish",)),
            fail_active=lambda *args: self.fail(str(args)),
        )

        await MockAssemblySequencer.run_transfer_workflow(sequencer, active)
        self.assertEqual(calls, [
            ("arm",),
            ("publish", "ASSEMBLY_COMPLETED"),
        ])

        await MockAssemblySequencer.run_transfer_workflow(sequencer, active)
        self.assertEqual(
            [call[0] for call in calls],
            ["arm", "publish", "assembly", "inspection", "flush", "transfer", "finish"],
        )
        self.assertEqual(active["inspection_result"], "PASS")

        calls.clear()
        active["after_action_index"] = 1
        sequencer.db_writer.flush = Mock(side_effect=RuntimeError("DB failed"))
        sequencer.fail_active = Mock()
        await MockAssemblySequencer.run_transfer_workflow(sequencer, active)
        self.assertEqual([call[0] for call in calls], ["assembly", "inspection"])
        self.assertEqual(sequencer.fail_active.call_args.args[0], "DB_ERROR")

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

    async def test_conveyor_arrival_resumes_yaml_worker_once(self):
        calls = []

        async def workflow(active):
            return None

        class Executor:
            def create_task(self, coroutine):
                calls.append(("workflow",))
                coroutine.close()

        active = {
            "job_id": JOB_ID,
            "state": "CONVEYOR_MOVING",
            "conveyor_confirmed": False,
        }
        sequencer = SimpleNamespace(
            active=active,
            set_response=MockAssemblySequencer.set_response,
            conveyor_deadline=1.0,
            executor=Executor(),
            run_assembly_workflow=workflow,
        )
        first = await MockAssemblySequencer.conveyor_arrived(
            sequencer, {"job_id": JOB_ID}, SimpleNamespace(cmd_res="")
        )
        second = await MockAssemblySequencer.conveyor_arrived(
            sequencer, {"job_id": JOB_ID}, SimpleNamespace(cmd_res="")
        )

        self.assertTrue(json.loads(first.cmd_res)["accepted"])
        self.assertTrue(json.loads(second.cmd_res)["accepted"])
        self.assertTrue(active["conveyor_confirmed"])
        self.assertEqual(calls, [("workflow",)])

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

    async def test_incomplete_pass_target_restarts_recipe_for_next_unit(self):
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

        async def workflow(active):
            return None

        class Executor:
            def create_task(self, coroutine):
                calls.append(("workflow",))
                coroutine.close()

        active = {
            "job_id": JOB_ID,
            "unit_id": 22,
            "recipe_version": "assembly-r1",
            "state": "PCB_PLACED",
            "resolved_steps": [{"step": {"slot_code": "SLOT-01"}}],
            "placed_count": 1,
            "expected_step_count": 1,
            "held_step_order": 0,
            "held_part_id": "",
            "held_slot_code": "",
            "transfer_requested": True,
            "inspection_result": "PASS",
            "assembled_pcb": {},
        }
        sequencer = SimpleNamespace(
            active=active,
            recipe_version="assembly-r1",
            db_writer=Writer(),
            conveyor_deadline=None,
            executor=Executor(),
            run_assembly_workflow=workflow,
        )

        MockAssemblySequencer.finish_active_unit(sequencer, active)

        self.assertEqual(active["unit_id"], 23)
        self.assertEqual(active["state"], "STARTED")
        self.assertEqual(active["before_action_index"], 0)
        self.assertEqual(active["after_action_index"], 0)
        self.assertEqual(active["resolved_steps"], [{"step": {"slot_code": "SLOT-01"}}])
        self.assertFalse(active["transfer_requested"])
        self.assertNotIn("assembled_pcb", active)
        self.assertEqual(
            [call[0] for call in calls], ["flush", "claim", "workflow"]
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
