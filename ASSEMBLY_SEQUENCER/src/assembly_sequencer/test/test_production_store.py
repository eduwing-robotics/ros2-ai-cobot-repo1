"""Integration checks that only create and remove UUID-scoped test rows."""

import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

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
        self.other_product_code = "__MDB_TEST_OTHER_PRODUCT_" + suffix
        self.product_version = "test-v1"
        self.part_id = "__MDB_TEST_PART_" + suffix
        self.other_part_id = "__MDB_TEST_OTHER_PART_" + suffix
        self.request_ids = []

        with psycopg.connect(TEST_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO production.parts (
                        part_id, part_name, part_category, stock_quantity
                    ) VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)
                    """,
                    (
                        self.part_id, "test part", "TEST", 4,
                        self.other_part_id, "other test part", "TEST", 1,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO production.products (
                        product_code, product_name, product_version
                    ) VALUES (%s, %s, %s), (%s, %s, %s)
                    RETURNING product_id
                    """,
                    (
                        self.product_code, "test product", self.product_version,
                        self.other_product_code, "other test product", self.product_version,
                    ),
                )
                self.product_id, self.other_product_id = [
                    row[0] for row in cursor.fetchall()
                ]
                cursor.execute(
                    """
                    INSERT INTO production.product_slots (
                        product_id, slot_code, part_id
                    ) VALUES (%s, %s, %s), (%s, %s, %s), (%s, %s, %s)
                    """,
                    (
                        self.product_id, "SLOT-A-01", self.part_id,
                        self.product_id, "SLOT-A-02", self.part_id,
                        self.other_product_id, "OTHER-01", self.other_part_id,
                    ),
                )

    def tearDown(self):
        with psycopg.connect(TEST_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM control.assembly_requests WHERE request_id = ANY(%s)",
                    (self.request_ids,),
                )
                cursor.execute(
                    """
                    DELETE FROM production.unit_defects ud
                    USING production.units u, production.jobs j
                    WHERE ud.unit_id = u.unit_id
                      AND u.job_id = j.job_id
                      AND j.product_id = ANY(%s)
                    """,
                    ([self.product_id, self.other_product_id],),
                )
                cursor.execute(
                    """
                    DELETE FROM production.units u
                    USING production.jobs j
                    WHERE u.job_id = j.job_id AND j.product_id = ANY(%s)
                    """,
                    ([self.product_id, self.other_product_id],),
                )
                cursor.execute(
                    "DELETE FROM production.jobs WHERE product_id = ANY(%s)",
                    ([self.product_id, self.other_product_id],),
                )
                cursor.execute(
                    "DELETE FROM production.product_slots WHERE product_id = ANY(%s)",
                    ([self.product_id, self.other_product_id],),
                )
                cursor.execute(
                    "DELETE FROM production.products WHERE product_id = ANY(%s)",
                    ([self.product_id, self.other_product_id],),
                )
                cursor.execute(
                    "DELETE FROM production.parts WHERE part_id = ANY(%s)",
                    ([self.part_id, self.other_part_id],),
                )

    def scalar(self, query, parameters):
        with psycopg.connect(TEST_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, parameters)
                return cursor.fetchone()[0]

    def test_reservation_rolls_back_when_unit_creation_fails(self):
        with patch.object(
            store,
            "_insert_next_unit",
            side_effect=RuntimeError("forced unit failure"),
        ):
            with self.assertRaises(RuntimeError):
                store.reserve_work(
                    self.product_code,
                    self.product_version,
                    1,
                    "mock-r1",
                )

        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM production.jobs WHERE product_id = %s",
                (self.product_id,),
            ),
            0,
        )

    def test_normal_completion_and_duplicate_completion(self):
        reservation = store.reserve_work(
            self.product_code, self.product_version, 1, "mock-r1"
        )
        job_id, unit_id = reservation

        store.complete_assembly_and_consume_stock(unit_id)
        self.assertEqual(
            self.scalar(
                "SELECT stock_quantity FROM production.parts WHERE part_id = %s",
                (self.part_id,),
            ),
            2,
        )
        store.complete_assembly_and_consume_stock(unit_id)
        self.assertEqual(
            self.scalar(
                "SELECT stock_quantity FROM production.parts WHERE part_id = %s",
                (self.part_id,),
            ),
            2,
        )

        store.record_inspection(unit_id, "PASS", [], "/tmp/mock-pass.jpg")
        with self.assertRaises(RuntimeError):
            store.start_next_unit(job_id)

        with psycopg.connect(TEST_DSN) as connection:
            extra_failed_unit = connection.execute(
                """
                INSERT INTO production.units (
                    job_id, unit_sequence_in_job, unit_status
                ) VALUES (%s, %s, %s)
                RETURNING unit_id
                """,
                (job_id, 2, "FAILED"),
            ).fetchone()[0]
        with self.assertRaises(RuntimeError):
            store.finish_job(job_id, "COMPLETED")
        with psycopg.connect(TEST_DSN) as connection:
            connection.execute(
                "DELETE FROM production.units WHERE unit_id = %s",
                (extra_failed_unit,),
            )

        store.finish_job(job_id, "COMPLETED")
        self.assertEqual(store.get_job_state(job_id)["job_status"], "COMPLETED")
        self.assertEqual(
            store.get_product_slot_codes(job_id), ["SLOT-A-01", "SLOT-A-02"]
        )
        self.assertIsNone(store.get_active_job_state())
        store.record_inspection(unit_id, "PASS", [], "/tmp/mock-pass.jpg")
        self.assertEqual(
            self.scalar(
                "SELECT inspection_result FROM production.units WHERE unit_id = %s",
                (unit_id,),
            ),
            "PASS",
        )

    def test_inspection_rules_and_cross_product_slot(self):
        reservation = store.reserve_work(
            self.product_code, self.product_version, 1, "mock-r1"
        )
        job_id, unit_id = reservation
        store.complete_assembly_and_consume_stock(unit_id)

        with self.assertRaises(ValueError):
            store.record_inspection(
                unit_id,
                "PASS",
                [{"slot_code": "SLOT-A-01", "defect_type": "MISSING"}],
            )
        with self.assertRaises(ValueError):
            store.record_inspection(unit_id, "FAIL", [])
        with self.assertRaises(RuntimeError):
            store.record_inspection(
                unit_id,
                "FAIL",
                [{"slot_code": "OTHER-01", "defect_type": "MISSING"}],
            )
        self.assertEqual(
            self.scalar(
                "SELECT inspection_result FROM production.units WHERE unit_id = %s",
                (unit_id,),
            ),
            "PENDING",
        )

        store.record_inspection(
            unit_id,
            "FAIL",
            [{"slot_code": "SLOT-A-01", "defect_type": "MISSING"}],
        )
        store.finish_job(job_id, "COMPLETED")

    def test_insufficient_stock_rolls_back(self):
        reservation = store.reserve_work(
            self.product_code, self.product_version, 1, "mock-r1"
        )
        job_id, unit_id = reservation
        with psycopg.connect(TEST_DSN) as connection:
            connection.execute(
                "UPDATE production.parts SET stock_quantity = %s WHERE part_id = %s",
                (1, self.part_id),
            )

        with self.assertRaises(RuntimeError):
            store.complete_assembly_and_consume_stock(unit_id)
        self.assertEqual(
            self.scalar(
                "SELECT stock_quantity FROM production.parts WHERE part_id = %s",
                (self.part_id,),
            ),
            1,
        )
        self.assertIsNone(
            self.scalar(
                "SELECT assembly_completed_at FROM production.units WHERE unit_id = %s",
                (unit_id,),
            )
        )
        store.fail_unit(unit_id)
        store.finish_job(job_id, "FAILED")


    def test_queue_claim_completion_and_restart_cleanup(self):
        first_request_id = uuid.uuid4()
        self.request_ids.append(first_request_id)
        payload = {
            "command": "start",
            "request_id": str(first_request_id),
            "recipe_version": "mock-r1",
            "observations": [{}],
            "assembled_pcb": {},
        }
        with psycopg.connect(TEST_DSN) as connection:
            connection.execute(
                """
                INSERT INTO control.assembly_requests (
                    request_id, runtime_mode, payload
                ) VALUES (%s, 'mock', %s)
                """,
                (first_request_id, psycopg.types.json.Jsonb(payload)),
            )

        work = store.claim_queued_work(
            "mock", self.product_code, self.product_version, 1, "mock-r1"
        )
        self.assertEqual(work["request_id"], str(first_request_id))
        store.complete_assembly_and_consume_stock(work["unit_id"])
        store.record_inspection(work["unit_id"], "PASS", [])
        store.finish_job(work["job_id"], "COMPLETED")
        self.assertEqual(
            self.scalar(
                """
                SELECT request_status
                FROM control.assembly_requests
                WHERE request_id = %s
                """,
                (first_request_id,),
            ),
            "COMPLETED",
        )

        interrupted_request_id = uuid.uuid4()
        self.request_ids.append(interrupted_request_id)
        payload["request_id"] = str(interrupted_request_id)
        with psycopg.connect(TEST_DSN) as connection:
            connection.execute(
                """
                INSERT INTO control.assembly_requests (
                    request_id, runtime_mode, payload
                ) VALUES (%s, 'mock', %s)
                """,
                (interrupted_request_id, psycopg.types.json.Jsonb(payload)),
            )
        interrupted = store.claim_queued_work(
            "mock", self.product_code, self.product_version, 1, "mock-r1"
        )
        self.assertEqual(store.fail_interrupted_requests("mock"), 1)
        self.assertEqual(
            store.get_job_state(interrupted["job_id"])["job_status"], "FAILED"
        )
        self.assertEqual(
            self.scalar(
                """
                SELECT request_status
                FROM control.assembly_requests
                WHERE request_id = %s
                """,
                (interrupted_request_id,),
            ),
            "FAILED",
        )
    def test_db_writer_end_to_end(self):
        writer = DbWriter(
            retry_initial_seconds=0.001,
            retry_max_seconds=0.002,
        )
        self.addCleanup(writer.close, 0.5)

        reservation = writer.reserve(
            str(uuid.uuid4()),
            self.product_code,
            self.product_version,
            "mock-r1",
        )
        writer.assembly_completed(reservation.unit_id)
        writer.inspection_recorded(reservation.unit_id, "PASS", [])
        writer.finish(reservation.job_id, "COMPLETED")

        self.assertTrue(writer.flush(1.0))
        self.assertEqual(
            store.get_job_state(reservation.job_id)["job_status"],
            "COMPLETED",
        )
        self.assertEqual(writer.sync_state, "SYNCED")


if __name__ == "__main__":
    unittest.main()
