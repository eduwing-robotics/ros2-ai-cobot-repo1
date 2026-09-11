"""Checks for DB retry and YAML-driven Mock workflow gates."""

import asyncio
from copy import deepcopy
import os
import json
import random
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace, MethodType
from unittest.mock import AsyncMock, Mock, patch, mock_open, PropertyMock

import psycopg


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assembly_sequencer.db import DbQueueFull, DbWriter
from assembly_sequencer.mock_backend import MockBackend, choose_inspection
from assembly_sequencer.sequencer_node import AssemblySequencer
from assembly_sequencer.recipe_contract import assembly_snapshot, load_recipe, resolve_observations, parse_command, validate_recipe
from assembly_sequencer.db import production_store as store
from assembly_sequencer.real_backend import RealBackend
from assembly_sequencer import api_contracts


JOB_ID = "12345678-1234-5678-1234-567812345678"
OPERATION_ID = "87654321-4321-8765-4321-876543218765"


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

    def complete_unit(self, unit_id):
        self.calls.append(("unit_completed", unit_id))

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
        writer.unit_completed(work["unit_id"])
        writer.finish(work["job_id"], "COMPLETED")

        self.assertTrue(writer.flush(1.0))
        self.assertEqual(
            [call[0] for call in store.calls],
            ["claim", "assembly", "assembly", "inspection", "unit_completed", "finish"],
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
    def test_pause_preserves_remaining_operation_timeout(self):
        node = Mock(executor=None)
        backend = MockBackend(node, Mock())
        backend._require_accepted = AsyncMock()
        with patch("assembly_sequencer.mock_backend.time.monotonic", return_value=100.0) as clock:
            operation = backend.move_joint(JOB_ID, [0] * 6)
            try:
                future = operation.send(None)
                check_timeout = node.create_timer.call_args.args[1]
                clock.return_value = 200.0
                asyncio.run(backend.set_paused(JOB_ID, True))
                clock.return_value = 1500.0
                asyncio.run(backend.set_paused(JOB_ID, True))
                check_timeout()
                self.assertFalse(future.cancelled(), "Pause must outlast the original 600-second deadline.")
                asyncio.run(backend.set_paused(JOB_ID, False))
                clock.return_value = 1600.0
                asyncio.run(backend.set_paused(JOB_ID, False))
                asyncio.run(backend.set_paused(JOB_ID, True))
                clock.return_value = 3000.0
                check_timeout()
                self.assertFalse(future.cancelled())
                asyncio.run(backend.set_paused(JOB_ID, False))
                clock.return_value = 3399.0
                check_timeout()
                self.assertFalse(future.cancelled())
                clock.return_value = 3400.0
                check_timeout()
                self.assertTrue(future.cancelled(), "Resume must retain only the unspent running time.")
                with self.assertRaisesRegex(RuntimeError, "operation timed out"):
                    operation.send(None)
                self.assertIsNone(backend._operation_future)
                node.destroy_timer.assert_called_once()
            finally:
                operation.close()

    def test_rejected_pause_keeps_timeout_and_completed_operation_cleans_up(self):
        for complete in (False, True):
            with self.subTest(complete=complete), patch(
                "assembly_sequencer.mock_backend.time.monotonic", return_value=100.0
            ) as clock:
                node = Mock(executor=None)
                backend = MockBackend(node, Mock())
                backend._require_accepted = AsyncMock()
                operation = backend.move_joint(JOB_ID, [0] * 6)
                try:
                    future = operation.send(None)
                    check_timeout = node.create_timer.call_args.args[1]
                    backend._require_accepted.side_effect = RuntimeError("pause rejected")
                    with self.assertRaisesRegex(RuntimeError, "pause rejected"):
                        asyncio.run(backend.set_paused(JOB_ID, True))
                    if complete:
                        backend.accept_operation_feedback({
                            "job_id": JOB_ID, "operation_id": backend._operation_id,
                            "state": "COMPLETED", "message": "",
                        })
                        with self.assertRaises(StopIteration):
                            operation.send(None)
                        clock.return_value = 1000.0
                        check_timeout()
                        self.assertTrue(future.done())
                        self.assertFalse(future.cancelled())
                    else:
                        clock.return_value = 700.0
                        check_timeout()
                        with self.assertRaisesRegex(RuntimeError, "operation timed out"):
                            operation.send(None)
                    self.assertIsNone(backend._operation_future)
                    node.destroy_timer.assert_called_once()
                finally:
                    operation.close()

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
    async def test_mode_rejection_precedes_recipe_database_and_backend(self):
        sequencer = SimpleNamespace(runtime_mode="mock", get_logger=lambda: Mock(),
                                    set_response=AssemblySequencer.set_response)
        for payload in ('real\n{}', '{}', ''):
            response = await AssemblySequencer.on_external_request(
                sequencer, SimpleNamespace(cmd_str=payload), SimpleNamespace())
            self.assertEqual(json.loads(response.cmd_res)["error_code"], "MODE_MISMATCH")


    async def test_failed_writer_blocks_polling_and_failure_finalization(self):
        writer = Mock(sync_state="FAILED", last_error="permission denied")
        sequencer = SimpleNamespace(runtime_mode="mock",
            active=None, db_writer=writer, backend=Mock(),
            get_logger=lambda: Mock(),
        )
        await AssemblySequencer.on_pending_job(sequencer)
        error = AssemblySequencer.fail_job(sequencer, JOB_ID)
        self.assertIn("restart recovery required", str(error))
        self.assertEqual(writer.mock_calls, [])
        self.assertEqual(sequencer.backend.mock_calls, [])

        writer.sync_state = "PENDING"
        await AssemblySequencer.on_pending_job(sequencer)
        self.assertEqual(writer.mock_calls, [])
        writer.sync_state = "SYNCED"
        self.assertIsNone(AssemblySequencer.fail_job(sequencer, JOB_ID))
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
        sequencer = SimpleNamespace(runtime_mode="mock",
            recipe=recipe, recipe_version=recipe["recipe_version"], active=None,
            pending_requests={}, set_response=AssemblySequencer.set_response,
            db_writer=Mock(), backend=Mock(), executor=Mock(),
        )
        sequencer.db_writer.get_job.return_value = {"job_status": "PENDING"}
        response = await AssemblySequencer.on_external_request(
            sequencer, SimpleNamespace(cmd_str="mock\n" + json.dumps(command)), SimpleNamespace())
        self.assertTrue(json.loads(response.cmd_res)["accepted"])
        resolved = sequencer.pending_requests[JOB_ID]["resolved_steps"]
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
                sequencer.pending_requests.clear()
                sequencer.db_writer.reset_mock()
                response = await AssemblySequencer.on_external_request(
                    sequencer, SimpleNamespace(cmd_str="mock\n" + json.dumps(bad)), SimpleNamespace())
                outcome = json.loads(response.cmd_res)
                self.assertFalse(outcome["accepted"])
                self.assertEqual(outcome["error_code"], "INVALID_REQUEST")
                self.assertEqual(sequencer.db_writer.mock_calls, [])
                self.assertEqual(sequencer.backend.mock_calls, [])
                self.assertEqual(sequencer.executor.mock_calls, [])
                self.assertEqual(sequencer.pending_requests, {})

    def test_public_feedback_keeps_unit_identity_after_terminal_cleanup(self):
        publisher = Mock()
        sequencer = SimpleNamespace(runtime_mode="mock", active=dict(job_id=JOB_ID, unit_id=22),
                                    terminal_snapshot=None, external_publisher=publisher)
        payload = dict(job_id=JOB_ID, state="CONVEYOR_MOVING")
        AssemblySequencer.publish(sequencer, payload)
        self.assertEqual(json.loads(publisher.publish.call_args.args[0].data)["unit_id"], 22)
        self.assertNotIn("unit_id", payload)
        sequencer.terminal_snapshot = sequencer.active
        sequencer.active = None
        AssemblySequencer.publish(sequencer, dict(job_id=JOB_ID, state="COMPLETED"))
        self.assertEqual(json.loads(publisher.publish.call_args.args[0].data)["unit_id"], 22)
        AssemblySequencer.publish(sequencer, dict(job_id="different", state="FAILED"))
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

            def get_next_runnable_job(self, product_code, product_version, recipe_version, ready_job_ids=None):
                return {"job_id": JOB_ID}

        class Backend:
            def is_available(self):
                return True

        async def start_job(command, response):
            starts.append(command["job_id"])
            return AssemblySequencer.set_response(response, True, JOB_ID)

        sequencer = SimpleNamespace(runtime_mode="mock",
            active=None,
            recipe_version="assembly-r1",
            db_writer=Writer(),
            backend=Backend(),
            pending_requests={},
            start_job=start_job,
        )
        await AssemblySequencer.on_pending_job(sequencer)
        self.assertEqual(starts, [])

        sequencer.pending_requests[JOB_ID] = {"job_id": JOB_ID}
        await AssemblySequencer.on_pending_job(sequencer)
        self.assertEqual(starts, [JOB_ID])
        self.assertEqual(sequencer.pending_requests, {})


class TransferSequenceTest(unittest.IsolatedAsyncioTestCase):
    def fixture(self):
        recipe = load_recipe(str(Path(__file__).resolve().parents[1] / "config/recipes/assembly-r1.yaml"))
        pose = {"xyz_mm": [100, 200, 300], "xyzw": [0, 0, 0, 1]}
        observations = [dict(step, source=pose, target=pose) for step in recipe["steps"]]
        active = dict(job_id=JOB_ID, unit_id=22, recipe_version=recipe["recipe_version"],
                      state="STARTED", observations=observations,
                      resolved_steps=resolve_observations(recipe, observations),
                      before_action_index=0, after_action_index=0, backend_started=False,
                      conveyor_confirmed=False, transfer_requested=False, conveyor_operation_id=OPERATION_ID,
                      expected_step_count=25, placed_count=0, held_step_order=0,
                      held_part_id="", held_slot_code="", inspection_result="",
                      slot_codes=[step["slot_code"] for step in recipe["steps"]])
        backend = Mock()
        for name in ("start", "move_joint", "pick", "place", "move_conveyor", "transfer_assembled_pcb"):
            setattr(backend, name, AsyncMock())
        backend.resolve_targets = AsyncMock(return_value=observations)
        backend.inspect_unit = AsyncMock(return_value={"result": "PASS", "defects": [], "image_path": "test.png"})
        writer = Mock(sync_state="SYNCED")
        sequencer = SimpleNamespace(runtime_mode="mock", active=active, recipe=recipe,
                                    recipe_version=recipe["recipe_version"], backend=backend,
                                    db_writer=writer, publish=Mock(), fail_active=Mock(),
                                    finish_active_unit=Mock(), set_response=AssemblySequencer.set_response)
        sequencer.conveyor_arrived = MethodType(AssemblySequencer.conveyor_arrived, sequencer)
        sequencer.conveyor_failed = MethodType(AssemblySequencer.conveyor_failed, sequencer)
        sequencer.run_transfer_workflow = MethodType(AssemblySequencer.run_transfer_workflow, sequencer)
        return sequencer, active

    async def test_recipe_workflow_waits_for_conveyor_then_follows_yaml(self):
        sequencer, active = self.fixture()
        arrived = asyncio.Event()
        async def conveyor(job, station, **kwargs):
            kwargs["on_ready"]()
            if station == "ASSEMBLY":
                await arrived.wait()
        sequencer.backend.move_conveyor.side_effect = conveyor
        task = asyncio.create_task(AssemblySequencer.run_assembly_workflow(sequencer, active))
        await asyncio.sleep(0)
        sequencer.backend.start.assert_not_awaited()
        sequencer.backend.pick.assert_not_awaited()
        self.assertFalse(task.done())
        arrived.set()
        await task
        sequencer.fail_active.assert_not_called()
        moves = [(call[0], call.args[1] if call[0] == "move_joint" else None)
                 for call in sequencer.backend.mock_calls if call[0] in {"move_joint", "pick", "place"}]
        points = sequencer.recipe["joint_points"]
        self.assertEqual(moves[:6], [("move_joint", points["home"]), ("move_joint", points["item_ready"]),
                                    ("pick", None), ("move_joint", points["home"]),
                                    ("move_joint", points["assembly_ready"]), ("place", None)])
        self.assertEqual(len(moves), 25 * 6)
        self.assertNotIn("pregrasp_opening_percent", sequencer.backend.pick.call_args.args[-1])
        sequencer.finish_active_unit.assert_called_once_with(active)

    async def test_real_cannot_enter_mock_motion_or_transfer_workflows(self):
        sequencer, active = self.fixture()
        sequencer.runtime_mode = "real"
        sequencer.recipe = None
        for run in (AssemblySequencer.run_assembly_workflow, AssemblySequencer.run_transfer_workflow):
            with self.assertRaisesRegex(RuntimeError, "Mock-only"):
                await run(sequencer, active)
        self.assertEqual(sequencer.backend.mock_calls, [])
        sequencer.publish.assert_not_called()
        sequencer.db_writer.claim.assert_not_called()

    def test_preopen_is_required_finite_and_in_range_for_parts(self):
        sequencer, _ = self.fixture()
        for value in (None, True, -1, 101, float("nan")):
            recipe = deepcopy(sequencer.recipe)
            profile = recipe["gripper"]["parts"]["HBM"]
            if value is None:
                del profile["pregrasp_opening_percent"]
            else:
                profile["pregrasp_opening_percent"] = value
            with self.assertRaises(ValueError):
                validate_recipe(recipe)
        self.assertNotIn("pregrasp_opening_percent", sequencer.recipe["gripper"]["assembled_pcb"])

    def test_invalid_workflow_orders_are_rejected(self):
        sequencer, _ = self.fixture()
        validate_recipe(sequencer.recipe)
        for section, left, right in (("before_all", 0, 1), ("per_step", 2, 5), ("after_all", 0, 1)):
            recipe = deepcopy(sequencer.recipe)
            actions = recipe["workflow"][section]
            actions[left], actions[right] = actions[right], actions[left]
            with self.subTest(section=section), self.assertRaisesRegex(ValueError, "invalid action order"):
                validate_recipe(recipe)
        for section in sequencer.recipe["workflow"]:
            for mutation in ("missing", "duplicate"):
                recipe = deepcopy(sequencer.recipe)
                actions = recipe["workflow"][section]
                if mutation == "missing":
                    actions.pop()
                else:
                    actions.append(actions[0])
                with self.subTest(section=section, mutation=mutation), self.assertRaises(ValueError):
                    validate_recipe(recipe)

    def test_invalid_recipe_stops_startup_before_equipment_and_database(self):
        sequencer, _ = self.fixture()
        recipe = deepcopy(sequencer.recipe)
        recipe["workflow"]["per_step"][2], recipe["workflow"]["per_step"][5] = (
            recipe["workflow"]["per_step"][5], recipe["workflow"]["per_step"][2])
        with patch("rclpy.node.Node.__init__", return_value=None), \
             patch.object(AssemblySequencer, "context", new_callable=PropertyMock) as context, \
             patch.object(AssemblySequencer, "declare_parameter", return_value=SimpleNamespace(value="assembly-r1.yaml")), \
             patch.object(AssemblySequencer, "create_client") as client, \
             patch("assembly_sequencer.sequencer_node.DbWriter") as writer, \
             patch("pathlib.Path.open", mock_open(read_data="unused")), \
             patch("yaml.safe_load", return_value=recipe):
            context.return_value.get_domain_id.return_value = 42
            with patch.dict(os.environ, {"ASSEMBLY_SEQUENCER_MODE": "mock"}), self.assertRaisesRegex(ValueError, "invalid action order"):
                AssemblySequencer()
            client.assert_not_called()
            writer.assert_not_called()

    async def test_inspection_precedes_transfer_and_db_failure_blocks_it(self):
        sequencer, active = self.fixture()
        inspection_arrived = asyncio.Event()
        sequencer.backend.move_conveyor.side_effect = lambda *args, **kwargs: None
        async def wait_arrival(*args, **kwargs):
            kwargs["on_ready"]()
            await inspection_arrived.wait()
        sequencer.backend.move_conveyor.side_effect = wait_arrival
        task = asyncio.create_task(sequencer.run_transfer_workflow(active))
        await asyncio.sleep(0)
        sequencer.backend.inspect_unit.assert_not_awaited()
        sequencer.backend.transfer_assembled_pcb.assert_not_awaited()
        inspection_arrived.set()
        await task
        sequencer.db_writer.inspection_recorded.assert_called_once_with(22, result="PASS", defects=[], image_path="test.png")
        sequencer.backend.transfer_assembled_pcb.assert_awaited_once()
        self.assertEqual(active["inspection_result"], "PASS")
        sequencer, active = self.fixture()
        sequencer.db_writer.flush.side_effect = RuntimeError("DB failed")
        await sequencer.run_transfer_workflow(active)
        self.assertEqual(sequencer.fail_active.call_args.args[0], "DB_ERROR")
        sequencer.backend.transfer_assembled_pcb.assert_not_awaited()
        sequencer.finish_active_unit.assert_not_called()

    async def test_unknown_inspection_holds_unit_without_transfer_or_completion(self):
        sequencer, active = self.fixture()
        sequencer.backend.inspect_unit.return_value = {"result": "UNKNOWN", "defects": None,
                                                     "image_path": None, "inspection": {"id": "evidence"}}
        await sequencer.run_transfer_workflow(active)
        self.assertEqual(active["state"], "PAUSED")
        self.assertTrue(active["inspection_hold"])
        sequencer.db_writer.flush.assert_called_once()
        sequencer.fail_active.assert_not_called()
        sequencer.finish_active_unit.assert_not_called()
        sequencer.backend.transfer_assembled_pcb.assert_not_awaited()
        response = await AssemblySequencer.on_external_request(sequencer,
            SimpleNamespace(cmd_str="mock\n" + json.dumps({"command": "resume", "job_id": JOB_ID})), SimpleNamespace())
        self.assertEqual(json.loads(response.cmd_res)["error_code"], "BUSY")
        sequencer.backend.set_paused.assert_not_called()

    async def test_transfer_request_requires_completed_assembly(self):
        sequencer, active = self.fixture()
        active["state"] = "PLACED"
        pose = {"xyz_mm": [0, 0, 0], "xyzw": [0, 0, 0, 1]}
        response = await AssemblySequencer.on_external_request(sequencer,
            SimpleNamespace(cmd_str="mock\n" + json.dumps({"command":"transfer_assembled_pcb", "job_id":JOB_ID,
                                                          "unit_id":22, "operation_id":OPERATION_ID,
                                                          "assembled_pcb":{"source":pose,"target":pose}})), SimpleNamespace())
        self.assertEqual(json.loads(response.cmd_res)["error_code"], "BUSY")
        sequencer.backend.confirm_conveyor.assert_not_called()

    async def test_pause_is_forwarded_without_changing_job_state(self):
        sequencer, active = self.fixture()
        sequencer.backend.set_paused = AsyncMock()
        for command, paused in (("pause", True), ("resume", False)):
            response = await AssemblySequencer.on_external_request(sequencer,
                SimpleNamespace(cmd_str="mock\n" + json.dumps({"command":command,"job_id":JOB_ID})), SimpleNamespace())
            self.assertTrue(json.loads(response.cmd_res)["accepted"])
            sequencer.backend.set_paused.assert_awaited_with(JOB_ID, paused)
            self.assertEqual(active["state"], "STARTED")
        sequencer.db_writer.assert_not_called()

    async def test_conveyor_arrival_completes_wait_once(self):
        sequencer, active = self.fixture()
        active["state"] = "CONVEYOR_MOVING"
        for _ in range(2):
            response = await AssemblySequencer.conveyor_arrived(sequencer, {"job_id":JOB_ID,"unit_id":22,"operation_id":OPERATION_ID}, SimpleNamespace())
            self.assertTrue(json.loads(response.cmd_res)["accepted"])
        sequencer.backend.confirm_conveyor.assert_called_once_with(JOB_ID, "ASSEMBLY", unit_id=22, operation_id=OPERATION_ID)
        self.assertTrue(active["conveyor_confirmed"])

    async def test_stale_conveyor_commands_do_not_mutate_current_unit(self):
        pose = {"xyz_mm": [0, 0, 0], "xyzw": [0, 0, 0, 1]}
        for name, state, extra in (
            ("conveyor_arrived", "CONVEYOR_MOVING", {}),
            ("conveyor_failed", "CONVEYOR_MOVING", {"message": "old failure"}),
            ("conveyor_failed", "ASSEMBLY_COMPLETED", {"message": "old failure"}),
            ("transfer_assembled_pcb", "ASSEMBLY_COMPLETED", {"assembled_pcb": {"source": pose, "target": pose}}),
        ):
            for identity in ({"unit_id": 21}, {"operation_id": JOB_ID}, {"job_id": OPERATION_ID}):
                sequencer, active = self.fixture()
                active["state"] = state
                before = deepcopy(active)
                command = dict(command=name, job_id=JOB_ID, unit_id=22, operation_id=OPERATION_ID, **extra)
                command.update(identity)
                response = await AssemblySequencer.on_external_request(sequencer,
                    SimpleNamespace(cmd_str="mock\n" + json.dumps(command)), SimpleNamespace())
                with self.subTest(command=name, identity=identity):
                    self.assertEqual(json.loads(response.cmd_res)["error_code"], "NOT_ACTIVE")
                    self.assertEqual(active, before)
                    self.assertEqual(sequencer.backend.mock_calls, [])
                    sequencer.fail_active.assert_not_called()
                    sequencer.db_writer.claim.assert_not_called()

    async def test_conveyor_identity_is_required_before_dispatch(self):
        sequencer, active = self.fixture()
        for name in ("conveyor_arrived", "conveyor_failed", "transfer_assembled_pcb"):
            pose = {"xyz_mm": [0, 0, 0], "xyzw": [0, 0, 0, 1]}
            valid = dict(command=name, job_id=JOB_ID, unit_id=22, operation_id=OPERATION_ID)
            if name == "conveyor_failed":
                valid["message"] = "stopped"
            if name == "transfer_assembled_pcb":
                valid["assembled_pcb"] = {"source": pose, "target": pose}
            for key, value in (("unit_id", None), ("unit_id", True), ("unit_id", 0),
                               ("unit_id", "22"), ("operation_id", None), ("operation_id", "bad")):
                command = dict(valid)
                if value is None:
                    del command[key]
                else:
                    command[key] = value
                response = await AssemblySequencer.on_external_request(sequencer,
                    SimpleNamespace(cmd_str="mock\n" + json.dumps(command)), SimpleNamespace())
                with self.subTest(command=name, key=key, value=value):
                    self.assertEqual(json.loads(response.cmd_res)["error_code"], "INVALID_REQUEST")
        self.assertEqual(sequencer.backend.mock_calls, [])

    async def test_matching_transfer_is_idempotent_and_failed_wait_is_rejected(self):
        sequencer, active = self.fixture()
        active["state"] = "ASSEMBLY_COMPLETED"
        pose = {"xyz_mm": [0, 0, 0], "xyzw": [0, 0, 0, 1]}
        command = dict(command="transfer_assembled_pcb", job_id=JOB_ID, unit_id=22,
                       operation_id=OPERATION_ID, assembled_pcb={"source": pose, "target": pose})
        for _ in range(2):
            response = await AssemblySequencer.on_external_request(sequencer,
                SimpleNamespace(cmd_str="mock\n" + json.dumps(command)), SimpleNamespace())
            self.assertTrue(json.loads(response.cmd_res)["accepted"])
        sequencer.backend.confirm_conveyor.assert_called_once()
        self.assertTrue(active["transfer_requested"])
        command = dict(command="conveyor_failed", job_id=JOB_ID, unit_id=22,
                       operation_id=OPERATION_ID, message="late failure")
        sequencer.backend.fail_conveyor.side_effect = RuntimeError("movement already completed")
        response = await AssemblySequencer.on_external_request(sequencer,
            SimpleNamespace(cmd_str="mock\n" + json.dumps(command)), SimpleNamespace())
        self.assertEqual(json.loads(response.cmd_res)["error_code"], "BUSY")
        sequencer.fail_active.assert_not_called()

    async def test_movement_ids_are_distinct_and_recoverable(self):
        sequencer, active = self.fixture()
        sequencer.external_publisher = Mock()
        sequencer.terminal_snapshot = None
        sequencer.publish = MethodType(AssemblySequencer.publish, sequencer)
        snapshots = []
        def ready(*args, **kwargs):
            kwargs["on_ready"]()
            snapshots.append(assembly_snapshot(active, active["state"]))
        sequencer.backend.move_conveyor.side_effect = ready
        await AssemblySequencer.run_assembly_workflow(sequencer, active)
        self.assertEqual(len(snapshots), 2)
        self.assertNotEqual(snapshots[0]["operation_id"], snapshots[1]["operation_id"])
        messages = [json.loads(call.args[0].data) for call in sequencer.external_publisher.publish.call_args_list]
        movements = [row for row in messages if row["state"] in {"CONVEYOR_MOVING", "ASSEMBLY_COMPLETED"}]
        for snapshot, payload in zip(snapshots, movements):
            self.assertEqual(payload["operation_id"], snapshot["operation_id"])
            self.assertEqual(payload["unit_id"], 22)

    async def test_conveyor_failure_ends_workflow_before_robot_start(self):
        sequencer, active = self.fixture()
        sequencer.backend.move_conveyor.side_effect = TimeoutError("belt timeout")
        await AssemblySequencer.run_assembly_workflow(sequencer, active)
        self.assertEqual(sequencer.fail_active.call_args.args[0], "CONVEYOR_FAILED")
        sequencer.backend.start.assert_not_awaited()
        sequencer.backend.pick.assert_not_awaited()

    def test_incomplete_pass_target_restarts_recipe_for_next_unit(self):
        sequencer, active = self.fixture()
        sequencer.db_writer.get_job.return_value = {"completed_quantity":1,"requested_quantity":2}
        sequencer.db_writer.claim.return_value = {"job_id":JOB_ID,"unit_id":23}
        sequencer.run_assembly_workflow = AsyncMock()
        sequencer.executor = Mock()
        sequencer.executor.create_task.side_effect = lambda coroutine: coroutine.close()
        AssemblySequencer.finish_active_unit(sequencer, active)
        sequencer.db_writer.unit_completed.assert_called_once_with(22)
        calls = [call[0] for call in sequencer.db_writer.mock_calls]
        self.assertLess(calls.index("unit_completed"), calls.index("flush"))
        self.assertLess(calls.index("flush"), calls.index("claim"))
        self.assertEqual(active["unit_id"],23)
        self.assertEqual(active["before_action_index"],0)
        self.assertEqual(active["after_action_index"],0)
        self.assertEqual(active["placed_count"],0)
        sequencer.db_writer.finish.assert_not_called()
        sequencer.executor.create_task.assert_called_once()


class ModeIsolationTest(unittest.IsolatedAsyncioTestCase):
    async def test_opposite_prefix_is_rejected_before_any_dependency(self):
        for mode, prefix in (("real","mock"),("mock","real")):
            sequencer=SimpleNamespace(runtime_mode=mode, get_logger=lambda:Mock(),set_response=AssemblySequencer.set_response)
            response=await AssemblySequencer.on_external_request(sequencer,
                SimpleNamespace(cmd_str=prefix+"\n{}"),SimpleNamespace())
            self.assertEqual(json.loads(response.cmd_res)["error_code"],"MODE_MISMATCH")

    async def test_real_rejects_simulated_signals_and_unready_start_before_db(self):
        sequencer=SimpleNamespace(runtime_mode="real",recipe_version="assembly-r1",
            recipe={"joint_points":{},"frame":"base_link"},
            backend=SimpleNamespace(prepare=AsyncMock(side_effect=RuntimeError("reset is unverified"))),
            set_response=AssemblySequencer.set_response,db_writer=Mock())
        sequencer.start_real_job = MethodType(AssemblySequencer.start_real_job, sequencer)
        for command in ("observations","conveyor_arrived","conveyor_failed","transfer_assembled_pcb"):
            response=await AssemblySequencer.on_external_request(sequencer,
                SimpleNamespace(cmd_str="real\n"+json.dumps({"command":command,"job_id":JOB_ID})),SimpleNamespace())
            self.assertEqual(json.loads(response.cmd_res)["error_code"],"INVALID_REQUEST")
        response=await AssemblySequencer.on_external_request(sequencer,
            SimpleNamespace(cmd_str="real\n"+json.dumps({"command":"start","job_id":JOB_ID,"recipe_version":"assembly-r1"})),SimpleNamespace())
        self.assertEqual(json.loads(response.cmd_res)["error_code"],"NOT_READY")
        self.assertEqual(sequencer.db_writer.mock_calls,[])

    def test_db_checks_both_modes_and_rejects_environment_changes(self):
        for mode in ("mock","real"):
            for actual in ("mock","real",None):
                connection=Mock()
                connection.execute.return_value.fetchone.return_value={"runtime_mode":actual}
                with patch.object(store,"_RUNTIME_MODE",mode), patch.dict(os.environ,{"ASSEMBLY_SEQUENCER_MODE":mode,"PRODUCTION_DB_DSN":"test"}), patch.object(store.psycopg,"connect",return_value=connection):
                    if actual==mode:
                        self.assertIs(store._connect(),connection)
                        connection.close.assert_not_called()
                    else:
                        with self.assertRaisesRegex(RuntimeError,"MODE_REJECTED"):
                            store._connect()
                        connection.commit.assert_not_called()
                        connection.close.assert_called_once()
            with patch.object(store,"_RUNTIME_MODE",mode), patch.dict(os.environ,{"ASSEMBLY_SEQUENCER_MODE":"real" if mode=="mock" else "mock"}), patch.object(store.psycopg,"connect") as connect:
                with self.assertRaisesRegex(RuntimeError,"MODE_REJECTED"):
                    store._connect()
                connect.assert_not_called()

    def test_mock_process_cannot_write_real_inspection(self):
        with patch.object(store,"_RUNTIME_MODE","mock"), patch.dict(os.environ,{"ASSEMBLY_SEQUENCER_MODE":"mock"}), patch.object(store.psycopg,"connect") as connect:
            with self.assertRaisesRegex(RuntimeError,"MODE_REJECTED"):
                store._connect(expected_mode="real")
            connect.assert_not_called()


class RealWorkflowTest(unittest.IsolatedAsyncioTestCase):
    def sequencer(self, decision="PASS", reached=True):
        from assembly_sequencer.recipe_contract import PRODUCTION_SLOTS
        slots = [slot for slot, _ in PRODUCTION_SLOTS]
        active = dict(job_id=JOB_ID, unit_id=22, recipe_version="assembly-r1", execution_id=OPERATION_ID,
            robot_recipe_revision="deployed-r1", scene_confirmation={}, slot_codes=slots,
            placed_slot_codes=[], placed_count=0, expected_step_count=25, held_step_order=0,
            held_part_id="", held_slot_code="", state="STARTED", inspection_result="")
        db = Mock(sync_state="SYNCED")
        db.get_job.return_value = dict(completed_quantity=1 if reached else 0, requested_quantity=1)
        backend = SimpleNamespace(move_conveyor=AsyncMock(), execute_assembly=AsyncMock(),
                                  inspect_unit=AsyncMock(return_value=dict(result=decision, defects=None)))
        node = SimpleNamespace(runtime_mode="real", active=active, backend=backend, db_writer=db,
            terminal_snapshot=None, pending_requests={}, publish=Mock(), get_logger=lambda: Mock())
        for name in ("real_progress", "finish_active_unit", "fail_active", "fail_job", "finalize_cancel", "restore_quality_hold"):
            setattr(node, name, MethodType(getattr(AssemblySequencer, name), node))
        async def assembly(*args):
            args[-1](dict(execution_id=OPERATION_ID, production_job_id=JOB_ID, unit_id=22,
                          completed_slots=slots, current_stage="complete"))
        backend.execute_assembly.side_effect = assembly
        return node, active

    async def test_force_cancel_is_rejected_and_keeps_active_job_running(self):
        node, active = self.sequencer()
        node.recipe_version = "assembly-r1"
        node.set_response = AssemblySequencer.set_response
        request = SimpleNamespace(cmd_str="real\n" + json.dumps(
            {"command": "force_cancel", "job_id": JOB_ID}))

        response = await AssemblySequencer.on_external_request(
            node, request, SimpleNamespace())
        result = json.loads(response.cmd_res)

        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "CONTROL_REJECTED")
        self.assertIs(node.active, active)
        node.db_writer.finish.assert_not_called()
        node.db_writer.flush.assert_not_called()

    async def test_force_cancel_late_assembly_result_cannot_start_inspection_or_write_completion(self):
        node, active = self.sequencer()
        async def cancel_during_assembly(*args):
            active["force_cancel_requested"] = True
            node.finalize_cancel(active, "force")
            args[-1](dict(execution_id=OPERATION_ID, production_job_id=JOB_ID, unit_id=22,
                          completed_slots=active["slot_codes"], current_stage="complete"))
        node.backend.execute_assembly.side_effect = cancel_during_assembly
        await AssemblySequencer.run_real_workflow(node, active)
        node.backend.move_conveyor.assert_awaited_once_with("ASSEMBLY")
        node.backend.inspect_unit.assert_not_awaited()
        node.db_writer.assembly_completed.assert_not_called()
        node.db_writer.inspection_recorded.assert_not_called()
        self.assertIsNone(node.active)

    def test_detail_changes_notify_without_claiming_a_held_part(self):
        node, active = self.sequencer()
        original = dict(job_id=OPERATION_ID, operation_id="pick-1", action="robot.pick",
                        phase="05_pick_final_50mm_vertical", event="PHASE_STARTED")
        metadata = dict(server_instance_id="robot", event_sequence=1, part_id="GPU", slot_code="GPU-01")
        payload = dict(execution_id=OPERATION_ID, production_job_id=JOB_ID, unit_id=22,
                       completed_slots=[], current_stage="assemble_non-smd",
                       last_robot_event=dict(original=original, metadata=metadata))
        node.real_progress(active, payload)
        node.real_progress(active, payload)
        self.assertEqual(node.publish.call_count, 1)
        snapshot = assembly_snapshot(active, active["state"])
        self.assertEqual(snapshot["current_slot_code"], "GPU-01")
        self.assertEqual(snapshot["current_phase"], "05_pick_final_50mm_vertical")
        self.assertEqual(snapshot["held_slot_code"], "")
        original["event"] = "PHASE_COMPLETED"
        metadata["event_sequence"] = 2
        node.real_progress(active, payload)
        self.assertEqual(node.publish.call_count, 2)
        self.assertEqual(active["current_event"], "PHASE_COMPLETED")
        payload["current_stage"] = "capture_smd_view"
        node.real_progress(active, payload)
        self.assertEqual(assembly_snapshot(active, active["state"])["current_phase"], "")
        payload["current_stage"] = "assemble_smd"
        node.real_progress(active, payload)
        node.real_progress(active, payload)
        self.assertEqual(active["current_slot_code"], "", "Old non-SMD event must not leak into SMD.")
        metadata.update(event_sequence=3, part_id="CAP", slot_code="CAP-01")
        node.real_progress(active, payload)
        self.assertEqual(active["current_slot_code"], "CAP-01")
        active.update(state="ASSEMBLY_COMPLETED", message="검사 진행 중")
        self.assertEqual(assembly_snapshot(active, active["state"])["current_phase"], "")

    def test_foreign_or_invalid_detail_is_not_displayed(self):
        for job, part, slot in (("foreign", "GPU", "GPU-01"), (OPERATION_ID, "HBM", "GPU-01")):
            node, active = self.sequencer()
            node.real_progress(active, dict(execution_id=OPERATION_ID, production_job_id=JOB_ID, unit_id=22,
                completed_slots=[], current_stage="assemble_non-smd", last_robot_event=dict(
                    original=dict(job_id=job, action="robot.pick", phase="GRASP", event="PHASE_STARTED"),
                    metadata=dict(part_id=part, slot_code=slot))))
            self.assertEqual(active["current_slot_code"], "")

    def test_stage_changes_without_placement_notify_and_restore(self):
        node, active = self.sequencer()
        payload = dict(execution_id=OPERATION_ID, production_job_id=JOB_ID, unit_id=22,
                       completed_slots=[], current_stage="capture_board")
        node.real_progress(active, payload)
        node.real_progress(active, payload)
        self.assertEqual(node.publish.call_count, 1)
        self.assertEqual(node.publish.call_args.args[0]["slot_code"], "")
        payload["current_stage"] = "capture_tray"
        node.real_progress(active, payload)
        self.assertEqual(node.publish.call_count, 2)
        self.assertEqual(assembly_snapshot(active, active["state"])["message"], "capture_tray")
        payload["completed_slots"] = active["slot_codes"][:1]
        node.real_progress(active, payload)
        payload["current_stage"] = "after_photo"
        node.real_progress(active, payload)
        self.assertEqual(node.publish.call_count, 4)
        self.assertEqual(active["placed_count"], 1)
        # A stale snapshot must not replace a newer placement or its stage.
        payload.update(completed_slots=[], current_stage="capture_board")
        node.real_progress(active, payload)
        self.assertEqual(node.publish.call_count, 4)
        self.assertEqual(active["message"], "after_photo")

    async def test_inspection_notification_precedes_result_and_preserves_decision(self):
        for decision, reached in (("PASS", True), ("FAIL", False), ("UNKNOWN", False)):
            node, active = self.sequencer(decision, reached)
            async def inspect(*args):
                self.assertEqual(node.publish.call_args.args[0]["message"], "검사 진행 중")
                self.assertEqual(assembly_snapshot(active, active["state"])["message"], "검사 진행 중")
                return dict(result=decision, defects=None)
            node.backend.inspect_unit.side_effect = inspect
            await AssemblySequencer.run_real_workflow(node, active)
            messages = [call.args[0]["message"] for call in node.publish.call_args_list]
            self.assertLess(messages.index("조립 위치 이동 중"), messages.index("전체 조립 실행 중"))
            self.assertLess(messages.index("검사 위치 이동 중"), messages.index("검사 진행 중"))
            if decision == "UNKNOWN":
                self.assertIn("판정 보류", messages[-1])
            else:
                self.assertIn("검사 결과 · " + decision, messages[-1])
            if decision == "PASS":
                self.assertEqual(node.terminal_snapshot["message"], messages[-1])
            else:
                self.assertEqual(active["state"], "PAUSED")

    async def test_start_claims_once_and_duplicate_never_starts_another_unit(self):
        import time
        from assembly_sequencer.recipe_contract import PRODUCTION_SLOTS
        node, _ = self.sequencer()
        node.active = None
        node.set_response = AssemblySequencer.set_response
        node.recipe_version = "assembly-r1"
        node.backend.prepare_execution = AsyncMock(return_value="deployed-r1")
        node.db_writer.get_job.return_value = dict(job_status="PENDING")
        node.db_writer.get_product_slots.return_value = [dict(slot_code=s, part_id=p) for s, p in PRODUCTION_SLOTS]
        node.db_writer.claim.return_value = dict(job_id=JOB_ID, unit_id=23)
        node.run_real_workflow = Mock(return_value="workflow-task")
        node.executor = Mock()
        command = dict(job_id=JOB_ID, recipe_version="assembly-r1", scene_confirmation=dict(
            operator_id="test", execution_id=OPERATION_ID, confirmed_unix=time.time(),
            scope="empty_gripper_empty_pcb_full_tray_fixed_fixture"))
        for _ in range(2):
            response = await AssemblySequencer.start_real_job(node, command, SimpleNamespace())
            self.assertTrue(json.loads(response.cmd_res)["accepted"])
        node.db_writer.claim.assert_called_once()
        node.executor.create_task.assert_called_once()
        self.assertEqual(node.active["unit_id"], 23)
        node.backend.move_conveyor.assert_not_awaited()

    async def test_preflight_failure_never_claims_job(self):
        import time
        node, _ = self.sequencer()
        node.active = None
        node.set_response = AssemblySequencer.set_response
        node.recipe_version = "assembly-r1"
        node.backend.prepare_execution = AsyncMock(side_effect=RuntimeError("not ready"))
        command = dict(job_id=JOB_ID, recipe_version="assembly-r1", scene_confirmation=dict(
            operator_id="test", execution_id=OPERATION_ID, confirmed_unix=time.time(),
            scope="empty_gripper_empty_pcb_full_tray_fixed_fixture"))
        response = await AssemblySequencer.start_real_job(node, command, SimpleNamespace())
        self.assertEqual(json.loads(response.cmd_res)["error_code"], "NOT_READY")
        node.db_writer.claim.assert_not_called()
        node.backend.move_conveyor.assert_not_awaited()

    async def test_pass_advances_only_after_completion_and_db_sync(self):
        node, active = self.sequencer()
        sequence = Mock()
        sequence.attach_mock(node.backend.move_conveyor, "move")
        sequence.attach_mock(node.backend.execute_assembly, "assembly")
        sequence.attach_mock(node.backend.inspect_unit, "inspect")
        sequence.attach_mock(node.db_writer.assembly_completed, "assembled")
        sequence.attach_mock(node.db_writer.flush, "flush")
        sequence.attach_mock(node.db_writer.inspection_recorded, "record")
        sequence.attach_mock(node.db_writer.unit_completed, "complete")
        sequence.attach_mock(node.db_writer.finish, "finish")
        await AssemblySequencer.run_real_workflow(node, active)
        self.assertEqual([c[0] for c in sequence.mock_calls],
            ["move", "assembly", "assembled", "flush", "move", "inspect", "record", "flush",
             "complete", "flush", "finish", "flush"])
        self.assertEqual([c.args[0] for c in node.backend.move_conveyor.await_args_list], ["ASSEMBLY", "INSPECTION"])
        self.assertIsNone(node.active)
        self.assertEqual(node.terminal_snapshot["state"], "COMPLETED")
        self.assertEqual(node.terminal_snapshot["placed_count"], 25)

    async def test_unknown_keeps_unit_running_and_preserves_reason_in_status(self):
        node, active = self.sequencer("UNKNOWN", False)
        await AssemblySequencer.run_real_workflow(node, active)
        node.db_writer.inspection_recorded.assert_called_once()
        node.db_writer.unit_completed.assert_not_called()
        node.db_writer.finish.assert_not_called()
        self.assertEqual(assembly_snapshot(active, active["state"])["error_code"], "INSPECTION_UNKNOWN")
        self.assertTrue(active["inspection_hold"])

    async def test_fail_inspection_completes_attempt_but_waits_for_new_confirmation(self):
        node, active = self.sequencer("FAIL", False)
        await AssemblySequencer.run_real_workflow(node, active)
        node.db_writer.unit_completed.assert_called_once_with(22)
        node.db_writer.finish.assert_not_called()
        node.db_writer.claim.assert_not_called()
        self.assertTrue(active["awaiting_next_unit"])
        self.assertEqual(active["error_code"], "QUALITY_HOLD")

    async def test_quality_resume_does_not_resume_completed_robot_execution(self):
        node, active = self.sequencer("FAIL", False)
        await AssemblySequencer.run_real_workflow(node, active)
        node.set_response = AssemblySequencer.set_response
        node.recipe_version = "assembly-r1"
        node.backend.prepare_execution = AsyncMock(return_value="revision")
        node.backend.request_control = AsyncMock()
        response = await AssemblySequencer.on_external_request(node,
            SimpleNamespace(cmd_str="real\n" + json.dumps({"command": "resume", "job_id": JOB_ID})), SimpleNamespace())
        self.assertTrue(json.loads(response.cmd_res)["accepted"])
        node.db_writer.resume_quality.assert_called_once_with(JOB_ID)
        node.backend.request_control.assert_not_called()
        node.db_writer.claim.assert_not_called()
        self.assertEqual(active["error_code"], "SCENE_CONFIRMATION_REQUIRED")

    async def test_quality_hold_is_restored_without_starting_a_unit(self):
        node, active = self.sequencer("FAIL", False)
        node.active = None
        node.recipe_version = "assembly-r1"
        node.recipe = None
        node.set_response = AssemblySequencer.set_response
        node.db_writer.get_quality_hold.return_value = dict(job_id=JOB_ID, unit_id=22, recipe_version="assembly-r1")
        await AssemblySequencer.on_pending_job(node)
        response = await AssemblySequencer.on_external_request(node,
            SimpleNamespace(cmd_str="real\n" + json.dumps({"command": "status"})), SimpleNamespace())
        snapshot = json.loads(response.cmd_res)
        self.assertEqual(snapshot["error_code"], "QUALITY_HOLD")
        self.assertEqual(snapshot["state"], "PAUSED")
        node.db_writer.claim.assert_not_called()
        node.backend.execute_assembly.assert_not_called()

    async def test_quality_cancel_finalizes_job_without_robot_command(self):
        node, active = self.sequencer("FAIL", False)
        await AssemblySequencer.run_real_workflow(node, active)
        node.set_response = AssemblySequencer.set_response
        node.recipe_version = "assembly-r1"
        node.backend.request_control = AsyncMock()
        response = await AssemblySequencer.on_external_request(node,
            SimpleNamespace(cmd_str="real\n" + json.dumps({"command": "cancel", "job_id": JOB_ID})), SimpleNamespace())
        self.assertTrue(json.loads(response.cmd_res)["accepted"])
        node.db_writer.finish.assert_called_once_with(JOB_ID, "CANCELLED")
        node.backend.request_control.assert_not_called()
        self.assertIsNone(node.active)

    async def test_uncertain_robot_completion_blocks_inspection_and_db_finalization(self):
        node, active = self.sequencer()
        node.backend.execute_assembly.side_effect = RuntimeError("SAFETY_STOP: completion unconfirmed")
        await AssemblySequencer.run_real_workflow(node, active)
        node.backend.move_conveyor.assert_awaited_once_with("ASSEMBLY")
        node.backend.inspect_unit.assert_not_awaited()
        node.db_writer.assembly_completed.assert_not_called()
        node.db_writer.finish.assert_not_called()
        self.assertEqual(active["state"], "PAUSED")

    async def test_db_failure_after_assembly_never_moves_to_inspection(self):
        node, active = self.sequencer()
        node.db_writer.flush.side_effect = RuntimeError("DB unavailable")
        await AssemblySequencer.run_real_workflow(node, active)
        node.backend.move_conveyor.assert_awaited_once_with("ASSEMBLY")
        node.backend.inspect_unit.assert_not_awaited()
        self.assertEqual(node.terminal_snapshot["error_code"], "DB_ERROR")


