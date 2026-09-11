#!/usr/bin/env python3
"""Download one completed Vision ROS inspection record and annotated PNG."""

import argparse
import hashlib
import json
from pathlib import Path

import rclpy
from vision_interfaces.srv import GetInspection, GetInspectionImage


def call(node, client, request, timeout=15.0):
    if not client.wait_for_service(timeout_sec=timeout):
        raise RuntimeError(f"service unavailable: {client.srv_name}")
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future, timeout_sec=timeout)
    if not future.done() or future.cancelled() or future.exception() is not None:
        raise RuntimeError(f"service call failed or timed out: {client.srv_name}")
    return future.result()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inspection_id")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rclpy.init()
    node = rclpy.create_node("vision_result_downloader")
    try:
        get_client = node.create_client(GetInspection, "/vision/inspection/get")
        record_response = call(
            node, get_client, GetInspection.Request(inspection_id=args.inspection_id))
        if not record_response.success:
            raise RuntimeError(f"get failed: {record_response.error_code}")
        record = json.loads(record_response.record_json)
        if record.get("status") != "COMPLETED":
            raise RuntimeError(f"inspection is not complete: {record.get('status')}")

        json_path = args.output_dir / f"inspection_{args.inspection_id}.json"
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        image_client = node.create_client(GetInspectionImage, "/vision/inspection/get_image")
        content = bytearray()
        expected_total = None
        expected_sha256 = None
        filename = None
        while True:
            request = GetInspectionImage.Request(
                inspection_id=args.inspection_id, slot_code="",
                offset=len(content), max_bytes=65536)
            response = call(node, image_client, request)
            if not response.success:
                raise RuntimeError(f"get_image failed: {response.error_code}")
            if response.offset != len(content):
                raise RuntimeError(f"unexpected offset: {response.offset} != {len(content)}")
            expected_total = response.total_bytes
            expected_sha256 = response.sha256
            filename = response.filename
            content.extend(response.data)
            if response.eof:
                break

        if len(content) != expected_total:
            raise RuntimeError(f"image size mismatch: {len(content)} != {expected_total}")
        actual_sha256 = hashlib.sha256(content).hexdigest()
        if actual_sha256 != expected_sha256:
            raise RuntimeError(f"image SHA-256 mismatch: {actual_sha256} != {expected_sha256}")
        image_path = args.output_dir / f"inspection_{args.inspection_id}_{filename}"
        image_path.write_bytes(content)
        print(json.dumps({
            "json": str(json_path), "image": str(image_path),
            "image_bytes": len(content), "sha256": actual_sha256,
        }, ensure_ascii=False))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
