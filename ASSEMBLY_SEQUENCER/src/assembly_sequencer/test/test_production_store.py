"""Integration checks for the UUID Job and Unit-attempt lifecycle."""

import os
import copy
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch
import sys
import unittest
import uuid
from pathlib import Path

import psycopg


TEST_DSN = os.environ.get("PRODUCTION_DB_TEST_DSN")
if not TEST_DSN or not TEST_DSN.strip():
    raise RuntimeError("PRODUCTION_DB_TEST_DSN is required")
with psycopg.connect(TEST_DSN) as test_connection:
    test_database = test_connection.execute("SELECT current_database()").fetchone()[0]
if not test_database.endswith("_test"):
    raise RuntimeError("PRODUCTION_DB_TEST_DSN must target a database ending in _test")
os.environ["PRODUCTION_DB_DSN"] = TEST_DSN
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assembly_sequencer.db import DbWriter
from assembly_sequencer.db import production_store as store


class ProductionStoreIntegrationTest(unittest.TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex
        self.product_code = "__MDB_TEST_PRODUCT_" + suffix
        self.product_version = "test-v1"
        self.part_id = "__MDB_TEST_PART_" + suffix
        with psycopg.connect(TEST_DSN) as connection:
            self.product_id = connection.execute(
                """
                INSERT INTO production.products (
                    product_code, product_name, product_version
                ) VALUES (%s, 'test product', %s)
                RETURNING product_id
                """,
                (self.product_code, self.product_version),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO production.parts (
                    part_id, part_name, part_category, stock_quantity
                ) VALUES (%s, 'test part', 'TEST', 8)
                """,
                (self.part_id,),
            )
            connection.execute(
                """
                INSERT INTO production.inventory_movements (
                    part_id, quantity_delta, movement_type, reason
                ) VALUES (%s, 8, 'OPENING', 'TEST_SETUP')
                """,
                (self.part_id,),
            )
            connection.execute(
                """
                INSERT INTO production.product_slots (product_id, slot_code, part_id)
                VALUES (%s, 'SLOT-A-01', %s), (%s, 'SLOT-A-02', %s)
                """,
                (self.product_id, self.part_id, self.product_id, self.part_id),
            )

    def tearDown(self):
        with psycopg.connect(TEST_DSN) as connection:
            connection.execute(
                """
                DELETE FROM production.unit_defects ud
                USING production.units u
                WHERE ud.unit_id = u.unit_id AND u.job_id IN (
                    SELECT job_id FROM production.jobs WHERE product_id = %s
                )
                """,
                (self.product_id,),
            )
            connection.execute(
                "DELETE FROM production.inventory_movements WHERE part_id = %s",
                (self.part_id,),
            )
            connection.execute(
                """
                DELETE FROM production.units WHERE job_id IN (
                    SELECT job_id FROM production.jobs WHERE product_id = %s
                )
                """,
                (self.product_id,),
            )
            connection.execute(
                "DELETE FROM production.jobs WHERE product_id = %s",
                (self.product_id,),
            )
            connection.execute(
                "DELETE FROM production.product_slots WHERE product_id = %s",
                (self.product_id,),
            )
            connection.execute(
                "DELETE FROM production.products WHERE product_id = %s",
                (self.product_id,),
            )
            connection.execute(
                "DELETE FROM production.parts WHERE part_id = %s",
                (self.part_id,),
            )

    def create_job(self, quantity=1):
        job_id = str(uuid.uuid4())
        with psycopg.connect(TEST_DSN) as connection:
            connection.execute(
                """
                INSERT INTO production.jobs (
                    job_id, product_id, requested_quantity, recipe_version
                ) VALUES (%s, %s, %s, 'assembly-r1')
                """,
                (job_id, self.product_id, quantity),
            )
        return job_id

    def claim(self, job_id):
        return store.claim_job(
            job_id, self.product_code, self.product_version, "assembly-r1"
        )

    def scalar(self, query, parameters):
        with psycopg.connect(TEST_DSN) as connection:
            return connection.execute(query, parameters).fetchone()[0]

    def complete(self, unit_id, result="PASS", defects=()):
        store.complete_assembly_and_consume_stock(unit_id)
        store.record_inspection(unit_id, result, defects)
        store.complete_unit(unit_id)

    def test_vision_slot_storage_replay_and_evidence_integrity(self):
        with psycopg.connect(TEST_DSN) as connection:
            connection.execute("UPDATE production.parts SET stock_quantity=100 WHERE part_id=%s", (self.part_id,))
            for number in range(3, 26):
                connection.execute("""INSERT INTO production.product_slots (product_id, slot_code, part_id)
                    VALUES (%s, %s, %s)""", (self.product_id, f"SLOT-{number:02}", self.part_id))
        job_id = self.create_job()
        unit_id = self.claim(job_id)["unit_id"]
        store.complete_assembly_and_consume_stock(unit_id)
        with psycopg.connect(TEST_DSN) as connection:
            rows = connection.execute("SELECT slot_code FROM production.product_slots WHERE product_id=%s",
                                      (self.product_id,)).fetchall()
        png = b"\x89PNG\r\n\x1a\nfixture"
        data = {
            "inspection_id": str(uuid.uuid4()), "job_id": job_id, "unit_id": unit_id,
            "status": "COMPLETED",
            "result": {"decision": "UNKNOWN", "inspected_at": datetime.now(timezone.utc).isoformat(),
                       "slots": [{"slot_code": row[0], "part_id": self.part_id, "decision": "UNKNOWN"} for row in rows],
                       "findings": [], "defects": []},
            "image": {"ready": True, "size_bytes": len(png), "sha256": hashlib.sha256(png).hexdigest()},
        }
        connect = store._connect
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"DEFECT_IMAGE_ROOT": root}), \
                patch.object(store, "_connect", lambda **kwargs: connect()):
            def save(payload=data, image=png):
                return store.record_inspection(unit_id, payload["result"]["decision"], None,
                                               inspection=payload, image_bytes=image)
            with self.assertRaisesRegex(ValueError, "SHA256"):
                save(image=png + b"corrupt")
            bad = copy.deepcopy(data)
            bad["result"]["slots"].pop()
            with self.assertRaisesRegex(ValueError, "exactly match"):
                save(bad)
            replace = os.replace
            def fail_mapping(source, target):
                if str(target).endswith("result.json"):
                    raise OSError("simulated disk failure")
                return replace(source, target)
            with patch.object(os, "replace", fail_mapping), self.assertRaisesRegex(OSError, "disk failure"):
                save()
            self.assertEqual(self.scalar("SELECT COUNT(*) FROM production.unit_defects WHERE unit_id=%s", (unit_id,)), 0)
            links = save()
            self.assertEqual(len(links), 25)
            self.assertEqual(save(), links)
            archived = Path(root) / "inspections" / str(unit_id) / "result.json"
            self.assertEqual(json.loads(archived.read_text())["unit_defects"], links)
            self.assertEqual(self.scalar("SELECT unit_status FROM production.units WHERE unit_id=%s", (unit_id,)), "RUNNING")
            self.assertEqual(self.scalar("SELECT COUNT(*) FROM production.unit_defects WHERE unit_id=%s AND defect_type IS NOT NULL", (unit_id,)), 0)
            self.assertEqual(self.scalar("SELECT COUNT(*) FROM production.defect_report_deliveries d JOIN production.unit_defects u USING(unit_defect_id) WHERE u.unit_id=%s", (unit_id,)), 0)
            changed = copy.deepcopy(data)
            changed["inspection_id"] = str(uuid.uuid4())
            with self.assertRaisesRegex(RuntimeError, "different Vision data"):
                save(changed)
            archived.unlink()
            self.assertEqual(save(), links)
            sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "MAIN_SERVER"))
            import queries
            with patch.dict(os.environ, {"MAIN_SERVER_MODE": "mock", "MAIN_SERVER_DB_DSN": TEST_DSN}):
                fetched = queries.units(job_id)[0]
                self.assertEqual(len(fetched["inspection"]["result"]["slots"]), 25)
                self.assertEqual(fetched["defects"], [])
                self.assertEqual(queries.inspection_image(unit_id), png)
                self.assertTrue(all(r["defective_quantity"] == 0 and r["inspected_quantity"] == 0
                                    for r in queries.slot_rates(self.product_id)))
                archived.write_text(json.dumps({"data": data, "unit_defects": []}))
                self.assertIsNotNone(queries.units(job_id)[0]["inspection_error"])
                save()
                (archived.parent / "02_annotated_report.png").write_bytes(png + b"corrupt")
                with self.assertRaises(queries.InspectionUnavailable):
                    queries.inspection_image(unit_id)
                save()
            store.finish_job(job_id, "FAILED")
            for verdict, ready in (("PASS", True), ("FAIL", True), ("UNKNOWN", False)):
                new_job = self.create_job()
                new_unit = self.claim(new_job)["unit_id"]
                store.complete_assembly_and_consume_stock(new_unit)
                payload = copy.deepcopy(data)
                payload.update(inspection_id=str(uuid.uuid4()), job_id=new_job, unit_id=new_unit)
                payload["result"].update(decision=verdict, inspected_at=datetime.now(timezone.utc).isoformat())
                for slot in payload["result"]["slots"]:
                    slot["decision"] = "PASS" if verdict == "PASS" else "UNKNOWN"
                if verdict == "FAIL":
                    slot_code = payload["result"]["slots"][0]["slot_code"]
                    payload["result"]["slots"][0]["decision"] = "FAIL"
                    payload["result"]["defects"] = [{"slot_code": slot_code}]
                    payload["result"]["findings"] = [{"slot_code": slot_code, "confirmed_defect": True,
                        "authority": "AUTHORITATIVE", "primary_defect_code": "SEATING_ERROR"}]
                if not ready:
                    payload["image"] = {"ready": False}
                def persist():
                    return store.record_inspection(new_unit, verdict, None, inspection=payload,
                                                   image_bytes=png if ready else None)
                self.assertEqual(len(persist()), 25)
                self.assertEqual(len(persist()), 25)
                self.assertEqual(self.scalar("SELECT COUNT(*) FROM production.unit_defects WHERE unit_id=%s AND defect_type IS NOT NULL", (new_unit,)), int(verdict == "FAIL"))
                self.assertEqual(self.scalar("SELECT COUNT(*) FROM production.defect_report_deliveries d JOIN production.unit_defects u USING(unit_defect_id) WHERE u.unit_id=%s", (new_unit,)), int(verdict == "FAIL"))
                store.finish_job(new_job, "FAILED")

    def test_inspected_pass_is_not_complete_until_transfer_finishes(self):
        job_id = self.create_job()
        unit_id = self.claim(job_id)["unit_id"]
        with self.assertRaisesRegex(RuntimeError, "confirmed inspection"):
            store.complete_unit(unit_id)
        store.complete_assembly_and_consume_stock(unit_id)
        store.record_inspection(unit_id, "PASS", [])
        self.assertEqual(store.get_job_state(job_id)["completed_quantity"], 0)
        with self.assertRaisesRegex(RuntimeError, "requested PASS"):
            store.finish_job(job_id, "COMPLETED")
        store.complete_unit(unit_id)
        store.complete_unit(unit_id)
        self.assertEqual(store.get_job_state(job_id)["completed_quantity"], 1)
        store.finish_job(job_id, "COMPLETED")

    def test_transfer_failure_preserves_inspection_without_counting_pass(self):
        job_id = self.create_job()
        unit_id = self.claim(job_id)["unit_id"]
        store.complete_assembly_and_consume_stock(unit_id)
        store.record_inspection(unit_id, "PASS", [])
        store.recover_interrupted_units()
        self.assertEqual(store.get_job_state(job_id)["completed_quantity"], 0)
        self.assertEqual(self.scalar(
            "SELECT unit_status FROM production.units WHERE unit_id=%s", (unit_id,)), "FAILED")
        self.assertEqual(self.scalar(
            "SELECT inspection_result FROM production.units WHERE unit_id=%s", (unit_id,)), "PASS")
        with self.assertRaisesRegex(RuntimeError, "must be running"):
            store.complete_unit(unit_id)
        self.claim(job_id)

    def test_main_server_pass_progress_requires_workflow_completion(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "MAIN_SERVER"))
        import queries

        job_id = self.create_job()
        unit_id = self.claim(job_id)["unit_id"]
        store.complete_assembly_and_consume_stock(unit_id)
        store.record_inspection(unit_id, "PASS", [])
        with patch.dict(os.environ, {"MAIN_SERVER_MODE": "mock", "MAIN_SERVER_DB_DSN": TEST_DSN}):
            for completed in (False, True):
                if completed:
                    store.complete_unit(unit_id)
                detail = queries.job(job_id)
                listing = next(row for row in queries.jobs() if str(row["job_id"]) == job_id)
                for row in (detail, listing):
                    self.assertEqual(row["completed_quantity"], int(completed))
                    self.assertEqual(row["progress_percent"], 100 if completed else 0)

    def test_failed_inspected_unit_remains_visible_to_quality_readers(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "MAIN_SERVER"))
        import queries
        import generate_defect_reports

        job_id = self.create_job()
        unit_id = self.claim(job_id)["unit_id"]
        store.complete_assembly_and_consume_stock(unit_id)
        store.record_inspection(unit_id, "FAIL", [
            {"slot_code": "SLOT-A-01", "defect_type": "MISSING"}
        ])
        defect_id = self.scalar(
            "SELECT unit_defect_id FROM production.unit_defects WHERE unit_id=%s", (unit_id,))
        with patch.dict(os.environ, {"MAIN_SERVER_MODE": "mock", "MAIN_SERVER_DB_DSN": TEST_DSN}):
            for failed in (False, True):
                if failed:
                    store.finish_job(job_id, "FAILED")
                self.assertEqual(queries.job(job_id)["completed_quantity"], 0)
                self.assertIn(defect_id, [row["unit_defect_id"] for row in queries.defect_reports()])
                context = generate_defect_reports.load_defect_context(TEST_DSN, defect_id)
                self.assertEqual(context[0]["target_unit_id"], unit_id)
                self.assertEqual(context[0]["inspected_units"], 1)

    def test_ready_pending_job_bypasses_unprepared_older_job(self):
        older = self.create_job()
        ready = self.create_job()
        args = (self.product_code, self.product_version, "assembly-r1")
        self.assertIsNone(store.get_next_runnable_job(*args, ready_job_ids=[]))
        self.assertEqual(store.get_next_runnable_job(*args, ready_job_ids=[ready])["job_id"], ready)
        self.claim(older)
        self.assertIsNone(store.get_next_runnable_job(*args, ready_job_ids=[ready]))
        store.recover_interrupted_units()
        self.assertEqual(store.get_next_runnable_job(*args, ready_job_ids=[ready])["job_id"], older)

    def test_requested_quantity_pass_target_finishes_job(self):
        job_id = self.create_job(quantity=2)
        first = self.claim(job_id)
        self.complete(first["unit_id"])
        second = self.claim(job_id)
        self.complete(second["unit_id"])
        store.finish_job(job_id, "COMPLETED")

        state = store.get_job_state(job_id)
        self.assertEqual(state["job_id"], job_id)
        self.assertEqual(state["job_status"], "COMPLETED")
        self.assertEqual(state["completed_quantity"], 2)
        self.assertEqual(
            self.scalar(
                "SELECT stock_quantity FROM production.parts WHERE part_id = %s",
                (self.part_id,),
            ),
            4,
        )
        store.complete_assembly_and_consume_stock(first["unit_id"])
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM production.inventory_movements WHERE unit_id = %s",
                (first["unit_id"],),
            ),
            1,
        )

    def test_failed_inspection_creates_replacement_attempt(self):
        job_id = self.create_job()
        first = self.claim(job_id)
        self.complete(first["unit_id"], "FAIL", ({
            "slot_code": "SLOT-A-01", "defect_type": "MISSING"
        },))
        self.assertEqual(
            self.scalar(
                """
                SELECT COUNT(*)
                FROM production.defect_report_deliveries delivery
                JOIN production.unit_defects defect USING (unit_defect_id)
                WHERE defect.unit_id = %s AND delivery.delivery_status = 'PENDING'
                """,
                (first["unit_id"],),
            ),
            1,
        )
        with self.assertRaisesRegex(RuntimeError, "PASS quantity"):
            store.finish_job(job_id, "COMPLETED")

        self.assertEqual(store.get_job_state(job_id)["job_status"], "PAUSED")
        self.assertEqual(store.get_quality_hold()["unit_id"], first["unit_id"])
        with self.assertRaises(RuntimeError):
            self.claim(job_id)
        queued = self.create_job()
        self.assertIsNone(store.get_next_runnable_job(self.product_code, self.product_version, "assembly-r1", [queued]))
        store.recover_interrupted_units()
        self.assertEqual(store.get_job_state(job_id)["job_status"], "PAUSED")
        with psycopg.connect(TEST_DSN) as connection:
            connection.execute("UPDATE production.parts SET stock_quantity=0 WHERE part_id=%s", (self.part_id,))
        with self.assertRaisesRegex(RuntimeError, "insufficient stock"):
            store.resume_quality_job(job_id)
        self.assertEqual(store.get_job_state(job_id)["job_status"], "PAUSED")
        with psycopg.connect(TEST_DSN) as connection:
            connection.execute("UPDATE production.parts SET stock_quantity=6 WHERE part_id=%s", (self.part_id,))
        store.resume_quality_job(job_id)
        with self.assertRaises(RuntimeError):
            store.resume_quality_job(job_id)
        second = self.claim(job_id)
        self.assertNotEqual(first["unit_id"], second["unit_id"])
        self.complete(second["unit_id"])
        store.finish_job(job_id, "COMPLETED")

        state = store.get_job_state(job_id)
        self.assertEqual(state["completed_quantity"], 1)
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM production.units WHERE job_id = %s",
                (job_id,),
            ),
            2,
        )

    def test_runnable_job_respects_queue_and_active_job(self):
        first_job_id = self.create_job()
        second_job_id = self.create_job()
        with psycopg.connect(TEST_DSN) as connection:
            connection.execute(
                "UPDATE production.jobs SET requested_at = now() - interval '1 minute' WHERE job_id = %s",
                (first_job_id,),
            )

        self.assertEqual(
            store.get_next_runnable_job(
                self.product_code, self.product_version, "assembly-r1"
            )["job_id"],
            first_job_id,
        )
        self.claim(first_job_id)
        self.assertIsNone(store.get_next_runnable_job(
            self.product_code, self.product_version, "assembly-r1"
        ))
        store.recover_interrupted_units()
        self.assertEqual(
            store.get_next_runnable_job(
                self.product_code, self.product_version, "assembly-r1"
            )["job_id"],
            first_job_id,
        )
        store.finish_job(first_job_id, "FAILED")
        store.finish_job(second_job_id, "CANCELLED")

    def test_restart_fails_only_running_unit(self):
        job_id = self.create_job()
        first = self.claim(job_id)
        self.assertEqual(store.recover_interrupted_units(), 1)
        self.assertEqual(store.get_job_state(job_id)["job_status"], "RUNNING")
        self.assertEqual(
            self.scalar(
                "SELECT unit_status FROM production.units WHERE unit_id = %s",
                (first["unit_id"],),
            ),
            "FAILED",
        )
        second = self.claim(job_id)
        self.assertNotEqual(first["unit_id"], second["unit_id"])
        store.finish_job(job_id, "FAILED")

    def test_initial_stock_covers_requested_pass_quantity(self):
        job_id = self.create_job(quantity=2)
        with psycopg.connect(TEST_DSN) as connection:
            connection.execute(
                "UPDATE production.parts SET stock_quantity = 3 WHERE part_id = %s",
                (self.part_id,),
            )
        with self.assertRaisesRegex(RuntimeError, "insufficient stock"):
            self.claim(job_id)
        self.assertEqual(store.get_job_state(job_id)["job_status"], "PENDING")

    def test_replacement_attempt_checks_stock_before_creating_unit(self):
        job_id = self.create_job()
        first = self.claim(job_id)
        self.complete(first["unit_id"], "FAIL", ({
            "slot_code": "SLOT-A-01", "defect_type": "MISSING"
        },))
        store.resume_quality_job(job_id)
        with psycopg.connect(TEST_DSN) as connection:
            connection.execute(
                "UPDATE production.parts SET stock_quantity = 1 WHERE part_id = %s",
                (self.part_id,),
            )
        with self.assertRaisesRegex(RuntimeError, "insufficient stock"):
            self.claim(job_id)
        self.assertEqual(store.get_job_state(job_id)["job_status"], "RUNNING")
        self.assertEqual(self.scalar(
            "SELECT COUNT(*) FROM production.units WHERE job_id = %s", (job_id,)
        ), 1)

    def test_running_job_requires_stock_for_only_the_next_attempt(self):
        job_id = self.create_job(quantity=3)
        first = self.claim(job_id)
        self.complete(first["unit_id"])
        with psycopg.connect(TEST_DSN) as connection:
            connection.execute(
                "UPDATE production.parts SET stock_quantity = 2 WHERE part_id = %s",
                (self.part_id,),
            )
        second = self.claim(job_id)
        self.assertNotEqual(first["unit_id"], second["unit_id"])
        store.finish_job(job_id, "FAILED")

    def test_db_writer_end_to_end(self):
        job_id = self.create_job()
        writer = DbWriter(retry_initial_seconds=0.001, retry_max_seconds=0.002)
        self.addCleanup(writer.close, 0.5)
        work = writer.claim(
            job_id, self.product_code, self.product_version, "assembly-r1"
        )
        writer.assembly_completed(work["unit_id"])
        writer.inspection_recorded(work["unit_id"], "PASS", [])
        writer.unit_completed(work["unit_id"])
        writer.finish(job_id, "COMPLETED")
        self.assertTrue(writer.flush(1.0))
        self.assertEqual(store.get_job_state(job_id)["job_status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
