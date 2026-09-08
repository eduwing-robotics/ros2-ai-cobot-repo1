"""Checks for DB retry and YAML-driven Mock workflow gates."""

import asyncio
import os
import json
import random
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace, MethodType
from unittest.mock import AsyncMock, Mock, patch

import psycopg


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assembly_sequencer.db import DbQueueFull, DbWriter
from assembly_sequencer.mock_backend import MockBackend, choose_inspection
from assembly_sequencer.sequencer_node import AssemblySequencer
from assembly_sequencer.recipe_contract import assembly_snapshot, load_recipe, resolve_observations, parse_command
from assembly_sequencer.db import production_store as store
from assembly_sequencer.real_backend import RealBackend


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
                      conveyor_confirmed=False, transfer_requested=False,
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
        sequencer.run_transfer_workflow = MethodType(AssemblySequencer.run_transfer_workflow, sequencer)
        return sequencer, active

    async def test_recipe_workflow_waits_for_conveyor_then_follows_yaml(self):
        sequencer, active = self.fixture()
        arrived = asyncio.Event()
        async def conveyor(job, station):
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
        sequencer.finish_active_unit.assert_called_once_with(active)

    async def test_before_all_action_order_comes_from_recipe(self):
        sequencer, active = self.fixture()
        sequencer.recipe["workflow"]["before_all"].reverse()
        await AssemblySequencer.run_assembly_workflow(sequencer, active)
        self.assertEqual([c[0] for c in sequencer.backend.mock_calls[:3]],
                         ["resolve_targets", "move_conveyor", "start"])
        sequencer.fail_active.assert_not_called()

    async def test_inspection_precedes_transfer_and_db_failure_blocks_it(self):
        sequencer, active = self.fixture()
        inspection_arrived = asyncio.Event()
        sequencer.backend.move_conveyor.side_effect = lambda *args: None
        async def wait_arrival(*args):
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
            response = await AssemblySequencer.conveyor_arrived(sequencer, {"job_id":JOB_ID}, SimpleNamespace())
            self.assertTrue(json.loads(response.cmd_res)["accepted"])
        sequencer.backend.confirm_conveyor.assert_called_once_with(JOB_ID, "ASSEMBLY")
        self.assertTrue(active["conveyor_confirmed"])

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


class RealReadinessTest(unittest.IsolatedAsyncioTestCase):
    async def test_live_state_does_not_override_unconnected_equipment_contracts(self):
        node = Mock(runtime_mode="real", executor=None)
        node.context.get_domain_id.return_value = 43
        backend = RealBackend(node)
        self.addCleanup(backend.close)
        backend._on_state(SimpleNamespace(reconnect_flag=0, emg=0, abnormal_stop=0,
            alarm=0, main_error_code=0, sub_error_code=0, gripperfaultnum=0,
            grippererro=0, safetydoor_alarm=0, safetyplanealarm=0))
        snapshot = await backend.status()
        self.assertFalse(snapshot["available"])
        self.assertFalse(snapshot["equipment_ready"])
        self.assertTrue(snapshot["robot_state_fresh"])
        with self.assertRaisesRegex(RuntimeError, "NOT_READY"):
            await backend.prepare({"home": [0] * 6}, "base_link")
        with self.assertRaisesRegex(RuntimeError, "NOT_READY"):
            await backend.move_joint(JOB_ID, [0] * 6)
        node.create_client.return_value.call_async.assert_not_called()
        node.create_client.return_value.call.assert_not_called()

    def test_real_backend_rejects_mock_process_before_ros_connections(self):
        for mode, domain in (("mock", 42), ("real", 42), ("mock", 43)):
            node = Mock(runtime_mode=mode)
            node.context.get_domain_id.return_value = domain
            with self.assertRaisesRegex(RuntimeError, "MODE_REJECTED"):
                RealBackend(node)
            node.create_client.assert_not_called()
            node.create_subscription.assert_not_called()