class RealApiBoundaryTest(unittest.IsolatedAsyncioTestCase):
    def backend(self):
        node = Mock(runtime_mode="real", executor=None)
        node.context.get_domain_id.return_value = 5
        backend = RealBackend(node)
        self.addCleanup(backend.close)
        return backend, node

    def test_real_startup_does_not_load_or_declare_motion_recipe(self):
        with patch("rclpy.node.Node.__init__", return_value=None), \
             patch.object(AssemblySequencer, "context", new_callable=PropertyMock) as context, \
             patch.object(AssemblySequencer, "declare_parameter") as parameter, \
             patch.object(AssemblySequencer, "create_service"), \
             patch.object(AssemblySequencer, "create_timer"), \
             patch.object(AssemblySequencer, "create_publisher"), \
             patch("assembly_sequencer.sequencer_node.RealBackend"), \
             patch("assembly_sequencer.sequencer_node.DbWriter") as writer, \
             patch("assembly_sequencer.sequencer_node.load_recipe") as load, \
             patch.dict(os.environ, {"ASSEMBLY_SEQUENCER_MODE": "real"}):
            context.return_value.get_domain_id.return_value = 5
            writer.return_value.recover_interrupted.return_value = 0
            node = AssemblySequencer()
            self.assertIsNone(node.recipe)
            self.assertEqual(node.recipe_version, "assembly-r1")
            load.assert_not_called()
            parameter.assert_not_called()

    async def test_real_api_does_not_publish_individual_motion(self):
        backend, node = self.backend()
        for method in ("prepare", "start", "move_joint", "pick", "place", "_execute",
                       "resolve_targets", "transfer_assembled_pcb", "set_paused", "accept_operation_feedback"):
            self.assertFalse(hasattr(backend, method), method)
        node.create_client.return_value.call_async.assert_not_called()
        node.create_publisher.return_value.publish.assert_not_called()
        self.assertEqual(node.create_publisher.call_args.args[1], "/real/assembly/command")
        self.assertEqual({call.args[1] for call in node.create_subscription.call_args_list},
                         {"/real/assembly/event", "/conveyor/state"})

    async def test_real_start_and_pending_poll_never_claim_without_cycle_contract(self):
        backend, node = self.backend()
        sequencer = SimpleNamespace(runtime_mode="real", recipe=None, recipe_version=None,
            backend=backend, active=None, db_writer=Mock(), set_response=AssemblySequencer.set_response)
        sequencer.start_real_job = MethodType(AssemblySequencer.start_real_job, sequencer)
        command = dict(command="start", job_id=JOB_ID, recipe_version="robot-owned-r2")
        response = await AssemblySequencer.on_external_request(sequencer,
            SimpleNamespace(cmd_str="real\n" + json.dumps(command)), SimpleNamespace())
        self.assertEqual(json.loads(response.cmd_res)["error_code"], "NOT_READY")
        response = await AssemblySequencer.start_job(sequencer, command, SimpleNamespace())
        self.assertEqual(json.loads(response.cmd_res)["error_code"], "NOT_READY")
        sequencer.restore_quality_hold = MethodType(AssemblySequencer.restore_quality_hold, sequencer)
        await AssemblySequencer.on_pending_job(sequencer)
        sequencer.db_writer.get_quality_hold.assert_called_once()
        sequencer.db_writer.claim.assert_not_called()
        node.create_client.return_value.call_async.assert_not_called()

    async def test_status_uses_api_but_does_not_enable_unconnected_runner(self):
        backend, node = self.backend()
        future = asyncio.get_running_loop().create_future()
        future.set_result(SimpleNamespace(success=True, message='{"hardware_execution_enabled":false}'))
        node.create_client.return_value.call_async.return_value = future
        snapshot = await backend.status()
        self.assertFalse(snapshot["equipment_ready"])
        self.assertFalse(snapshot["robot_api_status"]["hardware_execution_enabled"])
        self.assertFalse(backend._pending_calls)

    async def test_v2_capability_is_read_from_nested_contract(self):
        backend, node = self.backend()
        robot = dict(hardware_execution_enabled=True, state_fresh=True,
                     robot_health_clear=True, robot_mode=0, robot_motion_done=1, recovery_required=False,
                     active_operation=None, held_candidate=None)
        assembly = dict(hardware_execution_enabled=True,
                        supported_actions=["assembly.check", "assembly.stop"],
                        production_contract=dict(schema="fr5.assembly_execution/v2",
                            capabilities=dict(start=True), current_recipe_revision="deployed-r1",
                            equipment_busy_or_unresolved=False))
        backend._read_status = AsyncMock(side_effect=[robot, assembly])
        backend._ready_conveyor = Mock()
        backend._vision_url = "http://vision:8766"
        with patch.dict(os.environ, {"KSMC_VISION_API_TOKEN": "test-token-" * 4, "DEFECT_IMAGE_ROOT": "/tmp/test-evidence"}):
            snapshot = await backend.status()
        self.assertTrue(snapshot["production_contract"]["capabilities"]["start"])
        self.assertTrue(snapshot["equipment_ready"])
        self.assertTrue(snapshot["available"])
        node.create_publisher.return_value.publish.assert_not_called()

    def test_scene_confirmation_requires_actual_fresh_confirmation(self):
        from assembly_sequencer.recipe_contract import validate_scene_confirmation
        confirmation = dict(operator_id="operator-1", execution_id=OPERATION_ID,
                            confirmed_unix=1000.0,
                            scope="empty_gripper_empty_pcb_full_tray_fixed_fixture")
        with patch("assembly_sequencer.recipe_contract.time.time", return_value=1050.0):
            validate_scene_confirmation(confirmation)
            for changed in ({"confirmed_unix": 0}, {"confirmed_unix": 1051},
                            {"confirmed_unix": float("nan")}, {"confirmed_unix": True},
                            {"operator_id": " "}, {"execution_id": "not-a-uuid"}, {"scope": "true"}):
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    validate_scene_confirmation(confirmation | changed)
            command = dict(command="start", job_id=JOB_ID, recipe_version="assembly-r1",
                           scene_confirmation=confirmation)
            self.assertEqual(parse_command(json.dumps(command), None, "real")[0], "start")
            with self.assertRaises(ValueError):
                parse_command(json.dumps(command), "assembly-r1", "mock")

    def test_old_or_unrelated_execution_events_cannot_replace_terminal(self):
        backend, node = self.backend()
        backend._execution_id = OPERATION_ID
        completed = dict(schema="fr5.assembly_execution/v2", execution_id=OPERATION_ID,
                         event="EXECUTION_COMPLETED")
        backend._receive_execution(SimpleNamespace(data=json.dumps(completed | {"execution_id": JOB_ID})))
        self.assertIsNone(backend._execution_response)
        backend._receive_execution(SimpleNamespace(data=json.dumps(completed)))
        backend._receive_execution(SimpleNamespace(data=json.dumps(completed | {"event": "ROBOT_EVENT"})))
        self.assertEqual(backend._execution_response, completed)

    async def test_control_requests_preserve_execution_and_pause_identity(self):
        backend, node = self.backend()
        backend._execution_id = OPERATION_ID
        backend._execution_server = "server-a"
        status = dict(schema=api_contracts.ASSEMBLY_SCHEMA, execution_id=OPERATION_ID, server_instance_id="server-a",
                      capabilities=dict(pause=True, resume=True, cancel=True), recovery_required=False,
                      status="running")
        backend._read_status = AsyncMock(return_value={"production_contract": status})
        request = await backend.request_control(OPERATION_ID, "pause")
        self.assertEqual(request["action"], "assembly.pause")
        self.assertEqual(request["execution_id"], OPERATION_ID)
        self.assertIn("control_pending", backend.control_progress(status))
        paused = dict(status, status="paused", stop_verified=True, resume_available=True,
                      pause_control_id=request["control_id"])
        self.assertNotIn("control_pending", backend.control_progress(paused))
        backend._read_status.return_value = {"production_contract": paused}
        resume = await backend.request_control(OPERATION_ID, "resume")
        self.assertEqual(resume["pause_control_id"], request["control_id"])
        self.assertGreater(resume["control_sequence"], request["control_sequence"])
        self.assertIn("control_pending", backend.control_progress(dict(status, control_id="unrelated")))
        self.assertNotIn("control_pending", backend.control_progress(dict(status, control_id=resume["control_id"])))

    async def test_cancel_needs_matching_control_and_verified_stop(self):
        backend, node = self.backend()
        backend._execution_id = OPERATION_ID
        backend._execution_server = "server-a"
        status = dict(schema=api_contracts.ASSEMBLY_SCHEMA, execution_id=OPERATION_ID, server_instance_id="server-a",
                      capabilities=dict(cancel=True), recovery_required=False, status="running")
        backend._read_status = AsyncMock(return_value={"production_contract": status})
        request = await backend.request_control(OPERATION_ID, "cancel")
        backend._read_status.assert_awaited_once()
        result = dict(status, status="cancelled", control_id=request["control_id"], stop_verified=False)
        self.assertIn("control_pending", backend.control_progress(result))
        self.assertNotIn("control_pending", backend.control_progress(dict(result, stop_verified=True)))

    async def test_control_rejection_does_not_replace_assembly_result(self):
        backend, node = self.backend()
        backend._execution_id = OPERATION_ID
        backend._execution_server = "server-a"
        status = dict(schema=api_contracts.ASSEMBLY_SCHEMA, execution_id=OPERATION_ID, server_instance_id="server-a",
                      capabilities=dict(pause=True), recovery_required=False, status="running")
        backend._read_status = AsyncMock(return_value={"production_contract": status})
        await backend.request_control(OPERATION_ID, "pause")
        backend._execution_response = status
        backend._receive_execution(SimpleNamespace(data=json.dumps(dict(
            schema="fr5.assembly_execution/v2", execution_id=OPERATION_ID,
            request_accepted=False, message="control rejected"))))
        self.assertEqual(backend._execution_response, status)
        self.assertEqual(backend.control_progress(status)["control_error"], "control rejected")

    def completion_fixture(self):
        from assembly_sequencer.recipe_contract import PRODUCTION_SLOTS
        slots = [slot for slot, _ in PRODUCTION_SLOTS]
        request = dict(execution_id=OPERATION_ID, production_job_id=JOB_ID, unit_id=22,
                       product_id="HBM-ACCELERATOR-PACKAGE-BOARD", production_recipe_version="assembly-r1",
                       robot_recipe_revision="deployed-r1")
        complete = dict(request, schema="fr5.assembly_execution/v2", event="EXECUTION_COMPLETED",
                        status="motion_complete_awaiting_physical_verification", expected_slots=list(slots),
                        completed_slots=list(slots), stop_verified=True, recovery_required=False,
                        held_candidate=False, plan_complete=True,
                        plan_hashes={"non-smd": "a" * 64, "smd": "b" * 64}, inspection_pass=None)
        return request, complete, slots

    def test_completion_requires_identity_exact_slots_and_execution_evidence(self):
        request, complete, slots = self.completion_fixture()
        RealBackend._validate_completion(complete, request, slots)
        RealBackend._validate_completion(complete | {"held_candidate": None}, request, slots)
        for change in ({"unit_id": 23}, {"execution_id": JOB_ID}, {"completed_slots": slots[:-1]},
                       {"completed_slots": slots[:-1] + [slots[0]]}, {"expected_slots": []},
                       {"stop_verified": False}, {"recovery_required": True}, {"held_candidate": {}},
                       {"held_candidate": 0}, {"plan_complete": False}, {"plan_hashes": {}},
                       {"event": "EXECUTION_STARTED"}, {"status": "running"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                RealBackend._validate_completion(complete | change, request, slots)
        missing = dict(complete)
        del missing["held_candidate"]
        with self.assertRaises(ValueError):
            RealBackend._validate_completion(missing, request, slots)

    def test_eventless_rejection_and_failure_survive_late_progress(self):
        backend, _ = self.backend()
        for terminal in (dict(status="request_rejected", request_accepted=False, error_code="SAFETY_STOP"),
                         dict(event="EXECUTION_FAILED", recovery_required=True,
                              error_code="MOTION_PLAN_REJECTED", failure={"stage": "preflight_non-smd"})):
            backend._execution_id = OPERATION_ID
            backend._execution_response = None
            terminal = dict(terminal, schema="fr5.assembly_execution/v2", execution_id=OPERATION_ID)
            backend._receive_execution(SimpleNamespace(data=json.dumps(terminal)))
            backend._receive_execution(SimpleNamespace(data=json.dumps(dict(
                schema="fr5.assembly_execution/v2", execution_id=OPERATION_ID, event="EXECUTION_PROGRESS"))))
            self.assertEqual(backend._execution_response, terminal)

    def test_execution_sequence_and_server_restart_are_not_success(self):
        backend, _ = self.backend()
        backend._execution_id = OPERATION_ID
        backend._execution_server = "server-a"
        progress = dict(schema="fr5.assembly_execution/v2", execution_id=OPERATION_ID,
                        server_instance_id="server-a", event="EXECUTION_PROGRESS", event_sequence=20)
        backend._receive_execution(SimpleNamespace(data=json.dumps(progress)))
        backend._receive_execution(SimpleNamespace(data=json.dumps(progress | {"event_sequence": 19})))
        self.assertEqual(backend._execution_response["event_sequence"], 20)
        backend._receive_execution(SimpleNamespace(data=json.dumps(progress | {"server_instance_id": "server-b"})))
        self.assertTrue(backend._execution_response["recovery_required"])
        self.assertEqual(backend._execution_response["error_code"], "SERVER_RESTARTED")

    def test_conveyor_honors_deployed_interlock_requirement(self):
        import time
        backend, _ = self.backend()
        backend._conveyor_state = dict(state="IDLE", moving=False, armed=True, vision_ready=True,
            vision_ready_fresh=True, fr5_clear=False, fr5_clear_fresh=False, server_instance_id="server-a")
        backend._conveyor_received = time.monotonic()
        for required in (None, True, "false", 0):
            backend._conveyor_state["fr5_interlock_required"] = required
            with self.assertRaisesRegex(RuntimeError, "interlock"):
                backend._ready_conveyor()
        backend._conveyor_state["fr5_interlock_required"] = False
        backend._ready_conveyor()
        backend._conveyor_state.update(fr5_interlock_required=True, fr5_clear=True, fr5_clear_fresh=True)
        backend._ready_conveyor()

    def test_conveyor_readiness_reports_specific_stop_and_vision_reasons(self):
        import time
        backend, _ = self.backend()
        ready = dict(state="IDLE", moving=False, armed=True, vision_ready=True,
                     vision_ready_fresh=True, fr5_interlock_required=False, server_instance_id="server-a")
        for change, message in ((dict(state="MANUAL_STOP", reason="remote stop"), "정지 해제"),
                                (dict(state="FAULT", reason="heartbeat missing"), "heartbeat missing"),
                                (dict(state="MOVING_TO_ASSEMBLY", moving=True), "이동 중"),
                                (dict(armed=False), "armed=false"),
                                (dict(vision_ready_fresh=False), "신호 수신"),
                                (dict(vision_ready=False), "vision_ready=false")):
            with self.subTest(change=change):
                backend._conveyor_state = ready | change
                backend._conveyor_received = time.monotonic()
                with self.assertRaisesRegex(RuntimeError, message):
                    backend._ready_conveyor()
        backend._conveyor_state = ready
        backend._conveyor_received = time.monotonic()
        self.assertEqual(backend._ready_conveyor(), ready)

    async def test_whole_start_persists_request_and_waits_for_matching_completion(self):
        import tempfile
        import time
        backend, node = self.backend()
        request, completed, slots = self.completion_fixture()
        confirmation = dict(operator_id="test-operator", execution_id=OPERATION_ID,
            confirmed_unix=time.time(), scope="empty_gripper_empty_pcb_full_tray_fixed_fixture")
        backend._read_status = AsyncMock(side_effect=[{}, {"production_contract": {"server_instance_id": "server-a"}}])
        backend._validate_readiness = Mock(return_value="deployed-r1")
        backend._assembly_command.get_subscription_count.return_value = 1
        progress = Mock()
        async def tick():
            backend._receive_execution(SimpleNamespace(data=json.dumps(completed)))
        backend._wait_tick = tick
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"DEFECT_IMAGE_ROOT": directory}):
            def publish(message):
                saved = json.loads((Path(directory) / "executions/22/request.json").read_text())
                self.assertEqual(saved, json.loads(message.data))
                backend._receive_execution(SimpleNamespace(data=json.dumps(dict(
                    completed, event="EXECUTION_STARTED", status="running", completed_slots=[]))))
            backend._assembly_command.publish.side_effect = publish
            result = await backend.execute_assembly(JOB_ID, 22, "assembly-r1", "deployed-r1",
                                                     confirmation, slots, progress)
            self.assertEqual(result["event"], "EXECUTION_COMPLETED")
            backend._assembly_command.publish.assert_called_once()
            self.assertEqual(progress.call_args.args[0]["completed_slots"], slots)
            self.assertIsNone(backend._execution_id)
            self.assertIsNone(backend._display_wait)
            self.assertTrue((Path(directory) / "executions/22/events.jsonl").is_file())

    async def test_whole_start_does_not_retry_an_uncertain_execution(self):
        import tempfile
        import time
        backend, _ = self.backend()
        _, _, slots = self.completion_fixture()
        confirmation = dict(operator_id="test-operator", execution_id=OPERATION_ID,
            confirmed_unix=time.time(), scope="empty_gripper_empty_pcb_full_tray_fixed_fixture")
        backend._read_status = AsyncMock(side_effect=[{}, {"production_contract": {"server_instance_id": "server-a"}}])
        backend._validate_readiness = Mock(return_value="deployed-r1")
        backend._assembly_command.get_subscription_count.return_value = 1
        backend._wait_tick = AsyncMock(side_effect=TimeoutError("connection lost"))
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"DEFECT_IMAGE_ROOT": directory}):
            with self.assertRaisesRegex(RuntimeError, "SAFETY_STOP: connection lost"):
                await backend.execute_assembly(JOB_ID, 22, "assembly-r1", "deployed-r1", confirmation, slots, Mock())
        backend._assembly_command.publish.assert_called_once()
        self.assertEqual(backend._execution_id, OPERATION_ID)
        self.assertTrue(backend.execution_tracking_stopped)
        self.assertIsNone(backend._display_wait)

    async def test_invalid_confirmation_never_publishes_start(self):
        backend, _ = self.backend()
        with self.assertRaises(ValueError):
            await backend.execute_assembly(JOB_ID, 22, "assembly-r1", "deployed-r1", None, [], Mock())
        backend._assembly_command.publish.assert_not_called()

    def test_wrong_mode_is_rejected_before_any_ros_connections(self):
        for mode, domain in (("mock",42),("real",42),("mock",5),("real",43)):
            node = Mock(runtime_mode=mode)
            node.context.get_domain_id.return_value = domain
            with self.assertRaisesRegex(RuntimeError, "MODE_REJECTED"):
                RealBackend(node)
            node.create_client.assert_not_called()
            node.create_publisher.assert_not_called()

    async def test_cancel_before_assembly_requires_new_stopped_feedback(self):
        import time
        backend, _ = self.backend()
        backend._conveyor_state = dict(server_instance_id="server-a", state="MANUAL_STOP",
            moving=False, command_linear_x_mps=0)
        backend._conveyor_received = time.monotonic() - 10
        backend._read_status = AsyncMock(return_value={})
        async def feedback():
            backend._conveyor_received = time.monotonic()
        backend._wait_tick = AsyncMock(side_effect=feedback)
        result = await backend.confirm_conveyor_stopped()
        self.assertFalse(result["moving"])
        backend._wait_tick.assert_awaited_once()
        backend._read_status.assert_awaited_once_with(backend._conveyor_stop)

    async def test_cancel_before_assembly_keeps_job_when_stop_fails(self):
        active = dict(job_id=JOB_ID, state="PAUSED", control_pending=True)
        node = SimpleNamespace(active=active, backend=SimpleNamespace(
            confirm_conveyor_stopped=AsyncMock(side_effect=RuntimeError("stale state"))),
            db_writer=Mock(sync_state="NOT_STARTED"), publish=Mock())
        await AssemblySequencer.cancel_before_assembly(node, active)
        node.db_writer.finish.assert_not_called()
        self.assertIs(node.active, active)
        self.assertEqual(active["error_code"], "CONTROL_UNCONFIRMED")
        self.assertFalse(active["control_pending"])

    async def test_cancel_before_assembly_commits_only_after_stop(self):
        active = dict(job_id=JOB_ID, state="PAUSED", control_pending=True)
        writer = Mock(sync_state="SYNCED")
        node = SimpleNamespace(active=active, backend=SimpleNamespace(
            confirm_conveyor_stopped=AsyncMock()), db_writer=writer, pending_requests={}, publish=Mock())
        node.finalize_cancel = MethodType(AssemblySequencer.finalize_cancel, node)
        with patch("assembly_sequencer.sequencer_node.assembly_snapshot", return_value={"active": False}):
            await AssemblySequencer.cancel_before_assembly(node, active)
        writer.finish.assert_called_once_with(JOB_ID, "CANCELLED")
        writer.flush.assert_called_once()
        self.assertIsNone(node.active)

    async def test_same_robot_cancel_reuses_pending_identity(self):
        backend, node = self.backend()
        backend._execution_id = OPERATION_ID
        request = dict(action="assembly.cancel", control_id="existing")
        backend._pending_control = dict(request=request)
        backend.reconcile_control = AsyncMock(return_value={})
        self.assertEqual(await backend.request_control(OPERATION_ID, "cancel"), request)
        node.create_publisher.return_value.publish.assert_not_called()

    def test_control_permissions_match_paused_work_and_db_failure(self):
        backend = Mock()
        node = SimpleNamespace(active=dict(state="PAUSED", backend_started=False),
            db_writer=Mock(sync_state="SYNCED"), backend=backend)
        self.assertEqual(AssemblySequencer.control_reason(node, "cancel"), "")
        self.assertTrue(AssemblySequencer.control_reason(node, "resume"))
        node.active = dict(state="CONVEYOR_MOVING", backend_started=False)
        self.assertEqual(AssemblySequencer.control_reason(node, "cancel"), "")
        self.assertTrue(AssemblySequencer.control_reason(node, "pause"))
        node.active = dict(state="ASSEMBLY_COMPLETED", backend_started=True)
        self.assertEqual(AssemblySequencer.control_reason(node, "cancel"), "")
        self.assertTrue(AssemblySequencer.control_reason(node, "pause"))
        node.db_writer.sync_state = "FAILED"
        self.assertTrue(AssemblySequencer.control_reason(node, "cancel"))
        backend.control_reason.assert_not_called()

    async def test_matching_rejection_releases_control_but_wrong_server_does_not(self):
        backend, _ = self.backend()
        backend._execution_id = OPERATION_ID
        backend._execution_server = "server-a"
        pending = dict(request=dict(action="assembly.pause", control_id="control-a"),
            sent_at=0, rejection=dict(control_id="control-a", message="rejected"))
        backend._pending_control = pending
        data = dict(schema=api_contracts.ASSEMBLY_SCHEMA, execution_id=OPERATION_ID,
            server_instance_id="server-b", status="running")
        backend._read_status = AsyncMock(return_value={"production_contract": data})
        with self.assertRaises(RuntimeError):
            await backend.reconcile_control()
        self.assertIs(backend._pending_control, pending)
        data["server_instance_id"] = "server-a"
        result = await backend.reconcile_control()
        self.assertEqual(result["control_error"], "rejected")
        self.assertIsNone(backend._pending_control)

    async def test_late_reconciliation_cannot_change_replaced_execution(self):
        backend, _ = self.backend()
        backend._execution_id = OPERATION_ID
        backend._execution_server = "server-a"
        newer = {"status": "running", "execution_id": JOB_ID}
        async def replace_execution(client):
            backend._execution_id = JOB_ID
            backend._execution_response = newer
            return {"production_contract": dict(schema=api_contracts.ASSEMBLY_SCHEMA,
                execution_id=OPERATION_ID, server_instance_id="server-a", status="cancelled")}
        backend._read_status = AsyncMock(side_effect=replace_execution)
        with self.assertRaisesRegex(RuntimeError, "Local execution/control changed"):
            await backend.reconcile_control()
        self.assertIs(backend._execution_response, newer)
        self.assertIsNone(backend._control_status)

    def test_cancel_commit_timeout_rechecks_without_resubmitting(self):
        active = dict(job_id=JOB_ID)
        writer = Mock(sync_state="FAILED")
        writer.flush.side_effect = RuntimeError("commit response lost")
        writer.get_job.return_value = dict(job_status="RUNNING", running_quantity=1)
        node = SimpleNamespace(active=active, db_writer=writer, pending_requests={}, publish=Mock())
        AssemblySequencer.finalize_cancel(node, active, "cancel")
        self.assertIs(node.active, active)
        self.assertEqual(active["error_code"], "DB_ERROR")
        writer.get_job.return_value = dict(job_status="CANCELLED", running_quantity=0)
        with patch("assembly_sequencer.sequencer_node.assembly_snapshot", return_value={}):
            AssemblySequencer.finalize_cancel(node, active, "cancel")
        self.assertIsNone(node.active)
        writer.finish.assert_called_once_with(JOB_ID, "CANCELLED")
        node.publish.assert_called_once()

    async def test_periodic_reconciliation_finishes_cancel_without_status_request(self):
        active = dict(job_id=JOB_ID, backend_started=True)
        backend = SimpleNamespace(execution_tracking_stopped=True,
            reconcile_control=AsyncMock(return_value=dict(status="cancelled", stop_verified=True, recovery_required=False)),
            release_cancelled_execution=Mock())
        node = SimpleNamespace(runtime_mode="real", active=active, backend=backend)
        def finish(work, message):
            self.assertIs(work, active)
            node.active = None
        node.finalize_cancel = Mock(side_effect=finish)
        await AssemblySequencer.on_pending_job(node)
        node.finalize_cancel.assert_called_once()
        backend.release_cancelled_execution.assert_called_once()

    def test_real_contracts_are_declarations_without_duplicate_runtime_literals(self):
        import ast
        module = Path(api_contracts.__file__)
        declarations = ast.parse(module.read_text())
        values = []
        for statement in declarations.body[1:]:
            self.assertIsInstance(statement, ast.Assign)
            self.assertIsInstance(statement.value, ast.Constant)
            if isinstance(statement.value.value, str):
                values.append(statement.value.value)
        self.assertEqual(len(values), len(set(values)))
        for path in module.parent.rglob("*.py"):
            if path == module:
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertFalse(any(node.value.startswith(prefix) for prefix in
                        ("/real/", "/conveyor/", "/api/v1/inspections", "fr5.assembly_execution/")),
                        f"Duplicate or legacy API declaration: {path}:{node.lineno}")

    def test_real_backend_has_only_reviewed_imports_and_ros_endpoints(self):
        import ast
        source = Path(sys.modules[RealBackend.__module__].__file__).read_text()
        tree = ast.parse(source)
        allowed_imports = {"hashlib", "http", "json", "math", "os", "threading", "time", "uuid",
                           "urllib", "rclpy", "std_msgs", "std_srvs", "recipe_contract", "copy", "unittest", "pathlib"}
        endpoints = {"/real/robot/status", "/real/assembly/status", "/real/assembly/command",
                     "/real/assembly/event", "/conveyor/state", "/conveyor/move_to_assembly",
                     "/conveyor/move_to_inspection", "/conveyor/stop"}
        for item in ast.walk(tree):
            if isinstance(item, ast.Import):
                for alias in item.names:
                    self.assertIn(alias.name.split(".")[0], allowed_imports)
            elif isinstance(item, ast.ImportFrom):
                if item.module is None:
                    self.assertEqual([(a.name, a.asname) for a in item.names], [("api_contracts", "api")])
                else:
                    self.assertIn(item.module.split(".")[0], allowed_imports)
            elif isinstance(item, ast.Call):
                if isinstance(item.func, ast.Name):
                    self.assertNotIn(item.func.id, {"eval", "exec", "__import__"})
                if isinstance(item.func, ast.Attribute):
                    self.assertNotIn(item.func.attr, {"system", "popen", "execv", "spawnv", "import_module"})
                    if item.func.attr in {"create_client", "create_publisher", "create_subscription"}:
                        self.assertIsInstance(item.args[1], ast.Attribute)
                        self.assertIsInstance(item.args[1].value, ast.Name)
                        self.assertEqual(item.args[1].value.id, "api")
                        self.assertIn(getattr(api_contracts, item.args[1].attr), endpoints)
        for forbidden in ("fairino_remote_command_service", "nonrt_state_data", "MoveJ(", "MoveL(",
                          "MoveGripper(", "SetDO(", "GetDI(", "CARTPoint(", "JNTPoint("):
            self.assertNotIn(forbidden, source)


