"""Real orchestration API client and Vision HTTP boundary; no hardware drivers."""

import hashlib
import http.client
import json
import math
import os
import threading
import time
import uuid
from urllib.parse import urlsplit


class RealBackend:
    """Use documented equipment APIs only; never fall back to raw robot commands."""

    def __init__(self, node):
        from rclpy.callback_groups import ReentrantCallbackGroup
        from std_msgs.msg import Bool
        from std_srvs.srv import Trigger

        if node.runtime_mode != "real" or node.context.get_domain_id() != 43:
            raise RuntimeError("MODE_REJECTED stage=real_backend expected=real/domain43 result=blocked")
        self._node = node
        self._closed = False
        self._inspection_future = None
        self._pending_calls = set()
        self._vision_url = node.declare_parameter("vision_base_url", "").value
        self._status_client = node.create_client(
            Trigger, "/real/robot/status", callback_group=ReentrantCallbackGroup()
        )
        self._pause_publisher = node.create_publisher(Bool, "/real/robot/pause", 10)

    def is_available(self):
        return not self._closed and self._status_client.wait_for_service(timeout_sec=0.0)

    @staticmethod
    def _connection_error():
        return (
            "NOT_READY: robot operation command/event adapter and recipe field mapping "
            "are not connected; direct SDK, FAIRINO commands and IO fallback are prohibited"
        )

    async def status(self):
        from .recipe_contract import unavailable_snapshot
        from std_srvs.srv import Trigger

        snapshot = unavailable_snapshot(self._connection_error())
        snapshot.update(runtime_mode="real", equipment_ready=False, error_code="NOT_READY",
                        command_service_available=self.is_available())
        if not self.is_available():
            return snapshot
        future = self._status_client.call_async(Trigger.Request())
        self._pending_calls.add(future)
        timer = self._node.create_timer(5.0, future.cancel)
        try:
            response = await future
            if future.cancelled():
                raise TimeoutError("robot API status response timed out")
            if not response.success:
                raise RuntimeError(f"robot API status failed: {response.message}")
            data = json.loads(response.message)
            if not isinstance(data, dict):
                raise ValueError("robot API status must be a JSON object")
            # API availability does not prove that this runner's operation adapter
            # or the robot's hardware execution is ready. Preserve both boundaries.
            snapshot["robot_api_status"] = data
            return snapshot
        finally:
            self._pending_calls.discard(future)
            self._node.destroy_timer(timer)

    async def prepare(self, joint_points, frame):
        raise RuntimeError(self._connection_error())

    async def start(self, job_id, recipe_version, expected_step_count):
        raise RuntimeError(self._connection_error())

    async def move_joint(self, job_id, joint_point):
        raise RuntimeError(self._connection_error())

    async def pick(self, job_id, step, frame, source, motion, gripper):
        raise RuntimeError(self._connection_error())

    async def place(self, job_id, step, frame, target, motion, gripper):
        raise RuntimeError(self._connection_error())

    async def transfer_assembled_pcb(self, job_id, frame, assembled_pcb, motion, gripper):
        raise RuntimeError(self._connection_error())

    async def move_conveyor(self, job_id, station):
        raise RuntimeError("NOT_READY: conveyor service/state adapter is not connected; direct IO is prohibited")

    async def resolve_targets(self, observations):
        raise RuntimeError("NOT_READY: robot-side vision preparation API is not connected")

    async def set_paused(self, job_id, paused):
        from std_msgs.msg import Bool

        if self._closed:
            raise RuntimeError("Real API client is closed")
        if not paused:
            raise RuntimeError("NOT_READY: robot API does not provide resume/cancel")
        self._pause_publisher.publish(Bool(data=True))
        # Publishing Bool has no acknowledgment. Do not report physical pause
        # completion until the operation-event adapter is connected.
        raise RuntimeError("pause requested through API; physical PAUSED event is not yet confirmed")

    def accept_operation_feedback(self, payload):
        return False

    async def inspect_unit(self, job_id, unit_id, slot_codes):
        from rclpy.task import Future

        if self._closed or self._inspection_future is not None:
            raise RuntimeError("Real backend is closed or another inspection is pending")
        future = Future(executor=self._node.executor)
        self._inspection_future = future
        inspection_id = str(uuid.uuid5(uuid.UUID(job_id), f"unit:{unit_id}"))

        def run():
            try:
                output = inspect(inspection_id, job_id, unit_id, base_url=self._vision_url)
                data = output["data"]
                value = {
                    "result": data["result"]["decision"], "defects": None,
                    "image_path": None, "inspection": data,
                    "image_bytes": output["image_bytes"],
                }
                if not future.done():
                    future.set_result(value)
            except Exception as error:
                if not future.done():
                    future.set_exception(error)

        # Vision capture and HTTP polling must not block the ROS executor. The
        # existing inspect function retries only the same inspection identity;
        # cancelling this local Future does not cancel the remote inspection.
        threading.Thread(target=run, name="real-vision-inspection", daemon=True).start()
        try:
            return await future
        finally:
            if self._inspection_future is future:
                self._inspection_future = None

    def close(self):
        if self._closed:
            return
        self._closed = True
        for future in tuple(self._pending_calls):
            future.cancel()
        if self._inspection_future is not None:
            self._inspection_future.cancel()
        self._node.destroy_client(self._status_client)
        self._node.destroy_publisher(self._pause_publisher)