class RealMotionTest(unittest.IsolatedAsyncioTestCase):
    def backend(self):
        backend = RealBackend.__new__(RealBackend)
        backend._require_ready = Mock()
        backend._command = AsyncMock(return_value=[])
        backend._delay = AsyncMock()
        backend._operation_active = False
        backend._conveyor_active = False
        backend._prepared = True
        backend._node = Mock()
        backend._motion_speed = 20
        backend._tool = 0
        backend._user = 0
        backend._gripper_speed = 50
        backend._gripper_force = 30
        backend._state = SimpleNamespace(gripper_feedback_valid=False, gripper_position=0)
        return backend

    async def test_joint_motion_waits_for_target_even_if_done_was_stale(self):
        backend = self.backend()
        backend._command.side_effect = [[], [], [1], [0]*6, [0], [10]*6, [1], [10]*6]
        await backend.move_joint(JOB_ID, [10]*6)
        commands = [call.args[0] for call in backend._command.call_args_list]
        self.assertTrue(commands[0].startswith("JNTPoint(1,10.000000"))
        self.assertEqual(commands[1], "MoveJ(JNT1,20,0,0)")
        self.assertEqual(commands.count("GetRobotMotionDone()"), 3)
        self.assertEqual(backend._delay.await_count, 2)

    async def test_pick_uses_recipe_distances_and_gripper_profile_in_order(self):
        backend = self.backend()
        calls = []
        async def move(target): calls.append(("move", target[2]))
        async def grip(opening): calls.append(("grip", opening))
        backend._move = move
        backend._grip = grip
        await backend.pick(JOB_ID, {}, "base_link", {"xyz_mm": [10,20,30], "xyzw": [0,0,0,1]},
                           {"approach_dz_mm": 80, "retract_dz_mm": 90},
                           {"release_opening_percent": 25, "grasp_opening_percent": 18})
        self.assertEqual(calls, [("move",110),("grip",25),("move",30),("grip",18),("move",120)])

    async def test_gripper_does_not_accept_previous_done_flag(self):
        backend = self.backend()
        backend._command.side_effect = [[], [0,1], [0,0], [0,1]]
        await backend._grip(18)
        self.assertEqual(backend._command.await_count, 4)
        self.assertEqual(backend._delay.await_count, 2)
        self.assertEqual(backend._command.call_args_list[0].args[0], "MoveGripper(1,18,50,30,3000,1)")

    async def test_uncertain_motion_stops_without_retry_or_next_step(self):
        backend = self.backend()
        backend._move = AsyncMock(side_effect=TimeoutError("response lost"))
        backend._grip = AsyncMock()
        with self.assertRaisesRegex(RuntimeError, "SAFETY_STOP"):
            await backend.pick(JOB_ID, {}, "base_link", {"xyz_mm": [0,0,0], "xyzw": [0,0,0,1]},
                               {"approach_dz_mm": 80, "retract_dz_mm": 90},
                               {"release_opening_percent": 25, "grasp_opening_percent": 18})
        backend._move.assert_awaited_once()
        backend._grip.assert_not_awaited()
        backend._command.assert_awaited_once_with("StopMotion()")
        self.assertFalse(backend._prepared)
        self.assertFalse(backend._operation_active)

    async def test_transfer_validates_destination_before_pick_and_uses_drop_height(self):
        backend = self.backend()
        backend.pick = AsyncMock()
        backend.place = AsyncMock()
        pose = {"xyz_mm": [10,20,30], "xyzw": [0,0,0,1]}
        motion = {"approach_dz_mm": 100, "retract_dz_mm": 100,
                  "assembled_pcb_drop_approach_dz_mm": 150}
        with self.assertRaises(ValueError):
            await backend.transfer_assembled_pcb(JOB_ID, "base_link", {"source": pose, "target": {}}, motion, {})
        backend.pick.assert_not_awaited()
        await backend.transfer_assembled_pcb(JOB_ID, "base_link", {"source": pose, "target": pose}, motion, {})
        self.assertEqual(backend.place.call_args.args[4]["approach_dz_mm"], 150)
        self.assertEqual(motion["approach_dz_mm"], 100)

    def test_tcp_conversion_preserves_mm_and_converts_quaternion_to_degrees(self):
        pose = {"xyz_mm": [100,200,300], "xyzw": [0,0,2**-0.5,2**-0.5]}
        target = RealBackend._tcp_pose(pose, "base_link", 100)
        self.assertEqual(target[:3], [100,200,400])
        self.assertAlmostEqual(target[5], 90)
        with self.assertRaises(ValueError):
            RealBackend._tcp_pose(pose, "unity")

    def test_safety_stop_preserves_active_unit_without_db_finalization(self):
        node = SimpleNamespace(runtime_mode="real", active={"job_id": JOB_ID, "state": "STARTED"},
                               db_writer=Mock(sync_state="SYNCED"), publish=Mock(), fail_job=Mock())
        AssemblySequencer.fail_active(node, "INTERNAL_ERROR", RuntimeError("SAFETY_STOP: timeout"))
        self.assertEqual(node.active["state"], "PAUSED")
        node.fail_job.assert_not_called()
        node.db_writer.finish.assert_not_called()
        self.assertEqual(node.publish.call_args.args[0]["error_code"], "SAFETY_STOP")

    async def test_conveyor_waits_for_arrival_then_turns_off_drive(self):
        backend = self.backend()
        backend._conveyor_do = 2
        backend._arrival_di = {"ASSEMBLY": 3}
        backend._drive_level = 1
        backend._arrival_level = 1
        backend._command.side_effect = [[0], [], [0], [1], []]
        await backend.move_conveyor(JOB_ID, "ASSEMBLY")
        self.assertEqual([call.args[0] for call in backend._command.call_args_list],
                         ["GetDI(3,1)", "SetDO(2,1,0,1)", "GetDI(3,1)", "GetDI(3,1)", "SetDO(2,0,0,1)"])
        self.assertFalse(backend._conveyor_active)

    async def test_conveyor_rejects_missing_io_without_sending_commands(self):
        backend = self.backend()
        backend._conveyor_do = -1
        backend._arrival_di = {"ASSEMBLY": -1}
        with self.assertRaisesRegex(RuntimeError, "NOT_READY"):
            await backend.move_conveyor(JOB_ID, "ASSEMBLY")
        backend._command.assert_not_awaited()

    async def test_command_prefix_and_sdk_error_handling(self):
        backend = RealBackend.__new__(RealBackend)
        backend._closed = False
        backend._pending_calls = set()
        backend._node = Mock()
        backend._client = Mock()
        backend.is_available = Mock(return_value=True)
        future = asyncio.get_running_loop().create_future()
        future.set_result(SimpleNamespace(cmd_res="0,1"))
        backend._client.call_async.return_value = future
        self.assertEqual(await backend._command("GetRobotMotionDone()", 1), [1])
        self.assertEqual(backend._client.call_async.call_args.args[0].cmd_str, "real\nGetRobotMotionDone()")
        future = asyncio.get_running_loop().create_future()
        future.set_result(SimpleNamespace(cmd_res="-4,1"))
        backend._client.call_async.return_value = future
        with self.assertRaisesRegex(RuntimeError, "failed"):
            await backend._command("GetRobotMotionDone()", 1)
        self.assertFalse(backend._pending_calls)


