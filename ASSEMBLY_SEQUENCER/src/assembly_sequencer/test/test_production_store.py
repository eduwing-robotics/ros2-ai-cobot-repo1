"""Integration checks for the UUID Job and Unit-attempt lifecycle."""

import os
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

    def test_db_writer_end_to_end(self):
        job_id = self.create_job()
        writer = DbWriter(retry_initial_seconds=0.001, retry_max_seconds=0.002)
        self.addCleanup(writer.close, 0.5)
        work = writer.claim(
            job_id, self.product_code, self.product_version, "assembly-r1"
        )
        writer.assembly_completed(work["unit_id"])
        writer.inspection_recorded(work["unit_id"], "PASS", [])
        writer.finish(job_id, "COMPLETED")
        self.assertTrue(writer.flush(1.0))
        self.assertEqual(store.get_job_state(job_id)["job_status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