def inspect(inspection_id, job_id, unit_id, *, base_url, token=None,
            timeout=330.0, request_timeout=10.0, poll_interval=1.0):
    """Run or retrieve one inspection and return ``{data: dict, image_bytes: bytes | None}``.

    The caller owns persistent inspection IDs and UNKNOWN/reinspection policy.
    This blocking call belongs on a worker, never a ROS executor callback thread.
    ``data`` retains the Vision JSON fields unchanged; image_bytes is not JSON.
    FAILED raises RuntimeError; transport/deadline expiry raises TimeoutError.
    A client timeout does not cancel Vision: retry with the same three IDs.
    """
    for name, value in (("inspection_id", inspection_id), ("job_id", job_id)):
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError(f"{name} must be a canonical UUID string")
    if type(unit_id) is not int or unit_id <= 0:
        raise ValueError("unit_id must be a positive integer")
    for value in (timeout, request_timeout, poll_interval):
        if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
            raise ValueError("timeouts and poll_interval must be finite and positive")
    token = os.environ.get("KSMC_VISION_API_TOKEN", "") if token is None else token
    if (not isinstance(token, str) or len(token) < 32
            or not token.isascii() or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in token)):
        raise ValueError("a valid KSMC_VISION_API_TOKEN of at least 32 characters is required")
    url = urlsplit(base_url)
    if (url.scheme not in ("http", "https") or not url.hostname
            or url.username is not None or url.password is not None
            or url.path not in ("", "/") or url.query or url.fragment):
        raise ValueError("base_url must be an HTTP(S) origin without credentials")
    port = url.port
    connection_type = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
    identity = {"inspection_id": inspection_id, "job_id": job_id, "unit_id": unit_id}
    path = f"/api/v1/inspections/{inspection_id}"
    deadline = time.monotonic() + timeout

    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError(f"Vision inspection {inspection_id} timed out; remote execution may continue")
        return seconds

    def request(method, target, payload=None):
        connection = connection_type(url.hostname, port, timeout=min(request_timeout, remaining()))
        headers = {"Authorization": f"Bearer {token}"}
        if payload is not None:
            headers.update({"Content-Type": "application/json", "Idempotency-Key": inspection_id})
        try:
            connection.request(method, target, body=json.dumps(payload) if payload is not None else None,
                               headers=headers)
            response = connection.getresponse()
            body = response.read()
            remaining()
            return response.status, {k.lower(): v for k, v in response.getheaders()}, body
        finally:
            connection.close()

    method, target, payload = "POST", "/api/v1/inspections", identity
    while True:
        remaining()
        try:
            code, _, body = request(method, target, payload)
        except (OSError, http.client.HTTPException):
            # POST may already have started capture. Resolve that same ID before retrying.
            method, target, payload = "GET", path, None
            time.sleep(min(poll_interval, remaining()))
            continue
        if code == 404 and method == "GET":
            method, target, payload = "POST", "/api/v1/inspections", identity
            time.sleep(min(poll_interval, remaining()))
            continue
        if code != (202 if method == "POST" else 200):
            raise RuntimeError(f"Vision {method} {target} returned HTTP {code}: {body[:512]!r}")
        envelope = json.loads(body)
        data = envelope.get("data") if isinstance(envelope, dict) else None
        if (not isinstance(data, dict) or any(data.get(k) != v for k, v in identity.items())
                or type(data.get("unit_id")) is not int):
            raise ValueError("Vision response identity does not match the request")
        status = data.get("status")
        if status == "FAILED":
            raise RuntimeError(f"Vision inspection {inspection_id} FAILED: {data.get('error')!r}")
        if status == "COMPLETED":
            # Retrieve the authoritative completed JSON even when POST returns an existing result.
            if method == "GET":
                break
        elif status not in ("ACCEPTED", "RUNNING"):
            raise ValueError("unexpected Vision inspection status")
        method, target, payload = "GET", path, None
        time.sleep(min(poll_interval, remaining()))

    result, image = data.get("result"), data.get("image")
    if not isinstance(result, dict) or result.get("decision") not in ("PASS", "FAIL", "UNKNOWN"):
        raise ValueError("Vision completed result must contain an explicit decision")
    if not isinstance(image, dict) or type(image.get("ready")) is not bool:
        raise ValueError("Vision result must contain image.ready")
    if not image["ready"]:
        return {"data": data, "image_bytes": None}
    # Only the same inspection's relative endpoint receives the bearer token; no redirects.
    if (image.get("path") != path + "/image"
            or image.get("filename") != "02_annotated_report.png"
            or image.get("mime_type") != "image/png"
            or type(image.get("size_bytes")) is not int or image["size_bytes"] <= 0
            or not isinstance(image.get("sha256"), str)):
        raise ValueError("invalid Vision image metadata")
    while True:
        try:
            code, headers, png = request("GET", image["path"])
            break
        except (OSError, http.client.HTTPException):
            time.sleep(min(poll_interval, remaining()))
    if code != 200:
        raise RuntimeError(f"Vision image returned HTTP {code}")
    digest = hashlib.sha256(png).hexdigest()
    if (not png.startswith(b"\x89PNG\r\n\x1a\n")
            or headers.get("content-type", "").split(";", 1)[0] != "image/png"
            or headers.get("content-disposition") != 'inline; filename="02_annotated_report.png"'
            or len(png) != image["size_bytes"]
            or headers.get("content-length") != str(len(png))
            or digest != image["sha256"] or digest != headers.get("x-content-sha256")):
        raise ValueError("Vision PNG content, size or SHA256 does not match its metadata")
    return {"data": data, "image_bytes": png}


