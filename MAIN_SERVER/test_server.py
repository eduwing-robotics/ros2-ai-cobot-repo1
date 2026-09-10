"""Runnable integration and API-registry check for MainServer."""
import json
import hashlib
import os
import re
import sys
import threading
import tempfile
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
        request.add_header("X-Runtime-Mode", "mock")
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urlopen(request) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_inspection_image_returns_png_and_integrity_headers(self):
        png = b"\x89PNG\r\n\x1a\nfixture"
        request = Request(self.base_url + "/api/v1/units/42/inspection/image",
                          headers={"X-Runtime-Mode": "mock"})
        with patch.object(server.queries, "inspection_image", return_value=png) as load:
            with urlopen(request) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), png)
                self.assertEqual(response.headers["Content-Type"], "image/png")
                self.assertEqual(response.headers["Content-Length"], str(len(png)))
                self.assertEqual(response.headers["X-Content-SHA256"], hashlib.sha256(png).hexdigest())
            load.assert_called_once_with(42)
        with patch.object(server.queries, "inspection_image", side_effect=server.queries.InspectionUnavailable("hash mismatch")):
            status, body = self.request("/api/v1/units/42/inspection/image")
            self.assertEqual((status, body["error"]["code"]), (409, "inspection_unavailable"))

    def test_local_reports_generate_without_email_and_download(self):
        reports = server.reports
        candidates = server.queries.defect_reports()
        self.assertTrue(candidates)
        row = candidates[0]
        identity = row["unit_defect_id"]
        product = server.queries._one("""SELECT j.product_id FROM production.units u
            JOIN production.jobs j USING(job_id) WHERE u.unit_id=%s""", (row["unit_id"],))["product_id"]
        url = f"/api/v1/products/{product}/quality/defect-reports?slot_code={row['slot_code']}"
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"DEFECT_REPORT_OUTPUT_DIR": directory}):
            status, body = self.request(url)
            self.assertEqual(status, 200)
            self.assertTrue(all(r["slot_code"] == row["slot_code"] for r in body["data"]))
            self.assertFalse(any(r["report_ready"] for r in body["data"]))
            status, body = self.request(f"/api/v1/defect-reports/{identity}/file")
            self.assertEqual((status, body["error"]["code"]), (409, "report_unavailable"))
            before = server.queries._all("SELECT * FROM production.defect_report_deliveries ORDER BY unit_defect_id")
            with patch.object(reports, "send_message") as send, patch.object(reports, "load_mail_config") as config, \
                    patch.object(reports, "claim_delivery") as claim, \
                    patch.object(sys, "argv", ["generate_defect_reports.py", "--unit-defect-id", str(identity)]):
                reports.main()
                send.assert_not_called()
                config.assert_not_called()
                claim.assert_not_called()
            self.assertEqual(before, server.queries._all("SELECT * FROM production.defect_report_deliveries ORDER BY unit_defect_id"))
            target = reports.archived_report(row)
            original = target.read_bytes()
            with patch.object(reports, "create_report", side_effect=AssertionError("existing report must be preserved")):
                reports.run_local_worker(os.environ["MAIN_SERVER_DB_DSN"], reports.DATASHEET,
                                         reports.TEMPLATE, Path(directory), once=True, unit_defect_id=identity)
            self.assertEqual(target.read_bytes(), original)
            status, body = self.request(url)
            item = next(r for r in body["data"] if r["unit_defect_id"] == identity)
            self.assertTrue(item["report_ready"])
            with urlopen(Request(self.base_url + item["file_url"], headers={"X-Runtime-Mode": "mock"})) as response:
                self.assertEqual(response.read(), original)
                self.assertEqual(response.headers["X-Content-SHA256"], hashlib.sha256(original).hexdigest())
                self.assertIn(item["filename"], response.headers["Content-Disposition"])
            target.unlink()
            target.symlink_to(reports.TEMPLATE)
            status, body = self.request(f"/api/v1/defect-reports/{identity}/file")
            self.assertEqual((status, body["error"]["code"]), (409, "report_unavailable"))
            status, body = self.request(url + "&slot_code=other")
            self.assertEqual(status, 400)

    def test_local_report_rejects_image_unready_vision(self):
        reports = server.reports
        rows = [{"target_unit_id": 42, "target_image_path": None}]
        inspection = {"result": {"decision": "FAIL"}, "image": {"ready": False}}
        with patch.object(reports, "load_defect_context", return_value=rows), \
                patch.object(server.queries, "inspection", return_value=inspection), \
                patch.object(reports, "write_report") as write:
            with self.assertRaisesRegex(RuntimeError, "not ready"):
                reports.create_report("unused", 42, reports.DATASHEET, reports.TEMPLATE,
                                      reports.OUTPUT_DIR, reports.DEFAULT_IMAGE_ROOT, 10485760)
            write.assert_not_called()

    def test_paused_job_filter_reaches_query(self):
        with patch.object(server.queries, "jobs", return_value=[]) as query:
            status, body = self.request("/api/v1/jobs?status=PAUSED")
            self.assertEqual(status, 200)
            query.assert_called_once_with("PAUSED", 12)

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

    def test_requested_by_validation(self):
        command = dict(command="start", job_id=str(uuid.uuid4()), product_code="p",
                       product_version="v", recipe_version="r", requested_quantity=1)
        for invalid in (None, "", "   ", 42, "x" * 129):
            with self.assertRaises(server.ValidationError):
                server.ApiHandler._validate_start_command(command | {"requested_by": invalid})
        valid = command | {"requested_by": "  요청자  "}
        server.ApiHandler._validate_start_command(valid)
        self.assertEqual(valid["requested_by"], "요청자")
        server.ApiHandler._validate_start_command(command)

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
            "requested_by": "현장 요청자",
        }
        try:
            first = server.queries.create_job(command)
            second = server.queries.create_job(command)
            self.assertEqual(first["status"], "PENDING")
            self.assertEqual(second, first)
            self.assertEqual(server.queries.job(job_id)["requested_by"], "현장 요청자")
            listed = next(row for row in server.queries.jobs(limit=100) if str(row["job_id"]) == job_id)
            self.assertEqual(listed["requested_by"], "현장 요청자")
            with self.assertRaises(server.queries.DuplicateRequest):
                server.queries.create_job(command | {"requested_by": "다른 요청자"})

            changed = dict(command)
            changed["requested_quantity"] = 2
            with self.assertRaises(server.queries.DuplicateRequest):
                server.queries.create_job(changed)
        finally:
            with psycopg.connect(os.environ["MAIN_SERVER_DB_DSN"]) as connection:
                connection.execute(
                    "DELETE FROM production.jobs WHERE job_id = %s", (job_id,)
                )

    def test_pending_job_can_be_cancelled(self):
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
            server.queries.create_job(command)
            status, body = self.request(f"/api/v1/jobs/{job_id}", "DELETE")
            self.assertEqual((status, body["data"]["job_status"]), (200, "CANCELLED"))
            status, body = self.request(f"/api/v1/jobs/{job_id}", "DELETE")
            self.assertEqual((status, body["error"]["code"]), (409, "job_not_cancellable"))
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
        with patch.object(server, "_started_mode", None), patch.dict(os.environ, {"MAIN_SERVER_MODE": "real"}):
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


