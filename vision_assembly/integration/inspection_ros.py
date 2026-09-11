"""ROS 2 request/result/image transport for the existing durable S22 backend.

No HTTP listener, outbound upload, DB write, motor publisher or Endpoint process.
ROS imports stay in create_node/main so transport rules can be tested offline.
"""
import argparse
import copy
import fcntl
import hashlib
import json
from pathlib import Path
import uuid

from inspection_api import ApiError, IMAGE_NAME, LOCK, ROOT, Runner, Station, Store

PREFIX = '/vision/inspection'
MAX_CHUNK = 65536
MAX_IMAGE = 64 * 1024 * 1024


def canonical_id(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ApiError(400, 'invalid_identity') from None


def ros_record(record):
    """Preserve stored records, replacing legacy HTTP image links on the wire."""
    data = copy.deepcopy(record)
    info = data.get('image', {})
    info.pop('path', None)
    if info.get('ready'):
        info.update(service=PREFIX + '/get_image', slot_code='', max_chunk_bytes=MAX_CHUNK)
    for view in info.get('countermeasure_views', []):
        view.pop('path', None)
        view.update(service=PREFIX + '/get_image', max_chunk_bytes=MAX_CHUNK)
    data['transport'] = 'ros2'
    return data


class Transport:
    def __init__(self, store):
        self.store = store

    def submit(self, request):
        body = dict(inspection_id=request.inspection_id, job_id=request.job_id,
                    unit_id=request.unit_id)
        return ros_record(self.store.submit(body, canonical_id(request.inspection_id)))

    def get(self, request):
        return ros_record(self.store.get(canonical_id(request.inspection_id)))

    def image(self, request):
        iid = canonical_id(request.inspection_id)
        if not 1 <= request.max_bytes <= MAX_CHUNK or request.offset < 0:
            raise ApiError(400, 'invalid_image_range')
        record = self.store.get(iid)
        info = record['image']
        if not info.get('ready') or record['status'] != 'COMPLETED':
            raise ApiError(409, 'image_not_ready')
        if request.slot_code:
            info = next((v for v in info.get('countermeasure_views', [])
                         if v['slot_code'] == request.slot_code), None)
            if info is None:
                raise ApiError(404, 'countermeasure_image_unavailable')
        name = info.get('filename', IMAGE_NAME)
        directory = (self.store.root / iid).resolve()
        path = directory / name
        if (Path(name).name != name or not name.endswith('.png')
                or path.resolve().parent != directory):
            raise ApiError(409, 'image_integrity_error')
        try:
            with path.open('rb') as stream:
                png = stream.read(MAX_IMAGE + 1)
        except OSError:
            raise ApiError(409, 'image_unavailable') from None
        digest = hashlib.sha256(png).hexdigest()
        if (len(png) > MAX_IMAGE or not png.startswith(b'\x89PNG\r\n\x1a\n')
                or digest != info.get('sha256') or len(png) != info.get('size_bytes')):
            raise ApiError(409, 'image_integrity_error')
        if request.offset > len(png):
            raise ApiError(400, 'invalid_image_range')
        chunk = png[request.offset:request.offset + request.max_bytes]
        return dict(inspection_id=iid, slot_code=request.slot_code, filename=name,
                    mime_type='image/png', sha256=digest, total_bytes=len(png),
                    offset=request.offset, eof=request.offset + len(chunk) == len(png),
                    data=chunk)


def callback(operation, *, image=False):
    def handle(request, response):
        try:
            result = operation(request)
            if image:
                for key, value in result.items():
                    setattr(response, key, value)
            else:
                response.record_json = json.dumps(result, separators=(',', ':'))
            response.success = True
            response.error_code = ''
        except ApiError as exc:
            response.success, response.error_code = False, exc.code
        except Exception:
            response.success, response.error_code = False, 'internal_error'
        return response
    return handle


def create_node(store, station, *, context=None):
    import rclpy
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, qos_profile_sensor_data
    from std_msgs.msg import Bool, String
    from std_srvs.srv import Trigger
    from vision_interfaces.srv import SubmitInspection, GetInspection, GetInspectionImage

    node = rclpy.create_node('vision_inspection_server', context=context)
    try:
        transport = Transport(store)
        for name, service, method in (
                ('submit', SubmitInspection, transport.submit),
                ('get', GetInspection, transport.get),
                ('get_image', GetInspectionImage, transport.image)):
            node.create_service(service, PREFIX + '/' + name,
                                callback(method, image=name == 'get_image'))

        def health(_request, response):
            # This is server availability, not permission to capture or move.
            with store.lock:
                response.success = not store.closing
                response.message = json.dumps(dict(transport='ros2',
                    station_ready=station.ready(), active_inspection_id=store.active,
                    closing=store.closing), separators=(',', ':'))
            return response

        node.create_service(Trigger, PREFIX + '/health', health)
        for key, topic in [('moving', '/conveyor/moving'),
                           ('arrived', '/vision/conveyor/inspection/stop_trigger')]:
            node.create_subscription(Bool, topic,
                lambda msg, key=key: station.update(key, msg.data), qos_profile_sensor_data)

        publisher = node.create_publisher(String, PREFIX + '/state', QoSProfile(
            depth=32, reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL))
        # Hints only: intermediate transitions may coalesce. Durable get is
        # authoritative after reconnect/restart; never submit again with a new ID.
        with store.lock:
            sent = {iid: r['status'] for iid, r in store.records.items()}
            for iid in list(sent)[-32:]:
                sent.pop(iid)

        def publish_changes():
            with store.lock:
                changes = [dict(inspection_id=iid, job_id=r['job_id'], unit_id=r['unit_id'],
                                status=r['status'], decision=r.get('result', {}).get('decision'),
                                error=r.get('error'))
                           for iid, r in store.records.items() if sent.get(iid) != r['status']]
            for change in changes:
                publisher.publish(String(data=json.dumps(change, separators=(',', ':'))))
                sent[change['inspection_id']] = change['status']

        node.create_timer(0.2, publish_changes)
        return node
    except BaseException:
        node.destroy_node()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=300)
    parser.add_argument('--state-dir', type=Path, default=ROOT / 'runtime/inspection/api')
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 3600:
        parser.error('--timeout must be in (0, 3600] seconds')
    import rclpy
    from rclpy.executors import ExternalShutdownException
    # Fail on missing interface builds before taking ownership of the camera.
    from vision_interfaces.srv import SubmitInspection, GetInspection, GetInspectionImage

    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        runner = Runner(args.timeout, lock.fileno(), source_topic=PREFIX + '/submit')
        station = Station()
        store = Store(args.state_dir, station.ready, runner)
        node = None
        rclpy.init()
        try:
            node = create_node(store, station)
            node.get_logger().info('ROS inspection services ready; capture requires an explicit submit')
            rclpy.spin(node)
        except (KeyboardInterrupt, ExternalShutdownException):
            pass
        finally:
            with store.lock:
                store.closing = True
            runner.stop.set()
            if store.thread:
                store.thread.join()
            if node is not None:
                node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()


if __name__ == '__main__':
    main()
