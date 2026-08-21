"""Integration checks that only create and remove UUID-scoped test rows."""

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
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import production_store as store


class ProductionStoreIntegrationTest(unittest.TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex
        self.product_code = "__MDB_TEST_PRODUCT_" + suffix
        self.other_product_code = "__MDB_TEST_OTHER_PRODUCT_" + suffix
        self.product_version = "test-v1"
        self.part_id = "__MDB_TEST_PART_" + suffix
        self.other_part_id = "__MDB_TEST_OTHER_PART_" + suffix

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

    def test_normal_completion_and_duplicate_completion(self):
        job_id = store.start_job(
            self.product_code, self.product_version, 1, "mock-r1"
        )
        unit_id = store.start_next_unit(job_id)

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
        job_id = store.start_job(
            self.product_code, self.product_version, 1, "mock-r1"
        )
        unit_id = store.start_next_unit(job_id)
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
        job_id = store.start_job(
            self.product_code, self.product_version, 1, "mock-r1"
        )
        unit_id = store.start_next_unit(job_id)
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


if __name__ == "__main__":
    unittest.main()
