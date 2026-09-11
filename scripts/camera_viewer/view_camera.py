"""Receive compressed ROS camera frames before opening a local raw rqt view.

Run on the viewer PC. --check only subscribes and reports data reception; it
never starts rqt or publishes. No camera, Endpoint or motion control is used.
"""
import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

TOPICS = {
    's22': '/camera2/image_stream/compressed',
    'gopro': '/camera3/image_raw/compressed',
    'conveyor': '/vision/conveyor/stop_image/compressed',
    'assembly': '/vision/assembly/image/compressed',
}


def topic_name(value):
    value = TOPICS.get(value, value)
    if not value.startswith('/') or not value.endswith('/compressed') or ' ' in value:
        raise argparse.ArgumentTypeError('Use s22/gopro/conveyor/assembly or an absolute /.../compressed topic')
    return value


def diagnose(publishers, received, decoded):
    if not publishers:
        return 'NO_PUBLISHER: check ROS_DOMAIN_ID, discovery, source process and network'
    if not any(p.topic_type == 'sensor_msgs/msg/CompressedImage' for p in publishers):
        return 'WRONG_TYPE: the selected topic is not sensor_msgs/msg/CompressedImage'
    if not received:
        return 'NO_FRAMES: discovery works; check publisher output, DDS interfaces, firewall and Wi-Fi isolation'
    if not decoded:
        return 'DECODE_FAILED: bytes arrived but no valid JPEG/PNG could be decoded'
    return 'OK: compressed bytes and decoded image received on this PC'


def decode(message):
    import cv2
    import numpy as np
    try:
        return cv2.imdecode(np.frombuffer(message.data, dtype=np.uint8), cv2.IMREAD_COLOR)
    except (cv2.error, ValueError):
        return None


def raw_image(message, pixels, image_type):
    # No cv_bridge or image_transport plugin is needed in this receiver.
    image = image_type()
    image.header = message.header
    image.height, image.width = pixels.shape[:2]
    image.encoding = 'bgr8'
    image.is_bigendian = False
    image.step = image.width * 3
    image.data = pixels.tobytes()
    return image


def stop_owned(child):
    if child is None:
        return
    # Only the newly spawned viewer's session, never an existing rqt/Endpoint.
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(child.pid, sig)
        except ProcessLookupError:
            break
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            continue
        break


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('topic', nargs='?', default='conveyor', type=topic_name)
    parser.add_argument('--check', action='store_true', help='Read-only frame test; no GUI or publication')
    parser.add_argument('--seconds', type=float, default=8, help='Frame check / first-frame timeout')
    parser.add_argument('--fps', type=float, default=15, help='Local display cap, not source camera FPS')
    args = parser.parse_args(argv)
    if not math.isfinite(args.seconds) or not 1 <= args.seconds <= 120 or not 1 <= args.fps <= 60:
        parser.error('seconds must be 1..120 and fps must be 1..60')
    try:
        import rclpy
        from rclpy.executors import ExternalShutdownException
        from rclpy.qos import QoSProfile, ReliabilityPolicy
        from sensor_msgs.msg import CompressedImage, Image
        import cv2
        import numpy
    except ImportError as exc:
        parser.error(f'Source ROS first; install python3-opencv and ROS sensor_msgs: {exc}')
    viewer = None
    if not args.check:
        from ament_index_python.packages import get_package_prefix, PackageNotFoundError
        try:
            prefix = get_package_prefix('rqt_image_view')
        except PackageNotFoundError:
            parser.error('Install ros-$ROS_DISTRO-rqt-image-view on this viewer PC')
        viewer = Path(prefix) / 'lib/rqt_image_view/rqt_image_view'
        if not viewer.is_file():
            parser.error('rqt_image_view executable not found')

    print(json.dumps(dict(topic=args.topic, domain=os.environ.get('ROS_DOMAIN_ID', '0'),
        localhost_only=os.environ.get('ROS_LOCALHOST_ONLY'),
        discovery=os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE'),
        rmw=os.environ.get('RMW_IMPLEMENTATION'),
        dds_profile=os.environ.get('FASTRTPS_DEFAULT_PROFILES_FILE')), ensure_ascii=False), flush=True)
    rclpy.init()
    node = rclpy.create_node('ksmc_camera_view_' + str(os.getpid()))
    latest = [None]
    counts = dict(received=0, decoded=0)
    first_at = last_at = None
    first_shape = None
    publisher = child = viewer_settings = None
    output_topic = '/ksmc/rqt_' + str(os.getpid()) + '/image'
    started = time.monotonic()
    last_decode = -math.inf
    last_valid = None

    def receive(message):
        nonlocal first_at, last_at
        now = time.monotonic()
        first_at = now if first_at is None else first_at
        last_at = now
        counts['received'] += 1
        latest[0] = message  # Keep only the newest sample; no frame queue.

    node.create_subscription(CompressedImage, args.topic, receive, QoSProfile(
        depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=.05)
            now = time.monotonic()
            if latest[0] is not None and now - last_decode >= 1 / args.fps:
                message, latest[0] = latest[0], None
                last_decode = now
                pixels = decode(message)
                if pixels is not None:
                    counts['decoded'] += 1
                    last_valid = now
                    if first_shape is None:
                        first_shape = list(pixels.shape)
                        print(f'FRAME_OK {args.topic}: {first_shape}, {len(message.data)} bytes', flush=True)
                    if not args.check:
                        if publisher is None:
                            publisher = node.create_publisher(Image, output_topic, QoSProfile(
                                depth=1, reliability=ReliabilityPolicy.RELIABLE))
                            print('RQT_RAW_TOPIC ' + output_topic, flush=True)
                            # A raw Image topic works even when rqt discovers
                            # the publisher after startup; no compressed label
                            # parsing, cached transport, or plugin is involved.
                            viewer_settings = tempfile.TemporaryDirectory(prefix='ksmc_rqt_')
                            child = subprocess.Popen([str(viewer), output_topic], start_new_session=True,
                                env=dict(os.environ, XDG_CONFIG_HOME=viewer_settings.name))
                        publisher.publish(raw_image(message, pixels, Image))
            if args.check and now - started >= args.seconds:
                break
            if not args.check:
                if child is not None and child.poll() is not None:
                    return child.returncode
                if counts['decoded'] == 0 and now - started >= args.seconds:
                    break
                if last_valid is not None and now - last_valid > args.seconds:
                    print('SOURCE_STALE: closing this viewer instead of displaying a frozen frame', flush=True)
                    return 2
        pubs = node.get_publishers_info_by_topic(args.topic)
        result = dict(topic=args.topic, **counts, shape=first_shape,
            fps=(counts['received']-1)/(last_at-first_at) if counts['received'] > 1 else 0,
            publishers=[dict(node=p.node_name, type=p.topic_type,
                             reliability=str(p.qos_profile.reliability)) for p in pubs],
            diagnosis=diagnose(pubs, counts['received'], counts['decoded']))
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 0 if counts['decoded'] else 2
    except (KeyboardInterrupt, ExternalShutdownException):
        return 130
    finally:
        stop_owned(child)
        if viewer_settings is not None:
            viewer_settings.cleanup()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
