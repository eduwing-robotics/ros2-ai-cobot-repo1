#!/usr/bin/env python3
"""Fresh high-resolution edge coordinates, diagnostic only; no command client."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from scipy.spatial.transform import Rotation

from capture_smd_close_target import Capture, canonical_axis_base_angle, unwrap
from compare_smd_terminal_edges import estimate
from smd_set_selection import select_smd_set


def summarize(rows, gate):
    if len(rows) != 30:
        return {'stability_passed': False, 'reason': 'requires 30 accepted fresh frames'}
    if any(not np.isfinite(np.asarray(r[k], float)).all()
           for r in rows for k in ('center', 'angle', 'pose', 'base', 'base_angle')):
        return {'stability_passed': False, 'reason': 'nonfinite measurement'}
    c = np.array([r['center'] for r in rows])
    a = unwrap([r['angle'] for r in rows])
    batches = np.array([np.median(x) for x in np.split(a, 3)])
    mad = float(np.median(abs(batches - np.median(batches))))
    span = float(np.ptp(batches))
    poses = np.array([r['pose'] for r in rows])
    rotation_span = max(float(np.ptp(np.rad2deg(np.unwrap(np.deg2rad(poses[:, i]))))) for i in range(3, 6))
    translation_span = float(np.ptp(poses[:, :3], axis=0).max())
    center_span = np.ptp(c, axis=0)
    temporal = gate['temporal_median_gate']
    passed = (center_span.max() <= gate['max_center_span_canonical_px']
              and mad <= temporal['median_absolute_deviation_max_deg']
              and span <= temporal['max_batch_span_deg']
              and translation_span <= .5 and rotation_span <= .1)
    return dict(stability_passed=bool(passed), center_span_canonical_px=center_span.tolist(),
                angle_mad_deg=mad, angle_batch_span_deg=span,
                robot_translation_span_mm=translation_span, robot_rotation_span_deg=rotation_span,
                candidate_center_base_mm=np.median([r['base'] for r in rows], axis=0).tolist(),
                candidate_axis_base_deg=float(np.median(unwrap([r['base_angle'] for r in rows]))))


class EdgeCapture(Capture):
    def __init__(self, args):
        self.received = {}; self.rows = []; self.rejections = {}; self.seen = set()
        self.started = time.time(); self.roi = None; self.last_image = None
        super().__init__(args)

    def info_cb(self, m):
        super().info_cb(m); self.received['info'] = time.monotonic()

    def depth_cb(self, m):
        super().depth_cb(m); self.received['depth'] = time.monotonic()
        self.depth_stamp = m.header.stamp.sec + m.header.stamp.nanosec / 1e9

    def robot_cb(self, m):
        super().robot_cb(m); self.received['robot'] = time.monotonic()

    def complete(self):
        return len(self.rows) == 30

    def reject(self, reason):
        self.rejections[reason] = self.rejections.get(reason, 0) + 1

    def color_cb(self, m):
        if self.complete(): return
        stamp = m.header.stamp.sec + m.header.stamp.nanosec / 1e9
        if stamp in self.seen: return
        self.seen.add(stamp)
        if not 0 <= time.time() - stamp <= .5 or stamp < self.started:
            self.reject('stale_image'); return
        if any(time.monotonic() - self.received.get(k, -1e9) > .5 for k in ('info', 'depth', 'robot')):
            self.reject('stale_dependencies'); return
        if abs(stamp - self.depth_stamp) > .15:
            self.reject('depth_sync'); return
        s = self.robot
        faults = ('emg', 'abnormal_stop', 'main_error_code', 'sub_error_code', 'collision_err',
                  'alarm', 'safetydoor_alarm', 'safetyplanealarm', 'motionalarm', 'interferealarm',
                  'out_sflimit_err', 'strangeposflag', 'ctrlboxerror', 'cmdpointerror', 'paraerror')
        if s.robot_motion_done != 1 or any(float(getattr(s, k)) != 0 for k in faults):
            raise RuntimeError('robot not stopped or safety state not clear')
        tcp = np.array([getattr(s, f'cart_{k}_cur_pos') for k in 'xyzabc'])
        ref = np.array(self.cfg['reference_tcp_base'])
        if abs(tcp[:3]-ref[:3]).max() > 1 or abs((tcp[3:]-ref[3:]+180)%360-180).max() > .2:
            raise RuntimeError('robot is not at verified fixed-polygon reference pose')
        image = cv2.imdecode(np.frombuffer(m.data, np.uint8), cv2.IMREAD_COLOR)
        if image is None or image.shape[:2] != (1080, 1920) or self.depth.shape != (1080, 1920) or (self.info.width, self.info.height) != (1920, 1080):
            self.reject('resolution'); return
        dst = np.float32([[0,0],[self.width-1,0],[self.width-1,self.height-1],[0,self.height-1]])
        H = cv2.getPerspectiveTransform(np.float32(self.cfg['section_polygon_pixel']), dst)
        inv = np.linalg.inv(H)
        rect = cv2.warpPerspective(image, H, (self.width, self.height), flags=cv2.INTER_CUBIC)
        pred = self.model.predict(rect, imgsz=960, conf=.5, device='0', verbose=False)[0]
        items = []
        if pred.obb is not None:
            for box, score in zip(pred.obb.xyxyxyxy.cpu().numpy(), pred.obb.conf.cpu().numpy()):
                items.append(dict(box=box, center=box.mean(0), confidence=float(score)))
        try:
            item = select_smd_set(items, self.set_layout, 1, consumed_prefix_count=1)[1]
            if item is None: raise RuntimeError('SMD-02 missing')
            if self.roi is None: self.roi = np.array(item['center'])
            if np.linalg.norm(item['center'] - self.roi) > 10: raise ValueError('ROI identity drift')
            edge = estimate(rect, self.roi)
        except (ValueError, RuntimeError) as exc:
            self.reject(str(exc)); return
        pose = np.array([getattr(s, f'flange_{k}_cur_pos') for k in 'xyzabc'])
        Tbf = np.eye(4); Tbf[:3,:3] = Rotation.from_euler(self.euler, pose[3:], degrees=True).as_matrix()
        Tbf[:3,3] = pose[:3]/1000; Tbc = Tbf @ self.Tfc
        fx, fy, cx, cy = np.array(self.info.k)[[0,4,2,5]]
        uv = cv2.perspectiveTransform(np.float32([[edge['center']]]), inv)[0,0]
        ray = Tbc[:3,:3] @ np.array([(uv[0]-cx)/fx, (uv[1]-cy)/fy, 1.])
        scale = (-.047291 - Tbc[2,3])/ray[2]
        if not np.isfinite(scale) or scale <= 0: raise RuntimeError('invalid plane intersection')
        base = (Tbc[:3,3] + scale*ray)*1000
        self.rows.append(dict(edge, timestamp_unix=stamp, base=base.tolist(), pose=pose.tolist(),
                              source_pixel=uv.tolist(), base_angle=canonical_axis_base_angle(edge['center'], edge['angle'], inv, fx, fy, Tbc)))
        self.last_image = image
        self.get_logger().info(f'edge accepted {len(self.rows)}/30')


def main():
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--timeout', type=float, default=45)
    a = p.parse_args()
    if a.output.exists(): p.error('refusing to overwrite existing diagnostic')
    for k, v in dict(config=root/'config/smd_section_view.json', model=root/'models/smd_obb/pilot_06/weights/best.pt',
                     handeye=root.parent/'calibration/data/handeye_result.json', set_index=1, consumed_prefix_count=1,
                     all_instances=False, instance=2, frames=30, info_topic='/camera/camera/color/camera_info',
                     depth_topic='/camera/camera/aligned_depth_to_color/image_raw', robot_topic='/nonrt_state_data',
                     color_topic='/camera/camera/color/image_raw/compressed').items(): setattr(a,k,v)
    rclpy.init(); n = EdgeCapture(a); error = None
    try:
        deadline = time.monotonic()+a.timeout
        while not n.complete() and time.monotonic() < deadline: rclpy.spin_once(n, timeout_sec=.1)
    except Exception as exc:
        error = str(exc)
    finally:
        result = dict(diagnostic_only=True, robot_motion_authorized=False, validation_passed=False,
                      physical_accuracy_verified=False, correction_applied=False,
                      surface_plane_assumed_base_z_mm=-47.291, timestamp_unix=time.time(),
                      frame_count=len(n.rows), rejections=n.rejections, error=error,
                      handeye_sha256=hashlib.sha256(a.handeye.read_bytes()).hexdigest(),
                      model_sha256=hashlib.sha256(a.model.read_bytes()).hexdigest(),
                      **summarize(n.rows, n.cfg['obb_detection']), samples=n.rows)
        if error: result['stability_passed'] = False
        a.output.write_text(json.dumps(result, indent=2))
        if n.last_image is not None: cv2.imwrite(str(a.output.with_suffix('.jpg')), n.last_image)
        print(json.dumps({k:v for k,v in result.items() if k != 'samples'}, indent=2))
        n.destroy_node(); rclpy.shutdown()
    return 0 if result['stability_passed'] else 2


if __name__ == '__main__': raise SystemExit(main())
