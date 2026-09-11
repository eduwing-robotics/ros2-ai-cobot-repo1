"""Opt-in real DDS test with synthetic images and an inert capture runner.

Run only on a dedicated localhost ROS domain; never creates a motor publisher.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

import pytest

pytestmark = pytest.mark.skipif(os.environ.get('KSMC_TEST_ROS_TRANSPORT') != '1',
                                reason='opt-in isolated DDS transport test')
sys.path.insert(0, str(Path(__file__).parent))


def test_gopro_watcher_uses_its_own_ros_context():
    assert os.environ.get('ROS_LOCALHOST_ONLY') == '1'
    assert os.environ.get('ROS_DOMAIN_ID') == '219'
    from sensor_msgs.msg import CompressedImage
    from rclpy.qos import qos_profile_sensor_data
    from server_bundle import RosGraph, GOPRO_TOPIC
    # No global rclpy.init(): using the global executor here used to fail.
    with RosGraph() as graph:
        graph.watch_gopro()
        assert not graph.gopro_ready()
        publisher = graph.node.create_publisher(CompressedImage, GOPRO_TOPIC, qos_profile_sensor_data)
        deadline = time.monotonic() + 3
        while not graph.gopro_ready() and time.monotonic() < deadline:
            publisher.publish(CompressedImage(format='jpeg', data=b'\xff\xd8test\xff\xd9'))
            time.sleep(.02)
        assert graph.gopro_ready()


def test_ros_services_state_and_chunk_roundtrip(tmp_path):
    assert os.environ.get('ROS_LOCALHOST_ONLY') == '1'
    assert os.environ.get('ROS_DOMAIN_ID') == '219'
    import rclpy
    from rclpy.context import Context
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
    from std_msgs.msg import Bool, String
    from std_srvs.srv import Trigger
    from vision_interfaces.srv import SubmitInspection, GetInspection, GetInspectionImage
    import inspection_ros as ros
    from inspection_ros_client import download_image
    from server_bundle import RosGraph, SERVICES

    blob = b'\x89PNG\r\n\x1a\n' + bytes(range(256)) * 700
    calls, events = [], []
    def run(request, directory):
        calls.append(request)
        (directory / ros.IMAGE_NAME).write_bytes(blob)
        return {'decision': 'UNKNOWN'}, dict(ready=True, filename=ros.IMAGE_NAME,
            size_bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest())

    station = ros.Station()
    store = ros.Store(tmp_path, station.ready, run)
    context = Context()
    rclpy.init(context=context)
    executor = SingleThreadedExecutor(context=context)
    nodes = []
    try:
        server = ros.create_node(store, station, context=context)
        nodes.append(server)
        client = rclpy.create_node('transport_test_client', context=context)
        nodes.append(client)
        mock_conveyor = rclpy.create_node('conveyor_remote_server', context=context)
        nodes.append(mock_conveyor)
        for node in nodes:
            executor.add_node(node)
        moving = mock_conveyor.create_publisher(Bool, '/conveyor/moving', 1)
        arrived = mock_conveyor.create_publisher(Bool, '/vision/conveyor/inspection/stop_trigger', 1)
        def signals():
            moving.publish(Bool(data=False))
            arrived.publish(Bool(data=True))
        timer = mock_conveyor.create_timer(.05, signals)
        client.create_subscription(String, ros.PREFIX + '/state',
            lambda msg: events.append(json.loads(msg.data)), QoSProfile(depth=32,
                durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE))
        clients = {}
        def call(kind, name, request):
            if name not in clients:
                clients[name] = client.create_client(kind, ros.PREFIX + '/' + name)
            channel = clients[name]
            assert channel.wait_for_service(timeout_sec=5), name
            future = channel.call_async(request)
            executor.spin_until_future_complete(future, timeout_sec=5)
            assert future.done(), name
            return future.result()

        iid, job = str(uuid.uuid4()), str(uuid.uuid4())
        req = SubmitInspection.Request(inspection_id=iid, job_id=job, unit_id=7)
        rejected = call(SubmitInspection, 'submit', req)
        assert not rejected.success and rejected.error_code == 'station_not_ready'
        deadline = time.monotonic() + 5
        while not station.ready() and time.monotonic() < deadline:
            executor.spin_once(timeout_sec=.05)
        assert station.ready()
        accepted = call(SubmitInspection, 'submit', req)
        assert accepted.success
        store.thread.join(3)
        complete = call(GetInspection, 'get', GetInspection.Request(inspection_id=iid))
        record = json.loads(complete.record_json)
        assert record['status'] == 'COMPLETED' and record['result']['decision'] == 'UNKNOWN'
        assert call(SubmitInspection, 'submit', req).success
        assert len(calls) == 1
        missing = call(GetInspection, 'get', GetInspection.Request(inspection_id=str(uuid.uuid4())))
        assert not missing.success and missing.error_code == 'inspection_not_found'

        def fetch(iid, slot, offset, count):
            return call(GetInspectionImage, 'get_image', GetInspectionImage.Request(
                inspection_id=iid, slot_code=slot, offset=offset, max_bytes=count))
        target = tmp_path / 'download.png'
        download_image(fetch, iid, '', target, record['image'])
        assert target.read_bytes() == blob
        bad = fetch(iid, '', 0, 65537)
        assert not bad.success and bad.error_code == 'invalid_image_range'
        health = call(Trigger, 'health', Trigger.Request())
        assert health.success and json.loads(health.message)['transport'] == 'ros2'

        # Client names alone must never satisfy supervisor readiness.
        for name in SERVICES:
            client.create_client(Trigger, name)
        graph = RosGraph()
        graph.node, graph.rclpy = client, rclpy
        assert not graph.ready()
        for name in SERVICES:
            mock_conveyor.create_service(Trigger, name, lambda _, response: response)
        deadline = time.monotonic() + 5
        while (not graph.ready() or not any(e['status'] == 'COMPLETED' for e in events)) and time.monotonic() < deadline:
            executor.spin_once(timeout_sec=.05)
        assert graph.ready()
        assert any(e['inspection_id'] == iid and e['decision'] == 'UNKNOWN' for e in events)
        assert not any(name == '/cmd_vel' for name, _ in client.get_topic_names_and_types())
        mock_conveyor.destroy_timer(timer)
    finally:
        with store.lock:
            store.closing = True
        if store.thread:
            store.thread.join(3)
        executor.shutdown()
        for node in reversed(nodes):
            node.destroy_node()
        context.shutdown()
