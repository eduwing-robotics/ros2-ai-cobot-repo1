"""HTTP API for MainServer production queries and assembly requests."""
import argparse
import json
import logging
import os
import uuid
from datetime import date, datetime
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import datasheet
import queries
from assembly_gateway import AssemblyGateway, GatewayUnavailable


ROUTES = (
    ("GET", "/api/v1/health", "health"),
    ("GET", "/api/v1/products", "products"),
    ("GET", "/api/v1/products/{product_id}", "product"),
    ("GET", "/api/v1/products/{product_id}/requirements", "requirements"),
    ("GET", "/api/v1/parts/{part_id}", "part"),
    ("GET", "/api/v1/jobs/{job_id}", "job"),
    ("GET", "/api/v1/jobs/{job_id}/units", "units"),
    ("GET", "/api/v1/products/{product_id}/quality/slot-rates", "slot_rates"),
    ("POST", "/api/v1/assemblies", "assembly_start"),
    ("GET", "/api/v1/assemblies/current", "assembly_current"),
)
if len({(method, path) for method, path, _ in ROUTES}) != len(ROUTES):
    raise RuntimeError("duplicate API method/path")

VALID_RUNTIME_MODES = ("mock", "real")
MAX_REQUEST_BODY_BYTES = 1_000_000
assembly_gateway = AssemblyGateway()


class RuntimeConfigurationError(RuntimeError):
    pass


class ValidationError(ValueError):
    pass


class AssemblyRejected(RuntimeError):
    def __init__(self, status, code, message):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def runtime_mode():
    mode = os.environ.get("MAIN_SERVER_MODE")
    if mode not in VALID_RUNTIME_MODES:
        raise RuntimeConfigurationError("MAIN_SERVER_MODE must be exactly 'mock' or 'real'")
    return mode


def validate_startup_configuration():
    mode = runtime_mode()
    if not os.environ.get("MAIN_SERVER_DB_DSN", "").strip():
        raise RuntimeConfigurationError("MAIN_SERVER_DB_DSN is required")
    return mode


def positive(value, label):
    if not value or not value.isdecimal() or int(value) <= 0:
        raise ValidationError(f"{label} must be a positive integer")
    return int(value)