class MockConveyorTest(unittest.TestCase):
    def test_arrival_timeout_and_wrong_job_cannot_advance_wait(self):
        for timeout in (False,True):
            node=Mock(executor=None)
            backend=MockBackend(node,Mock())
            operation=backend.move_conveyor(JOB_ID,"ASSEMBLY")
            try:
                future=operation.send(None)
                with self.assertRaises(RuntimeError):
                    backend.confirm_conveyor("other-job","ASSEMBLY")
                self.assertFalse(future.done())
                if timeout:
                    node.create_timer.call_args.args[1]()
                    with self.assertRaises(TimeoutError):
                        operation.send(None)
                else:
                    backend.confirm_conveyor(JOB_ID,"ASSEMBLY")
                    backend.confirm_conveyor(JOB_ID,"ASSEMBLY")
                    with self.assertRaises(StopIteration):
                        operation.send(None)
                self.assertIsNone(backend._conveyor_future)
                node.destroy_timer.assert_called_once()
            finally:
                operation.close()

    def test_mock_inspection_boundaries(self):
        self.assertEqual(choose_inspection(random.Random(1),0,[]),("PASS",[]))
        result,defects=choose_inspection(random.Random(1),1,["SLOT"])
        self.assertEqual(result,"FAIL")
        self.assertEqual(defects[0]["slot_code"],"SLOT")


if __name__ == "__main__":
    unittest.main()