def _self_check():
    import copy
    from unittest.mock import patch

    identity = {"inspection_id": str(uuid.uuid4()), "job_id": str(uuid.uuid4()), "unit_id": 1}
    png = b"\x89PNG\r\n\x1a\ncheck"
    digest = hashlib.sha256(png).hexdigest()
    data = dict(identity, status="COMPLETED", result={"decision": "UNKNOWN", "defects": []},
                image={"ready": True, "path": f"/api/v1/inspections/{identity['inspection_id']}/image",
                       "filename": "02_annotated_report.png", "mime_type": "image/png",
                       "size_bytes": len(png), "sha256": digest})
    headers = {"Content-Type": "image/png", "Content-Length": str(len(png)),
               "X-Content-SHA256": digest,
               "Content-Disposition": 'inline; filename="02_annotated_report.png"'}

    def run(final, image_body=png, lost_post=False):
        responses = [(202, {}, json.dumps({"data": dict(identity, status="ACCEPTED")}).encode()),
                     (200, {}, json.dumps({"data": final}).encode()), (200, headers, image_body)]
        calls = []

        class Connection:
            def __init__(self, *args, **kwargs):
                pass

            def request(self, method, target, body=None, headers=None):
                calls.append((method, target, body))

            def getresponse(self):
                self.status, self.headers, self.body = responses.pop(0)
                if lost_post and len(calls) == 1:
                    raise TimeoutError("lost POST response")
                return self

            def read(self):
                return self.body

            def getheaders(self):
                return self.headers.items()

            def close(self):
                pass

        with patch.object(http.client, "HTTPConnection", Connection):
            output = inspect(**identity, base_url="http://vision.invalid:8766", token="x" * 32,
                             poll_interval=0.001)
        assert [call[0] for call in calls].count("POST") == 1
        return output

    assert run(data, lost_post=True) == {"data": data, "image_bytes": png}
    unavailable = copy.deepcopy(data)
    unavailable["image"] = {"ready": False, "error": "legacy_zip_record"}
    assert run(unavailable)["image_bytes"] is None
    for field, value in (("status", "FAILED"), ("unit_id", 2)):
        invalid = copy.deepcopy(data)
        invalid[field] = value
        try:
            run(invalid)
        except (ValueError, RuntimeError):
            pass
        else:
            raise AssertionError(f"accepted invalid {field}")
    try:
        run(data, png + b"corrupt")
    except ValueError:
        pass
    else:
        raise AssertionError("accepted corrupt image")
    print("Vision backend self-check passed")


if __name__ == "__main__":
    _self_check()