class ModeIsolationTest(unittest.TestCase):
    def test_http_mode_rejects_before_database(self):
        with patch.dict(os.environ, {"MAIN_SERVER_MODE": "mock"}), patch.object(server, "_started_mode", "mock"):
            httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.ApiHandler)
            worker = threading.Thread(target=httpd.serve_forever, daemon=True)
            worker.start()
            try:
                with patch.object(server.queries, "products", return_value=[]) as read:
                    for mode in (None, "real", "Mock", "mock"):
                        request = Request(f"http://127.0.0.1:{httpd.server_port}/api/v1/products")
                        if mode is not None:
                            request.add_header("X-Runtime-Mode", mode)
                        if mode == "mock":
                            with urlopen(request) as response:
                                self.assertEqual(response.status, 200)
                        else:
                            with self.assertRaises(HTTPError) as error:
                                urlopen(request)
                            self.assertEqual(error.exception.code, 409)
                            read.assert_not_called()
                    read.assert_called_once()
            finally:
                httpd.shutdown()
                httpd.server_close()
                worker.join()

    def test_database_identity_and_connection_cleanup(self):
        from unittest.mock import MagicMock
        for actual in (None, "real", "mock"):
            connection = MagicMock()
            connection.execute.return_value.fetchone.return_value = (
                {"runtime_mode": actual} if actual else None)
            with patch.dict(os.environ, {"MAIN_SERVER_MODE": "mock", "MAIN_SERVER_DB_DSN": "test"}), \
                    patch.object(server.queries.psycopg, "connect", return_value=connection):
                if actual == "mock":
                    self.assertIs(server.queries._connect(), connection)
                    connection.commit.assert_called_once()
                    connection.close.assert_not_called()
                else:
                    with self.assertRaisesRegex(server.queries.DatabaseUnavailable, "MODE_REJECTED"):
                        server.queries._connect()
                    connection.close.assert_called_once()
                    connection.commit.assert_not_called()

    def test_mode_cannot_change_after_startup(self):
        with patch.object(server, "_started_mode", "mock"), patch.dict(os.environ, {"MAIN_SERVER_MODE": "real"}):
            with self.assertRaisesRegex(server.RuntimeConfigurationError, "cannot change"):
                server.runtime_mode()

    def test_sequencer_mode_is_required(self):
        from assembly_gateway import AssemblyGateway
        with patch.dict(os.environ, {"MAIN_SERVER_MODE": "mock"}):
            for response in ({}, {"runtime_mode": "real"}, {"runtime_mode": "mock"}):
                if response.get("runtime_mode") == "mock":
                    self.assertEqual(AssemblyGateway._parse_response(json.dumps(response)), response)
                else:
                    with self.assertRaisesRegex(GatewayUnavailable, "MODE_REJECTED"):
                        AssemblyGateway._parse_response(json.dumps(response))


if __name__ == "__main__":
    unittest.main(verbosity=2)