def uuid_value(value, label):
    try:
        return str(uuid.UUID(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValidationError(f"{label} must be a UUID string") from error


def json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "MainServer/1.0"

    def do_GET(self):
        self._serve("GET")

    def do_POST(self):
        self._serve("POST")

    def _serve(self, method):
        try:
            request = urlsplit(self.path)
            handler, route_values = self._route(method, request.path)
            data = getattr(self, handler)(
                route_values, parse_qs(request.query, keep_blank_values=True)
            )
            self._respond(202 if handler == "assembly_start" else 200, {"data": data})
        except ValidationError as error:
            self._error(400, "invalid_request", str(error))
        except AssemblyRejected as error:
            self._error(error.status, error.code, error.message)
        except GatewayUnavailable:
            self._error(503, "assembly_unavailable", "assembly bridge is unavailable")
        except queries.ResourceNotFound as error:
            self._error(404, "not_found", str(error))
        except queries.DatabaseUnavailable:
            self._error(503, "database_unavailable", "database is unavailable")
        except datasheet.DatasheetIntegrityError as error:
            logging.error("datasheet integrity error: %s", error)
            self._error(503, "datasheet_inconsistent", str(error))
        except Exception:
            logging.exception("unexpected API error")
            self._error(500, "internal_error", "internal server error")

    def _route(self, method, path):
        actual_parts = path.strip("/").split("/")
        for route_method, template, handler in ROUTES:
            if route_method != method:
                continue
            template_parts = template.strip("/").split("/")
            if len(actual_parts) != len(template_parts):
                continue
            values = {}
            for actual, expected in zip(actual_parts, template_parts):
                if expected.startswith("{") and expected.endswith("}"):
                    values[expected[1:-1]] = actual
                elif actual != expected:
                    break
            else:
                return handler, values
        raise queries.ResourceNotFound("route was not found")

    @staticmethod
    def _no_query(parameters):
        if parameters:
            raise ValidationError("this route does not accept query parameters")

    @staticmethod
    def _quantity(parameters):
        if set(parameters) != {"quantity"} or len(parameters["quantity"]) != 1:
            raise ValidationError("quantity is required exactly once")
        return positive(parameters["quantity"][0], "quantity")

    def health(self, values, parameters):
        self._no_query(parameters)
        data = queries.health()
        data["runtime_mode"] = runtime_mode()
        return data

    def products(self, values, parameters):
        self._no_query(parameters)
        return queries.products()

    def product(self, values, parameters):
        self._no_query(parameters)
        return queries.product(positive(values["product_id"], "product_id"))

    def requirements(self, values, parameters):
        rows = queries.requirements(
            positive(values["product_id"], "product_id"), self._quantity(parameters)
        )
        return [self._priced(row) for row in rows]

    def part(self, values, parameters):
        self._no_query(parameters)
        if not values["part_id"].strip():
            raise ValidationError("part_id is required")
        row = queries.part(values["part_id"])
        row["candidates"] = self._candidates(
            row["part_category"], row["part_name"])
        return row

    @staticmethod
    def _candidates(part_category, part_name=""):
        """부품 타입의 후보 목록. 데이터시트를 못 읽어도 DB 응답은 살린다."""
        try:
            rows = datasheet.candidates(part_category)
            if part_name:
                datasheet.selected_candidate(part_category, part_name)
            return rows
        except datasheet.DatasheetUnavailable as error:
            logging.warning("datasheet unavailable: %s", error)
            return []

    @classmethod
    def _priced(cls, row):
        """보드당 원가를 붙인다. 단가는 데이터시트, 수량은 DB 가 갖고 있다.

        후보가 여러 종이라 단가가 하나로 정해지지 않는다. selected 는 DB 가 실제로
        쓰는 부품의 단가이고, min/max 는 다른 후보로 바꿨을 때의 폭이다.
        """
        try:
            summary = datasheet.prices(row["part_category"], row["part_name"])
        except datasheet.DatasheetUnavailable as error:
            logging.warning("datasheet unavailable: %s", error)
            summary = {"unit_price_min": None, "unit_price_max": None,
                       "unit_price_selected": None, "candidate_count": 0}
        quantity = row["quantity_per_product"]
        row.update(summary)
        for bound in ("min", "max", "selected"):
            price = summary[f"unit_price_{bound}"]
            row[f"line_cost_{bound}"] = (
                None if price is None else round(price * quantity, 2))
        return row

    def job(self, values, parameters):
        self._no_query(parameters)
        return queries.job(uuid_value(values["job_id"], "job_id"))

    def units(self, values, parameters):
        self._no_query(parameters)
        return queries.units(uuid_value(values["job_id"], "job_id"))

    def slot_rates(self, values, parameters):
        self._no_query(parameters)
        return queries.slot_rates(positive(values["product_id"], "product_id"))

    def assembly_start(self, values, parameters):
        self._no_query(parameters)
        command = self._request_json()
        self._validate_start_command(command)
        try:
            return queries.create_job(command)
        except queries.DuplicateRequest as error:
            raise AssemblyRejected(409, "duplicate_request", str(error)) from error

    def assembly_current(self, values, parameters):
        self._no_query(parameters)
        snapshot = assembly_gateway.status()
        if snapshot.get("available") is False and snapshot.get("error_code") in {"UNAVAILABLE", "DB_ERROR", "INTERNAL_ERROR"}:
            self._raise_rejection(snapshot)
        return snapshot

    def _request_json(self):
        length = self.headers.get("Content-Length")
        if length is None or not length.isdecimal() or int(length) > MAX_REQUEST_BODY_BYTES:
            raise ValidationError("JSON request body must be at most 1000000 bytes")
        try:
            command_json = self.rfile.read(int(length)).decode("utf-8")
            command = json.loads(command_json)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValidationError("request body must be valid JSON") from error
        if not isinstance(command, dict):
            raise ValidationError("request body must be a JSON object")
        return command

    @staticmethod
    def _validate_start_command(command):
        if set(command) != {
            "command", "job_id", "product_code", "product_version",
            "requested_quantity", "recipe_version",
        }:
            raise ValidationError(
                "command, job_id, product_code, product_version, "
                "requested_quantity and recipe_version are required"
            )
        if command["command"] != "start":
            raise ValidationError("command must be start")
        command["job_id"] = uuid_value(command["job_id"], "job_id")
        for field in ("product_code", "product_version", "recipe_version"):
            if not isinstance(command[field], str) or not command[field].strip():
                raise ValidationError(f"{field} must be a nonblank string")
        quantity = command["requested_quantity"]
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValidationError("requested_quantity must be a positive integer")

    @staticmethod
    def _raise_rejection(result):
        error_code = result.get("error_code")
        message = result.get("message")
        if not isinstance(message, str) or not message:
            message = "assembly bridge rejected the request"
        if error_code == "BUSY":
            raise AssemblyRejected(409, "assembly_busy", message)
        if error_code in {"INVALID_REQUEST", "INVALID_RECIPE"}:
            raise AssemblyRejected(400, "invalid_request", message)
        if error_code == "FAULTED":
            raise AssemblyRejected(503, "assembly_faulted", message)
        if error_code == "PLAN_ONLY":
            raise AssemblyRejected(503, "assembly_execution_unavailable", message)
        raise AssemblyRejected(503, "assembly_unavailable", message)

    def _error(self, status, code, message):
        self._respond(status, {"error": {"code": code, "message": message}})

    def _respond(self, status, body):
        encoded = json.dumps(body, default=json_default, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        logging.info("%s - %s", self.address_string(), format % args)


def run(host="127.0.0.1", port=8000):
    validate_startup_configuration()
    with ThreadingHTTPServer((host, port), ApiHandler) as httpd:
        httpd.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Run the MainServer HTTP API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    arguments = parser.parse_args()
    run(arguments.host, arguments.port)


if __name__ == "__main__":
    main()
