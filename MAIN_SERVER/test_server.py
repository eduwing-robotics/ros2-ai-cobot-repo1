"""Runnable integration and API-registry check for MainServer."""
import json
import os
import re
import sys
import threading
import uuid
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

import psycopg

sys.path.insert(0, str(Path(__file__).parent))
import server
from assembly_gateway import GatewayUnavailable


class FakeGateway:
    def __init__(self, snapshot=None, error=None):
        self.snapshot = snapshot
        self.error = error
        self.calls = []

    def status(self):
        self.calls.append('{"command":"status"}')
        if self.error is not None:
            raise self.error
        return self.snapshot


class MainServerApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("MAIN_SERVER_MODE") != "mock":
            raise RuntimeError("run integration tests with MAIN_SERVER_MODE=mock")
        server.validate_startup_configuration()
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.ApiHandler)
        cls.base_url = f"http://127.0.0.1:{cls.httpd.server_port}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def request(self, path, method="GET", body=None):
        request = Request(self.base_url + path, data=body, method=method)
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urlopen(request) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_documented_routes_are_registered_once(self):
        document = (Path(__file__).parent / "Main_serverAPI.md").read_text(encoding="utf-8")
        marker = chr(96)
        documented = re.findall(
            r"\| " + marker + r"([A-Z]+)" + marker + r" \| " + marker
            + r"(/api/v1/[^" + marker + r"?]+)(?:\?[^" + marker + r"]*)?" + marker
            + r" \|",
            document,
        )
        registered = [(method, path) for method, path, _ in server.ROUTES]
        self.assertEqual(documented, registered)
        self.assertEqual(len(documented), len(set(documented)))
        self.assertEqual(len(registered), len(set(registered)))

    def test_seeded_read_routes(self):
        status, health = self.request("/api/v1/health")
        self.assertEqual(status, 200)
        self.assertIn("database_name", health["data"])
        self.assertEqual(health["data"]["runtime_mode"], "mock")
        status, products = self.request("/api/v1/products")
        self.assertEqual(status, 200)
        product = next(
            item for item in products["data"]
            if item["product_code"] == "HBM-ACCELERATOR-PACKAGE-BOARD"
        )
        product_id = product["product_id"]
        status, detail = self.request(f"/api/v1/products/{product_id}")
        self.assertEqual(status, 200)
        self.assertTrue(detail["data"]["slots"])
        status, requirements = self.request(
            f"/api/v1/products/{product_id}/requirements?quantity=1"
        )
        self.assertEqual(status, 200)
        self.assertTrue(requirements["data"])
        self.assertTrue(all(
            row["unit_price_selected"] is not None for row in requirements["data"]
        ))
        part_id = detail["data"]["slots"][0]["part_id"]
        status, part = self.request(f"/api/v1/parts/{part_id}")
        self.assertEqual((status, part["data"]["part_id"]), (200, part_id))
        self.assertIn(
            part["data"]["part_name"],
            {candidate["mpn"] for candidate in part["data"]["candidates"]},
        )
        status, rates = self.request(f"/api/v1/products/{product_id}/quality/slot-rates")
        self.assertEqual((status, len(rates["data"])), (200, len(detail["data"]["slots"])))
        status, jobs = self.request("/api/v1/jobs?limit=5")
        self.assertEqual(status, 200)
        self.assertIsInstance(jobs["data"], list)
        self.assertLessEqual(len(jobs["data"]), 5)
        with psycopg.connect(os.environ["MAIN_SERVER_DB_DSN"]) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT job_id FROM production.jobs ORDER BY job_id DESC LIMIT 1")
                job = cursor.fetchone()
        if job is None:
            status, body = self.request("/api/v1/jobs/1")
            self.assertEqual((status, body["error"]["code"]), (404, "not_found"))
        else:
            job_id = str(job[0])
            status, body = self.request(f"/api/v1/jobs/{job_id}")
            self.assertEqual((status, body["data"]["job_id"]), (200, job_id))
            status, body = self.request(f"/api/v1/jobs/{job_id}/units")
            self.assertEqual(status, 200)
            self.assertIsInstance(body["data"], list)

    def test_execution_routes_with_fake_gateway(self):
        job_id = "12345678-1234-5678-1234-567812345678"
        command = {
            "command": "start",
            "job_id": job_id,
            "product_code": "HBM-ACCELERATOR-PACKAGE-BOARD",
            "product_version": "hbm-pkg-r1",
            "requested_quantity": 1,
            "recipe_version": "assembly-r1",
        }
        body = json.dumps(command, separators=(",", ":")).encode("utf-8")
        snapshot = {
            "available": True,
            "active": True,
            "job_id": job_id,
            "recipe_version": "assembly-r1",
            "state": "STARTED",
            "placed_count": 0,
            "expected_step_count": 1,
        }
        gateway = FakeGateway(snapshot=snapshot)
        created = {"accepted": True, "job_id": job_id, "status": "PENDING"}
        with patch.object(server, "assembly_gateway", gateway), \
                patch.object(
                    server.queries, "create_job", return_value=created
                ) as create:
            status, result = self.request("/api/v1/assemblies", "POST", body)
            self.assertEqual((status, result["data"]["accepted"]), (202, True))
            create.assert_called_once_with(command)
            self.assertEqual(gateway.calls, [])
            status, result = self.request("/api/v1/assemblies/current")
            self.assertEqual((status, result["data"]["state"]), (200, "STARTED"))
            self.assertEqual(gateway.calls[-1], '{"command":"status"}')

    def test_execution_duplicate_and_unavailable(self):
        body = json.dumps({
            "command": "start",
            "job_id": "12345678-1234-5678-1234-567812345678",
            "product_code": "HBM-ACCELERATOR-PACKAGE-BOARD",
            "product_version": "hbm-pkg-r1",
            "requested_quantity": 1,
            "recipe_version": "assembly-r1",
        }).encode("utf-8")
        with patch.object(
            server.queries,
            "create_job",
            side_effect=server.queries.DuplicateRequest("different Job request"),
        ):
            status, result = self.request("/api/v1/assemblies", "POST", body)
            self.assertEqual(
                (status, result["error"]["code"]), (409, "duplicate_request")
            )
        unavailable = FakeGateway(error=GatewayUnavailable("ROS2 unavailable"))
        with patch.object(server, "assembly_gateway", unavailable):
            status, result = self.request("/api/v1/assemblies/current")
            self.assertEqual(
                (status, result["error"]["code"]), (503, "assembly_unavailable")
            )
        idle = FakeGateway(
            snapshot={"available": False, "error_code": "", "state": "IDLE"}
        )
        with patch.object(server, "assembly_gateway", idle):
            status, result = self.request("/api/v1/assemblies/current")
            self.assertEqual((status, result["data"]["state"]), (200, "IDLE"))

    def test_create_job_is_idempotent_by_job_id(self):
        job_id = str(uuid.uuid4())
        command = {
            "command": "start",
            "job_id": job_id,
            "product_code": "HBM-ACCELERATOR-PACKAGE-BOARD",
            "product_version": "hbm-pkg-r1",
            "requested_quantity": 1,
            "recipe_version": "assembly-r1",
        }
        try:
            first = server.queries.create_job(command)
            second = server.queries.create_job(command)
            self.assertEqual(first["status"], "PENDING")
            self.assertEqual(second, first)

            changed = dict(command)
            changed["requested_quantity"] = 2
            with self.assertRaises(server.queries.DuplicateRequest):
                server.queries.create_job(changed)
        finally:
            with psycopg.connect(os.environ["MAIN_SERVER_DB_DSN"]) as connection:
                connection.execute(
                    "DELETE FROM production.jobs WHERE job_id = %s", (job_id,)
                )

    def test_validation_and_missing_resource(self):
        status, body = self.request("/api/v1/jobs?status=UNKNOWN")
        self.assertEqual((status, body["error"]["code"]), (400, "invalid_request"))
        status, body = self.request("/api/v1/jobs?limit=51")
        self.assertEqual((status, body["error"]["code"]), (400, "invalid_request"))
        status, body = self.request("/api/v1/products/1/requirements?quantity=0")
        self.assertEqual((status, body["error"]["code"]), (400, "invalid_request"))
        status, body = self.request("/api/v1/parts/not-a-part")
        self.assertEqual((status, body["error"]["code"]), (404, "not_found"))
        status, body = self.request(
            "/api/v1/assemblies", "POST", b'{"command":"start"}'
        )
        self.assertEqual((status, body["error"]["code"]), (400, "invalid_request"))

    def test_datasheet_mismatch_is_service_unavailable(self):
        missing = {
            "part_id": "MISSING",
            "part_name": "missing MPN",
            "part_category": "MLCC",
            "stock_quantity": 1,
        }
        with patch.object(server.queries, "part", return_value=missing):
            status, body = self.request("/api/v1/parts/MISSING")
        self.assertEqual(
            (status, body["error"]["code"]), (503, "datasheet_inconsistent")
        )

    def test_runtime_mode_validation(self):
        with patch.dict(os.environ, {"MAIN_SERVER_MODE": "real"}):
            self.assertEqual(server.validate_startup_configuration(), "real")
        for value in ("", "Mock", "simulation"):
            with self.subTest(value=value), patch.dict(os.environ, {"MAIN_SERVER_MODE": value}):
                with self.assertRaisesRegex(
                    server.RuntimeConfigurationError,
                    "MAIN_SERVER_MODE must be exactly 'mock' or 'real'",
                ):
                    server.validate_startup_configuration()
        with patch.dict(os.environ, {"MAIN_SERVER_DB_DSN": ""}):
            with self.assertRaisesRegex(
                server.RuntimeConfigurationError, "MAIN_SERVER_DB_DSN is required"
            ):
                server.validate_startup_configuration()


if __name__ == "__main__":
    unittest.main(verbosity=2)
