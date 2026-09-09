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
            self.assertIsNone(node.recipe_version)
            load.assert_not_called()
            parameter.assert_not_called()

    async def test_retired_motion_api_has_no_publishers_or_subscriptions(self):
        backend, node = self.backend()
        for method in ("prepare", "start", "move_joint", "pick", "place", "_execute",
                       "resolve_targets", "transfer_assembled_pcb", "set_paused", "accept_operation_feedback"):
            self.assertFalse(hasattr(backend, method), method)
        node.create_client.return_value.call_async.assert_not_called()
        node.create_publisher.assert_not_called()
        node.create_subscription.assert_not_called()
        self.assertEqual(node.create_client.call_args.args[1], "/real/robot/status")

    async def test_real_start_and_pending_poll_never_claim_without_cycle_contract(self):
        backend, node = self.backend()
        sequencer = SimpleNamespace(runtime_mode="real", recipe=None, recipe_version=None,
            backend=backend, active=None, db_writer=Mock(), set_response=AssemblySequencer.set_response)
        command = dict(command="start", job_id=JOB_ID, recipe_version="robot-owned-r2")
        response = await AssemblySequencer.on_external_request(sequencer,
            SimpleNamespace(cmd_str="real\n" + json.dumps(command)), SimpleNamespace())
        self.assertEqual(json.loads(response.cmd_res)["error_code"], "NOT_READY")
        response = await AssemblySequencer.start_job(sequencer, command, SimpleNamespace())
        self.assertEqual(json.loads(response.cmd_res)["error_code"], "NOT_READY")
        await AssemblySequencer.on_pending_job(sequencer)
        self.assertEqual(sequencer.db_writer.mock_calls, [])
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

    def test_wrong_mode_is_rejected_before_any_ros_connections(self):
        for mode, domain in (("mock",42),("real",42),("mock",5),("real",43)):
            node = Mock(runtime_mode=mode)
            node.context.get_domain_id.return_value = domain
            with self.assertRaisesRegex(RuntimeError, "MODE_REJECTED"):
                RealBackend(node)
            node.create_client.assert_not_called()
            node.create_publisher.assert_not_called()

    def test_real_backend_has_only_reviewed_imports_and_ros_endpoints(self):
        import ast
        source = Path(sys.modules[RealBackend.__module__].__file__).read_text()
        tree = ast.parse(source)
        allowed_imports = {"hashlib", "http", "json", "math", "os", "threading", "time", "uuid",
                           "urllib", "rclpy", "std_msgs", "std_srvs", "recipe_contract", "copy", "unittest"}
        endpoints = {"/real/robot/status"}
        for item in ast.walk(tree):
            if isinstance(item, ast.Import):
                for alias in item.names:
                    self.assertIn(alias.name.split(".")[0], allowed_imports)
            elif isinstance(item, ast.ImportFrom):
                self.assertIn(item.module.split(".")[0], allowed_imports)
            elif isinstance(item, ast.Call):
                if isinstance(item.func, ast.Name):
                    self.assertNotIn(item.func.id, {"eval", "exec", "__import__"})
                if isinstance(item.func, ast.Attribute):
                    self.assertNotIn(item.func.attr, {"system", "popen", "execv", "spawnv", "import_module"})
                    if item.func.attr in {"create_client", "create_publisher", "create_subscription"}:
                        self.assertIsInstance(item.args[1], ast.Constant)
                        self.assertIn(item.args[1].value, endpoints)
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