class MockConveyorTest(unittest.TestCase):
    def test_arrival_timeout_and_wrong_job_cannot_advance_wait(self):
        for timeout in (False,True):
            node=Mock(executor=None)
            backend=MockBackend(node,Mock())
            operation=backend.move_conveyor(JOB_ID,"ASSEMBLY", unit_id=22, operation_id=OPERATION_ID, on_ready=Mock())
            try:
                future=operation.send(None)
                with self.assertRaises(RuntimeError):
                    backend.confirm_conveyor("other-job","ASSEMBLY", unit_id=22, operation_id=OPERATION_ID)
                self.assertFalse(future.done())
                if timeout:
                    node.create_timer.call_args.args[1]()
                    with self.assertRaises(TimeoutError):
                        operation.send(None)
                else:
                    backend.confirm_conveyor(JOB_ID,"ASSEMBLY", unit_id=22, operation_id=OPERATION_ID)
                    backend.confirm_conveyor(JOB_ID,"ASSEMBLY", unit_id=22, operation_id=OPERATION_ID)
                    with self.assertRaises(StopIteration):
                        operation.send(None)
                self.assertIsNone(backend._conveyor_future)
                node.destroy_timer.assert_called_once()
            finally:
                operation.close()

    def test_waiter_exists_before_request_and_rejects_previous_movement(self):
        backend = MockBackend(Mock(executor=None), Mock())
        for unit, operation_id in ((21, JOB_ID), (22, OPERATION_ID)):
            ready = Mock(side_effect=lambda: self.assertIsNotNone(backend._conveyor_future))
            operation = backend.move_conveyor(JOB_ID, "ASSEMBLY", unit_id=unit,
                                              operation_id=operation_id, on_ready=ready)
            try:
                future = operation.send(None)
                ready.assert_called_once()
                if unit == 22:
                    for old_unit, old_operation in ((21, JOB_ID), (22, JOB_ID), (21, OPERATION_ID)):
                        with self.assertRaises(RuntimeError):
                            backend.confirm_conveyor(JOB_ID, "ASSEMBLY", unit_id=old_unit, operation_id=old_operation)
                        with self.assertRaises(RuntimeError):
                            backend.fail_conveyor(JOB_ID, "stale", unit_id=old_unit, operation_id=old_operation)
                        self.assertFalse(future.done())
                backend.confirm_conveyor(JOB_ID, "ASSEMBLY", unit_id=unit, operation_id=operation_id)
                backend.confirm_conveyor(JOB_ID, "ASSEMBLY", unit_id=unit, operation_id=operation_id)
                with self.assertRaises(RuntimeError):
                    backend.fail_conveyor(JOB_ID, "late", unit_id=unit, operation_id=operation_id)
                with self.assertRaises(StopIteration):
                    operation.send(None)
            finally:
                operation.close()

    def test_immediate_arrival_is_not_lost_and_duplicate_preserves_coordinates(self):
        backend = MockBackend(Mock(executor=None), Mock())
        coordinates = {"source": "first", "target": "first"}
        def arrive():
            backend.confirm_conveyor(JOB_ID, "INSPECTION", unit_id=22,
                                     operation_id=OPERATION_ID, assembled_pcb=coordinates)
            backend.confirm_conveyor(JOB_ID, "INSPECTION", unit_id=22,
                                     operation_id=OPERATION_ID, assembled_pcb={"source": "replacement"})
        operation = backend.move_conveyor(JOB_ID, "INSPECTION", unit_id=22,
                                          operation_id=OPERATION_ID, on_ready=arrive)
        try:
            with self.assertRaises(StopIteration):
                operation.send(None)
            self.assertEqual(backend._assembled_pcb, coordinates)
            self.assertIsNone(backend._conveyor_future)
        finally:
            operation.close()

    def test_timeout_or_failure_cannot_be_reversed_by_late_arrival(self):
        for timeout in (True, False):
            node = Mock(executor=None)
            backend = MockBackend(node, Mock())
            operation = backend.move_conveyor(JOB_ID, "INSPECTION", unit_id=22,
                                              operation_id=OPERATION_ID, on_ready=Mock())
            try:
                operation.send(None)
                if timeout:
                    node.create_timer.call_args.args[1]()
                    with self.assertRaises(RuntimeError):
                        backend.fail_conveyor(JOB_ID, "late failure", unit_id=22, operation_id=OPERATION_ID)
                else:
                    backend.fail_conveyor(JOB_ID, "stopped", unit_id=22, operation_id=OPERATION_ID)
                with self.assertRaises(RuntimeError):
                    backend.confirm_conveyor(JOB_ID, "INSPECTION", unit_id=22,
                                             operation_id=OPERATION_ID, assembled_pcb={"old": "pose"})
                self.assertIsNone(backend._assembled_pcb)
                with self.assertRaises(TimeoutError if timeout else RuntimeError):
                    operation.send(None)
            finally:
                operation.close()

    def test_concurrent_timeout_cannot_be_overwritten_by_arrival(self):
        node = Mock(executor=None)
        backend = MockBackend(node, Mock())
        operation = backend.move_conveyor(JOB_ID, "ASSEMBLY", unit_id=22,
                                          operation_id=OPERATION_ID, on_ready=Mock())
        entered, release, attempted = threading.Event(), threading.Event(), threading.Event()
        errors = []
        future = operation.send(None)
        cancel = future.cancel
        def delayed_cancel():
            entered.set()
            release.wait(2)
            cancel()
        def arrive():
            attempted.set()
            try:
                backend.confirm_conveyor(JOB_ID, "ASSEMBLY", unit_id=22, operation_id=OPERATION_ID)
            except RuntimeError as error:
                errors.append(str(error))
        future.cancel = delayed_cancel
        timer = threading.Thread(target=node.create_timer.call_args.args[1])
        arrival = threading.Thread(target=arrive)
        try:
            timer.start()
            self.assertTrue(entered.wait(1))
            arrival.start()
            self.assertTrue(attempted.wait(1))
            release.set()
            timer.join(2)
            arrival.join(2)
            self.assertFalse(timer.is_alive())
            self.assertFalse(arrival.is_alive())
            self.assertTrue(future.cancelled())
            self.assertEqual(len(errors), 1)
            with self.assertRaises(TimeoutError):
                operation.send(None)
        finally:
            release.set()
            timer.join(2)
            if arrival.ident is not None:
                arrival.join(2)
            operation.close()

    def test_mock_inspection_boundaries(self):
        self.assertEqual(choose_inspection(random.Random(1),0,[]),("PASS",[]))
        result,defects=choose_inspection(random.Random(1),1,["SLOT"])
        self.assertEqual(result,"FAIL")
        self.assertEqual(defects[0]["slot_code"],"SLOT")


if __name__ == "__main__":
    unittest.main()
