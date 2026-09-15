#!/usr/bin/env python3
"""Read-only paired RGB/JPEG diagnostic; never imports robot command services."""
import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image, CompressedImage
from fairino_msgs.msg import RobotNonrtState
from ultralytics import YOLO
from smd_set_selection import select_smd_set
from smd_terminal_axis import terminal_axis_from_obb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--frames', type=int, default=60)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root/'config/smd_section_view.json').read_text())
    rclpy.init()
    node = Node('smd_frame_jitter_readonly')
    raw, jpeg, states = {}, {}, []
    stamp = lambda m: m.header.stamp.sec * 10**9 + m.header.stamp.nanosec
    node.create_subscription(Image, '/camera/camera/color/image_raw',
                             lambda m: raw.setdefault(stamp(m), m), qos_profile_sensor_data)
    node.create_subscription(CompressedImage, '/camera/camera/color/image_raw/compressed',
                             lambda m: jpeg.setdefault(stamp(m), bytes(m.data)), qos_profile_sensor_data)
    node.create_subscription(RobotNonrtState, '/nonrt_state_data', states.append, 10)
    records = []
    end = time.monotonic() + 25
    try:
        while len(records) < args.frames and time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=.05)
            if not states:
                continue
            s = states[-1]
            pose = np.array([getattr(s, 'cart_'+k+'_cur_pos') for k in 'xyzabc'])
            ref = np.array(cfg['reference_tcp_base'])
            if (s.robot_motion_done != 1 or np.max(abs(pose[:3]-ref[:3])) > 1
                    or np.max(abs((pose[3:]-ref[3:]+180)%360-180)) > .2
                    or any(getattr(s, k) != 0 for k in
                           ['emg','abnormal_stop','main_error_code','sub_error_code','collision_err'])):
                raise RuntimeError('robot is not stationary at SMDSectionView or fault is present')
            for key in sorted(raw.keys() & jpeg.keys()):
                m, encoded = raw.pop(key), jpeg.pop(key)
                if abs(time.time()-key/1e9) > 2:
                    continue
                if m.encoding not in ('rgb8', 'bgr8'):
                    raise RuntimeError('unsupported RGB encoding '+m.encoding)
                pixels = np.frombuffer(m.data, np.uint8).reshape(m.height, m.step)
                pixels = pixels[:, :m.width*3].reshape(m.height,m.width,3)
                if m.encoding == 'rgb8':
                    pixels = cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR)
                index = len(records)
                cv2.imwrite(str(args.output/f'{index:03d}_raw.png'), pixels)
                (args.output/f'{index:03d}_jpeg.jpg').write_bytes(encoded)
                records.append(dict(index=index, stamp_ns=key, tcp=pose.tolist()))
                if len(records) == args.frames:
                    break
            for cache in (raw,jpeg):
                for key in list(cache):
                    if time.time()-key/1e9 > 2:
                        del cache[key]
        if len(records) != args.frames:
            raise RuntimeError(f'only {len(records)} matched raw/JPEG frames')
    finally:
        node.destroy_node()
        rclpy.shutdown()
        (args.output/'capture.json').write_text(json.dumps(records, indent=2))
    print(f'Captured {len(records)} timestamp-matched RGB/JPEG pairs', flush=True)
    model = YOLO(str(root/'models/smd_obb/pilot_06/weights/best.pt'))
    w,h = cfg['canonical_size']
    dst = np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
    previous = json.loads((root/'data/smd02_close_repeat_2026-09-05.json').read_text())
    fixed_center = np.median([s['center'] for s in previous['samples']],axis=0)
    cx,cy = np.rint(fixed_center).astype(int)
    reference = None
    results = []
    for row in records:
        for kind, suffix in [('raw','raw.png'),('jpeg','jpeg.jpg')]:
            im = cv2.imread(str(args.output/f"{row['index']:03d}_{suffix}"))
            scale = np.float32([im.shape[1],im.shape[0]])/cfg['source_image_size']
            H = cv2.getPerspectiveTransform(np.float32(cfg['section_polygon_pixel'])*scale.astype(np.float32),dst)
            rect = cv2.warpPerspective(im,H,(w,h),flags=cv2.INTER_CUBIC)
            crop = rect[cy-45:cy+45,cx-45:cx+45]
            gray = cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
            if reference is None:
                reference = gray.astype(np.float32)
            window = cv2.createHanningWindow((90,90),cv2.CV_32F)
            shift,response = cv2.phaseCorrelate(reference.copy(),gray.astype(np.float32),window)
            pred = model.predict(rect,imgsz=960,conf=.5,device='0',verbose=False)[0]
            result = dict(index=row['index'],kind=kind,brightness=float(gray.mean()),
                          bright_fraction=float(np.mean(gray>=245)),
                          sharpness=float(cv2.Laplacian(gray,cv2.CV_64F).var()),
                          image_shift_px=list(shift),image_shift_response=response)
            try:
                items = [dict(box=b,center=b.mean(0)) for b in pred.obb.xyxyxyxy.cpu().numpy()]
                item = select_smd_set(items,cfg['set_layout'],1,consumed_prefix_count=1)[1]
                # Diagnostic extraction only; normal 1.35 validity is reported separately.
                axis = terminal_axis_from_obb(item['box'],minimum_axis_ratio=1.0)
                result.update(center=item['center'].tolist(),box=item['box'].tolist(),
                              angle=axis['angle_canonical_deg'],axis_ratio=axis['axis_ratio'],
                              axis_gate_passed=axis['axis_ratio']>=1.35)
            except (RuntimeError,ValueError,AttributeError) as exc:
                result['error'] = str(exc)
            results.append(result)
    output = dict(robot_motion_authorized=False, diagnostic_only=True,
                  capture=records,results=results,roi_center=fixed_center.tolist())
    (args.output/'analysis.json').write_text(json.dumps(output,indent=2))
    for kind in ('raw','jpeg'):
        rows = [r for r in results if r['kind']==kind and 'center' in r]
        centers = np.array([r['center'] for r in rows])
        print(kind, json.dumps(dict(count=len(rows),center_span_px=np.ptp(centers,axis=0).tolist(),
              axis_gate_passed=sum(r['axis_gate_passed'] for r in rows))))


if __name__ == '__main__':
    main()
