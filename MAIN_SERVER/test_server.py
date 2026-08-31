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
    def __init__(self, start_response=None, snapshot=None, error=None):
        self.start_response = start_response
        self.snapshot = snapshot
        self.error = error
        self.calls = []

    def call(self, command_json):
        self.calls.append(command_json)
        if self.error is not None:
            raise self.error
        if command_json == '{"command":"status"}':
            return self.snapshot
        return self.start_response


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
        part_id = detail["data"]["slots"][0]["part_id"]
        status, part = self.request(f"/api/v1/parts/{part_id}")
        self.assertEqual((status, part["data"]["part_id"]), (200, part_id))
        status, rates = self.request(f"/api/v1/products/{product_id}/quality/slot-rates")
        self.assertEqual((status, len(rates["data"])), (200, len(detail["data"]["slots"])))
        with psycopg.connect(os.environ["MAIN_SERVER_DB_DSN"]) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT job_id FROM production.jobs ORDER BY job_id DESC LIMIT 1")
                job = cursor.fetchone()
        if job is None:
            status, body = self.request("/api/v1/jobs/1")
            self.assertEqual((status, body["error"]["code"]), (404, "not_found"))
        else:
            job_id = job[0]
            status, body = self.request(f"/api/v1/jobs/{job_id}")
            self.assertEqual((status, body["data"]["job_id"]), (200, job_id))
            status, body = self.request(f"/api/v1/jobs/{job_id}/units")
            self.assertEqual(status, 200)
            self.assertIsInstance(body["data"], list)

    def test_execution_routes_with_fake_gateway(self):
        request_id = "12345678-1234-5678-1234-567812345678"
        command = {
            "command": "start",
            "request_id": request_id,
            "recipe_version": "mock-r1",
            "observations": [{}],
            "assembled_pcb": {},
        }
        body = json.dumps(command, separators=(",", ":")).encode("utf-8")
        snapshot = {
            "available": True,
            "active": True,
            "request_id": request_id,
            "recipe_version": "mock-r1",
            "state": "STARTED",
            "placed_count": 0,
            "expected_step_count": 1,
        }
        gateway = FakeGateway(snapshot=snapshot)
        queued = {
            "accepted": True,
            "request_id": request_id,
            "status": "QUEUED",
        }
        with patch.object(server, "assembly_gateway", gateway), \
                patch.object(
                    server.queries, "enqueue_assembly", return_value=queued
                ) as enqueue:
            status, result = self.request("/api/v1/assemblies", "POST", body)
            self.assertEqual((status, result["data"]["accepted"]), (202, True))
            enqueue.assert_called_once_with(command, "mock")
            self.assertEqual(gateway.calls, [])
            status, result = self.request("/api/v1/assemblies/current")
            self.assertEqual((status, result["data"]["state"]), (200, "STARTED"))
            self.assertEqual(gateway.calls[-1], '{"command":"status"}')

    def test_execution_duplicate_and_unavailable(self):
        request_id = "12345678-1234-5678-1234-567812345678"
        body = json.dumps({
            "command": "start",
            "request_id": request_id,
            "recipe_version": "mock-r1",
            "observations": [{}],
            "assembled_pcb": {},
        }).encode("utf-8")
        with patch.object(
            server.queries,
            "enqueue_assembly",
            side_effect=server.queries.DuplicateRequest("different command"),
        ):
            status, result = self.request("/api/v1/assemblies", "POST", body)
            self.assertEqual(
                (status, result["error"]["code"]), (409, "duplicate_request")
            )
        unavailable = FakeGateway(error=GatewayUnavailable("ROS2 runtime is unavailable"))
        with patch.object(server, "assembly_gateway", unavailable):
            status, result = self.request("/api/v1/assemblies/current")
            self.assertEqual((status, result["error"]["code"]), (503, "assembly_unavailable"))
        unavailable_snapshot = FakeGateway(snapshot={"available": False, "error_code": "UNAVAILABLE", "message": "bridge DB unavailable"})
        with patch.object(server, "assembly_gateway", unavailable_snapshot):
            status, result = self.request("/api/v1/assemblies/current")
            self.assertEqual((status, result["error"]["code"]), (503, "assembly_unavailable"))
        idle = FakeGateway(snapshot={"available": False, "error_code": "", "state": "IDLE"})
        with patch.object(server, "assembly_gateway", idle):
            status, result = self.request("/api/v1/assemblies/current")
            self.assertEqual((status, result["data"]["state"]), (200, "IDLE"))

    def test_enqueue_is_idempotent_by_request_id(self):
        request_id = str(uuid.uuid4())
        command = {
            "command": "start",
            "request_id": request_id,
            "recipe_version": "mock-r1",
            "observations": [{}],
            "assembled_pcb": {},
        }
        try:
            first = server.queries.enqueue_assembly(command, "mock")
            second = server.queries.enqueue_assembly(command, "mock")
            self.assertEqual(first["status"], "QUEUED")
            self.assertEqual(second, first)

            changed = dict(command)
            changed["recipe_version"] = "different"
            with self.assertRaises(server.queries.DuplicateRequest):
                server.queries.enqueue_assembly(changed, "mock")
        finally:
            with psycopg.connect(os.environ["MAIN_SERVER_DB_DSN"]) as connection:
                connection.execute(
                    "DELETE FROM control.assembly_requests WHERE request_id = %s",
                    (request_id,),
                )

    def test_validation_and_missing_resource(self):
        status, body = self.request("/api/v1/products/1/requirements?quantity=0")
        self.assertEqual((status, body["error"]["code"]), (400, "invalid_request"))
        status, body = self.request("/api/v1/parts/not-a-part")
        self.assertEqual((status, body["error"]["code"]), (404, "not_found"))
        status, body = self.request(
            "/api/v1/assemblies", "POST", b'{"command":"start"}'
        )
        self.assertEqual((status, body["error"]["code"]), (400, "invalid_request"))

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
