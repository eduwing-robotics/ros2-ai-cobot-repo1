"""Sequencer example: ROS submit/get and verified PNG download, no HTTP.

Without --job-id/--unit-id this is read-only. With both, it requests a real
inspection; callers must retain inspection_id across timeout/reconnection.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import uuid

PREFIX = '/vision/inspection'


def download_image(fetch, iid, slot, target, expected):
    """Validate every chunk's identity and final bytes before publishing a file."""
    temporary = target.with_name(target.name + '.part')
    offset = 0
    digest = hashlib.sha256()
    try:
        with temporary.open('wb') as stream:
            while True:
                response = fetch(iid, slot, offset, 65536)
                if not response.success:
                    raise RuntimeError(response.error_code)
                chunk = bytes(response.data)
                if (response.inspection_id != iid or response.slot_code != slot
                        or response.offset != offset or response.mime_type != 'image/png'
                        or response.filename != expected['filename']
                        or response.total_bytes != expected['size_bytes']
                        or response.sha256 != expected['sha256'] or len(chunk) > 65536
                        or offset + len(chunk) > response.total_bytes
                        or (not chunk and not response.eof)
                        or response.eof != (offset + len(chunk) == response.total_bytes)):
                    raise RuntimeError('image_chunk_mismatch')
                stream.write(chunk)
                digest.update(chunk)
                offset += len(chunk)
                if response.eof:
                    break
        if offset != expected['size_bytes'] or digest.hexdigest() != expected['sha256']:
            raise RuntimeError('image_integrity_error')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspection-id', required=True, type=uuid.UUID)
    parser.add_argument('--job-id', type=uuid.UUID)
    parser.add_argument('--unit-id', type=int)
    parser.add_argument('--wait', type=float, default=0,
                        help='Seconds to poll an accepted/running inspection; default query once')
    parser.add_argument('--output', type=Path, help='Save JSON and the selected PNG in this directory')
    parser.add_argument('--slot', default='', help='Empty: report; ALL or slot code: countermeasure')
    args = parser.parse_args(argv)
    if ((args.job_id is None) != (args.unit_id is None)
            or args.unit_id is not None and not 0 < args.unit_id < 2**63
            or not 0 <= args.wait <= 3600):
        parser.error('Provide job-id and positive int64 unit-id together; wait must be 0..3600')

    import rclpy
    from vision_interfaces.srv import SubmitInspection, GetInspection, GetInspectionImage
    rclpy.init()
    node = rclpy.create_node('inspection_ros_client')
    clients = {}

    def call(kind, name, request):
        client = clients.get(name)
        if client is None:
            client = clients[name] = node.create_client(kind, PREFIX + '/' + name)
        if not client.wait_for_service(timeout_sec=5):
            raise TimeoutError('service unavailable: ' + name)
        future = client.call_async(request)
        rclpy.spin_until_future_complete(node, future, timeout_sec=10)
        if not future.done():
            client.remove_pending_request(future)
            raise TimeoutError('response unknown; query the SAME inspection_id: ' + args.inspection_id.hex)
        response = future.result()
        if not response.success:
            raise RuntimeError(response.error_code)
        return response

    iid = str(args.inspection_id)
    try:
        if args.job_id is not None:
            response = call(SubmitInspection, 'submit', SubmitInspection.Request(
                inspection_id=iid, job_id=str(args.job_id), unit_id=args.unit_id))
        else:
            response = call(GetInspection, 'get', GetInspection.Request(inspection_id=iid))
        record = json.loads(response.record_json)
        deadline = time.monotonic() + args.wait
        while record['status'] in ('ACCEPTED', 'RUNNING') and time.monotonic() < deadline:
            time.sleep(min(0.5, max(0, deadline - time.monotonic())))
            response = call(GetInspection, 'get', GetInspection.Request(inspection_id=iid))
            record = json.loads(response.record_json)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        if args.output:
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / (iid + '.json')).write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + '\n')
            if record['status'] == 'COMPLETED' and record['image']['ready']:
                info = record['image']
                if args.slot:
                    info = next((v for v in info.get('countermeasure_views', [])
                                 if v['slot_code'] == args.slot), None)
                    if info is None:
                        raise RuntimeError('countermeasure_image_unavailable')
                if Path(info['filename']).name != info['filename']:
                    raise RuntimeError('invalid_image_filename')

                def fetch(iid, slot, offset, count):
                    return call(GetInspectionImage, 'get_image', GetInspectionImage.Request(
                        inspection_id=iid, slot_code=slot, offset=offset, max_bytes=count))

                download_image(fetch, iid, args.slot,
                               args.output / (iid + '_' + info['filename']), info)
        return 1 if record['status'] == 'FAILED' else 0
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
