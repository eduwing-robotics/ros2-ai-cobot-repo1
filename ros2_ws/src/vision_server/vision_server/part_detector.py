import json
import time
from collections import Counter, defaultdict, deque
from pathlib import Path

import cv2
import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CameraInfo, CompressedImage, Image

from vision_interfaces.msg import Detections, Part, VisionStatus

from .config_utils import default_path, load_yaml, resolve_package_path
from .depth_utils import deproject_pixel, robust_box_depth
from .detectors.yolo_backend import YoloBackend


SENSOR_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=ReliabilityPolicy.BEST_EFFORT,
)


class PartDetector(Node):
    def __init__(self) -> None:
        super().__init__('part_detector')
        self.declare_parameter('camera_config', default_path('config/cameras.yaml'))
        self.declare_parameter('yolo_config', default_path('config/yolo.yaml'))

        camera_config = load_yaml(self.get_parameter('camera_config').value)
        yolo_config = load_yaml(self.get_parameter('yolo_config').value)['yolo']

        self._output = self.create_publisher(
            Detections, str(yolo_config['output_topic']), 10
        )
        self._status = self.create_publisher(
            VisionStatus, str(yolo_config['status_topic']), 10
        )
        self._annotated_topic = str(
            yolo_config.get('annotated_topic', '/vision/detections_image/compressed')
        )
        self._annotated = self.create_publisher(
            CompressedImage, self._annotated_topic, SENSOR_QOS
        )
        self._jpeg_quality = int(yolo_config.get('jpeg_quality', 90))
        self._annotated_max_width = max(
            0, int(yolo_config.get('annotated_max_width', 0))
        )
        self._draw_angle = bool(yolo_config.get('draw_angle', False))
        self._draw_object_ids = bool(yolo_config.get('draw_object_ids', False))
        self._draw_object_centers = bool(
            yolo_config.get('draw_object_centers', True)
        )
        display_config = yolo_config.get('display_stabilization', {})
        self._display_stabilization_enabled = bool(
            display_config.get('enabled', False)
        )
        self._display_smoothing_alpha = min(
            1.0, max(0.05, float(display_config.get('smoothing_alpha', 0.35)))
        )
        self._display_match_distance_px = max(
            1.0, float(display_config.get('match_distance_px', 32.0))
        )
        self._display_hold_frames = max(
            0, int(display_config.get('hold_frames', 2))
        )
        self._display_class_hold_frames = {
            str(name): max(0, int(frames))
            for name, frames in display_config.get('class_hold_frames', {}).items()
        }
        self._display_tracks = defaultdict(list)
        self._next_display_track_id = 1
        self._tray_roi_enabled = False
        self._tray_registration_mode = 'tracked'
        self._tray_bins = {}
        self._class_filters = {}
        self._tray_reference_size = None
        self._tray_reference_quad = None
        self._tray_reference_keypoints = None
        self._tray_reference_descriptors = None
        self._tray_matcher = None
        self._tray_sift = None
        self._tray_homography = None
        self._tray_registration_at = 0.0
        self._tray_registration_attempt_at = 0.0
        self._tray_homography_corners = deque(maxlen=5)
        self._tray_registration_config = {}
        self._load_tray_roi_filter(yolo_config.get('tray_roi_filter', {}))
        self._last_frame = {}
        self._last_seen = {}
        self._camera_names = []
        self._required_camera_names = []
        self._subscriptions = []
        self._detector = None
        self._model_message = 'YOLO model is not loaded'
        self._camera_timeout = max(
            0.2, float(yolo_config.get('camera_timeout_sec', 2.0))
        )
        self._inference_count = 0
        self._depth_camera = None
        self._depth_image = None
        self._depth_scale_config = 0.001
        self._depth_image_scale = 1.0
        self._depth_received_at = 0.0
        self._depth_stamp = None
        self._depth_camera_matrix = None
        self._depth_camera_info_size = None
        self._depth_max_age = 0.15
        self._depth_sync_tolerance = 0.10
        self._depth_roi_fraction = 0.35
        self._depth_min_m = 0.02
        self._depth_max_m = 2.0

        try:
            self._detector = YoloBackend(
                model_path=resolve_package_path(str(yolo_config['model_path'])),
                image_size=int(yolo_config['image_size']),
                confidence=float(yolo_config['confidence']),
                iou=float(yolo_config['iou']),
                device=str(yolo_config.get('device', 'auto')),
                obb_duplicate_iou=float(
                    yolo_config.get('obb_duplicate_iou', 0.25)
                ),
                half=bool(yolo_config.get('half', False)),
                max_detections=int(yolo_config.get('max_detections', 300)),
            )
            self._model_message = 'YOLO model loaded'
            self.get_logger().info(self._model_message)
        except Exception as exc:
            self._model_message = str(exc)
            self.get_logger().warning(self._model_message)

        for camera, settings in camera_config.get('cameras', {}).items():
            if not settings.get('enabled', False) or not settings.get('run_yolo', False):
                continue
            topic = str(settings['output_topic'])
            transport = str(settings.get('transport', 'compressed'))
            max_fps = max(
                0.1,
                float(settings.get('yolo_max_fps', settings.get('max_fps', 5.0))),
            )
            msg_type = CompressedImage if transport == 'compressed' else Image
            subscription = self.create_subscription(
                msg_type,
                topic,
                lambda msg, camera=camera, max_fps=max_fps: self._on_image(
                    msg, camera, max_fps
                ),
                SENSOR_QOS,
            )
            self._subscriptions.append(subscription)
            self._camera_names.append(camera)
            if settings.get('required_for_ready', True):
                self._required_camera_names.append(camera)
            self.get_logger().info(f'YOLO input: {topic} ({camera}, max {max_fps:g} FPS)')

            depth_topic = settings.get('depth_topic')
            camera_info_topic = settings.get('camera_info_topic')
            if depth_topic and camera_info_topic:
                if self._depth_camera is not None:
                    raise RuntimeError('Only one aligned depth camera is currently supported')
                self._depth_camera = camera
                self._depth_scale_config = float(
                    settings.get('depth_scale_m_per_unit', 0.001)
                )
                self._depth_max_age = max(
                    0.01, float(settings.get('depth_max_age_sec', 0.15))
                )
                self._depth_sync_tolerance = max(
                    0.0, float(settings.get('depth_sync_tolerance_sec', 0.10))
                )
                self._depth_roi_fraction = float(
                    settings.get('depth_roi_fraction', 0.35)
                )
                self._depth_min_m = float(settings.get('depth_min_m', 0.02))
                self._depth_max_m = float(settings.get('depth_max_m', 2.0))
                self._subscriptions.append(
                    self.create_subscription(
                        Image, str(depth_topic), self._on_depth, SENSOR_QOS
                    )
                )
                self._subscriptions.append(
                    self.create_subscription(
                        CameraInfo,
                        str(camera_info_topic),
                        self._on_depth_camera_info,
                        SENSOR_QOS,
                    )
                )
                self.get_logger().info(
                    f'Aligned depth: {depth_topic} + {camera_info_topic} ({camera})'
                )

        self.create_timer(2.0, self._publish_status)
        self._publish_status()
        self.get_logger().info(f'Annotated detections: {self._annotated_topic}')
        if self._display_stabilization_enabled:
            self.get_logger().info(
                'Display-only OBB stabilization enabled; raw detection output '
                'remains unchanged'
            )

    def _load_tray_roi_filter(self, config) -> None:
        if not config or not bool(config.get('enabled', False)):
            return
        layout_path = Path(str(config.get('layout_file', ''))).expanduser()
        if not layout_path.is_file():
            self.get_logger().warning(f'Tray ROI layout not found: {layout_path}')
            return
        layout = json.loads(layout_path.read_text(encoding='utf-8'))
        self._tray_bins = {
            str(item['bin_id']): item['section_polygon_normalized']
            for item in layout.get('bins', [])
        }
        self._class_filters = dict(config.get('classes', {}))
        self._tray_registration_mode = str(
            config.get('registration_mode', 'tracked')
        ).strip().lower()
        if self._tray_registration_mode == 'fixed':
            self._tray_roi_enabled = bool(self._tray_bins and self._class_filters)
            if self._tray_roi_enabled:
                self.get_logger().info(
                    'Fixed tray ROI class filter enabled from tray_layout.json: '
                    + ', '.join(sorted(self._class_filters))
                )
            return
        reference_path = Path(str(layout.get('reference_image', ''))).expanduser()
        if not reference_path.is_absolute():
            reference_path = layout_path.parents[2] / reference_path
        reference = cv2.imread(str(reference_path), cv2.IMREAD_GRAYSCALE)
        if reference is None:
            self.get_logger().warning(f'Tray ROI reference not found: {reference_path}')
            return
        self._tray_reference_size = (reference.shape[1], reference.shape[0])
        self._tray_reference_quad = self._detect_tray_quad(reference)
        self._tray_registration_config = {
            'scale': float(config.get('registration_scale', 0.4)),
            'interval': float(config.get('registration_interval_sec', 1.0)),
            'timeout': float(config.get('registration_timeout_sec', 2.0)),
            'ratio_test': float(config.get('ratio_test', 0.72)),
            'min_matches': int(config.get('min_matches', 14)),
            'min_inliers': int(config.get('min_inliers', 10)),
            'ransac_px': float(config.get('ransac_px', 4.0)),
            'min_scale_area': float(config.get('min_scale_area', 0.18)),
            'max_scale_area': float(config.get('max_scale_area', 3.0)),
        }
        self._tray_homography_corners = deque(
            maxlen=max(1, int(config.get('smoothing_frames', 5)))
        )
        scale = self._tray_registration_config['scale']
        small = cv2.resize(
            reference, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
        )
        feature_mask = np.zeros_like(reference)
        all_points = []
        for normalized in self._tray_bins.values():
            points = np.asarray([
                (round(x * reference.shape[1]), round(y * reference.shape[0]))
                for x, y in normalized
            ], np.int32)
            all_points.extend(points.tolist())
            cv2.polylines(feature_mask, [points], True, 255, 70)
        if all_points:
            hull = cv2.convexHull(np.asarray(all_points, np.int32))
            cv2.polylines(feature_mask, [hull], True, 255, 70)
        mask_small = cv2.resize(
            feature_mask,
            (small.shape[1], small.shape[0]),
            interpolation=cv2.INTER_NEAREST,
        )
        self._tray_sift = cv2.SIFT_create(nfeatures=1600, contrastThreshold=0.025)
        keypoints, descriptors = self._tray_sift.detectAndCompute(small, mask_small)
        if (
            descriptors is None
            or len(keypoints) < self._tray_registration_config['min_matches']
        ):
            self.get_logger().warning('Tray ROI reference has insufficient SIFT features')
            return
        self._tray_reference_keypoints = keypoints
        self._tray_reference_descriptors = descriptors
        self._tray_matcher = cv2.BFMatcher(cv2.NORM_L2)
        self._tray_roi_enabled = bool(self._tray_bins and self._class_filters)
        if self._tray_roi_enabled:
            self.get_logger().info(
                'Tracked tray ROI class filter enabled: '
                + ', '.join(sorted(self._class_filters))
            )

    @staticmethod
    def _order_quad(points):
        points = np.asarray(points, dtype=np.float32).reshape(4, 2)
        ordered = np.empty((4, 2), dtype=np.float32)
        sums = points.sum(axis=1)
        differences = np.diff(points, axis=1).reshape(-1)
        ordered[0] = points[np.argmin(sums)]       # top-left
        ordered[2] = points[np.argmax(sums)]       # bottom-right
        ordered[1] = points[np.argmin(differences)]  # top-right
        ordered[3] = points[np.argmax(differences)]  # bottom-left
        return ordered

    @classmethod
    def _detect_tray_quad(cls, gray):
        """Find the bright outer tray for ROI registration fallback only."""
        if gray is None:
            return None
        if gray.ndim == 3:
            gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape[:2]
        threshold = int(np.clip(np.percentile(gray, 75) - 20, 145, 185))
        mask = cv2.inRange(gray, threshold, 255)
        kernel_size = max(15, int(round(min(height, width) * 0.03)))
        if kernel_size % 2 == 0:
            kernel_size += 1
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            np.ones((kernel_size, kernel_size), dtype=np.uint8),
        )
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        image_area = float(width * height)
        candidates = []
        for contour in contours:
            contour_area = abs(float(cv2.contourArea(contour)))
            if not 0.25 * image_area <= contour_area <= 0.82 * image_area:
                continue
            rect = cv2.minAreaRect(contour)
            short_side, long_side = sorted(rect[1])
            if short_side <= 0.0:
                continue
            aspect = long_side / short_side
            rect_area = short_side * long_side
            fill = contour_area / rect_area if rect_area > 0.0 else 0.0
            if 1.03 <= aspect <= 1.65 and fill >= 0.55:
                candidates.append((contour_area, cls._order_quad(cv2.boxPoints(rect))))
        return max(candidates, key=lambda item: item[0])[1] if candidates else None

    def _commit_tray_homography(self, full_h, now) -> bool:
        reference_width, reference_height = self._tray_reference_size
        corners = np.float32([[
            [0, 0], [reference_width, 0],
            [reference_width, reference_height], [0, reference_height],
        ]])
        moved = cv2.perspectiveTransform(corners, full_h)[0]
        area_ratio = abs(cv2.contourArea(moved)) / float(
            reference_width * reference_height
        )
        cfg = self._tray_registration_config
        if not cfg['min_scale_area'] <= area_ratio <= cfg['max_scale_area']:
            return self._tray_registration_is_fresh(now)
        self._tray_homography_corners.append(moved)
        smoothed = np.median(
            np.asarray(self._tray_homography_corners), axis=0
        ).astype(np.float32)
        self._tray_homography = cv2.getPerspectiveTransform(corners[0], smoothed)
        self._tray_registration_at = now
        return True

    def _update_tray_registration_geometry(self, gray, now) -> bool:
        if self._tray_reference_quad is None:
            return self._tray_registration_is_fresh(now)
        current_quad = self._detect_tray_quad(gray)
        if current_quad is None:
            return self._tray_registration_is_fresh(now)
        full_h = cv2.getPerspectiveTransform(
            self._tray_reference_quad.astype(np.float32),
            current_quad.astype(np.float32),
        )
        return self._commit_tray_homography(full_h, now)

    def _tray_registration_is_fresh(self, now=None) -> bool:
        if self._tray_registration_mode == 'fixed':
            return True
        now = time.monotonic() if now is None else now
        return (
            self._tray_homography is not None
            and now - self._tray_registration_at
            <= self._tray_registration_config.get('timeout', 0.0)
        )

    def _update_tray_registration(self, image) -> bool:
        if not self._tray_roi_enabled:
            return False
        if self._tray_registration_mode == 'fixed':
            return True
        now = time.monotonic()
        cfg = self._tray_registration_config
        if now - self._tray_registration_attempt_at < cfg['interval']:
            return self._tray_registration_is_fresh(now)
        self._tray_registration_attempt_at = now
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        scale = cfg['scale']
        small = cv2.resize(
            gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
        )
        keypoints, descriptors = self._tray_sift.detectAndCompute(small, None)
        if descriptors is None:
            return self._update_tray_registration_geometry(gray, now)
        pairs = self._tray_matcher.knnMatch(
            self._tray_reference_descriptors, descriptors, k=2
        )
        good = [
            first for first, second in pairs
            if first.distance < cfg['ratio_test'] * second.distance
        ]
        if len(good) < cfg['min_matches']:
            return self._update_tray_registration_geometry(gray, now)
        source = np.float32([
            self._tray_reference_keypoints[match.queryIdx].pt for match in good
        ]).reshape(-1, 1, 2)
        target = np.float32([
            keypoints[match.trainIdx].pt for match in good
        ]).reshape(-1, 1, 2)
        small_h, inlier_mask = cv2.findHomography(
            source, target, cv2.RANSAC, cfg['ransac_px']
        )
        inliers = int(inlier_mask.sum()) if inlier_mask is not None else 0
        if small_h is None or inliers < cfg['min_inliers']:
            return self._update_tray_registration_geometry(gray, now)
        scale_matrix = np.diag([scale, scale, 1.0])
        full_h = np.linalg.inv(scale_matrix) @ small_h @ scale_matrix
        return self._commit_tray_homography(full_h, now)

    def _tray_polygon(self, bin_id: str, width: int, height: int):
        normalized = self._tray_bins.get(bin_id)
        if not normalized:
            return None
        if self._tray_registration_mode == 'fixed':
            return np.asarray([
                (float(x) * width, float(y) * height) for x, y in normalized
            ], dtype=np.float32)
        if not self._tray_registration_is_fresh():
            return None
        reference_width, reference_height = self._tray_reference_size
        reference = np.asarray([
            (float(x) * reference_width, float(y) * reference_height)
            for x, y in normalized
        ], dtype=np.float32).reshape(-1, 1, 2)
        return cv2.perspectiveTransform(
            reference, self._tray_homography
        )[:, 0, :]

    @staticmethod
    def _detection_area_norm(item, image_area: float) -> float:
        if item.obb_points:
            area = abs(float(cv2.contourArea(np.asarray(item.obb_points, np.float32))))
        else:
            area = float(item.width * item.height)
        return 0.0 if image_area <= 0.0 else area / image_area

    def _filter_tray_detections(self, detected, image):
        if not self._tray_roi_enabled:
            return detected
        if not self._update_tray_registration(image):
            return []
        height, width = image.shape[:2]
        image_area = float(width * height)
        accepted = defaultdict(list)
        for item in detected:
            profile = self._class_filters.get(item.name)
            if profile is None or item.score < float(profile.get('min_score', 0.0)):
                continue
            polygon = self._tray_polygon(str(profile.get('bin_id', '')), width, height)
            if polygon is None:
                continue
            center = (item.x + item.width * 0.5, item.y + item.height * 0.5)
            if cv2.pointPolygonTest(polygon, center, False) < 0:
                continue
            area_norm = self._detection_area_norm(item, image_area)
            if not (
                float(profile.get('min_area_norm', 0.0))
                <= area_norm
                <= float(profile.get('max_area_norm', 1.0))
            ):
                continue
            accepted[item.name].append(item)

        filtered = []
        for name, items in accepted.items():
            max_count = int(self._class_filters[name].get('max_count', len(items)))
            filtered.extend(sorted(items, key=lambda item: item.score, reverse=True)[:max_count])
        return sorted(filtered, key=lambda item: (item.name, item.y, item.x))

    @staticmethod
    def _obb_measurement(item):
        if not item.obb_points:
            return None
        points = np.asarray(item.obb_points, dtype=np.float32)
        if points.shape != (4, 2):
            return None
        (center_x, center_y), (size_x, size_y), angle_deg = cv2.minAreaRect(points)
        if size_x <= 0.0 or size_y <= 0.0:
            return None
        if size_x < size_y:
            size_x, size_y = size_y, size_x
            angle_deg += 90.0
        return np.asarray(
            [center_x, center_y, size_x, size_y, angle_deg % 180.0],
            dtype=np.float64,
        )

    @staticmethod
    def _measurement_detection(track):
        center_x, center_y, long_side, short_side, angle_deg = track['state']
        rectangle = (
            (float(center_x), float(center_y)),
            (float(long_side), float(short_side)),
            float(angle_deg),
        )
        points = cv2.boxPoints(rectangle)
        minimum = points.min(axis=0)
        maximum = points.max(axis=0)
        source = track['source']
        from .detectors.base import Detection
        return Detection(
            name=source.name,
            class_id=source.class_id,
            score=float(track['score']),
            x=int(round(minimum[0])),
            y=int(round(minimum[1])),
            width=max(0, int(round(maximum[0] - minimum[0]))),
            height=max(0, int(round(maximum[1] - minimum[1]))),
            angle_deg=float(angle_deg),
            obb_points=tuple((float(x), float(y)) for x, y in points),
        )

    def _stabilize_display_detections(self, camera: str, detected):
        """Smooth only the viewer overlay; never feed held tracks to robot data."""
        if not self._display_stabilization_enabled:
            return detected

        tracks = self._display_tracks[camera]
        measurements = []
        passthrough = []
        for item in detected:
            state = self._obb_measurement(item)
            if state is None:
                passthrough.append(item)
            else:
                measurements.append((item, state))

        candidate_pairs = []
        for track_index, track in enumerate(tracks):
            for measurement_index, (item, state) in enumerate(measurements):
                if track['source'].class_id != item.class_id:
                    continue
                distance = float(np.linalg.norm(track['state'][:2] - state[:2]))
                if distance <= self._display_match_distance_px:
                    candidate_pairs.append((distance, track_index, measurement_index))
        candidate_pairs.sort()

        matched_tracks = set()
        matched_measurements = set()
        alpha = self._display_smoothing_alpha
        for _, track_index, measurement_index in candidate_pairs:
            if track_index in matched_tracks or measurement_index in matched_measurements:
                continue
            track = tracks[track_index]
            item, state = measurements[measurement_index]
            previous = track['state']
            updated = previous.copy()
            updated[:4] = (1.0 - alpha) * previous[:4] + alpha * state[:4]
            angle_delta = ((state[4] - previous[4] + 90.0) % 180.0) - 90.0
            updated[4] = (previous[4] + alpha * angle_delta) % 180.0
            track.update(
                state=updated,
                source=item,
                score=(1.0 - alpha) * float(track['score']) + alpha * item.score,
                missed=0,
            )
            matched_tracks.add(track_index)
            matched_measurements.add(measurement_index)

        for measurement_index, (item, state) in enumerate(measurements):
            if measurement_index in matched_measurements:
                continue
            tracks.append({
                'id': self._next_display_track_id,
                'state': state,
                'source': item,
                'score': item.score,
                'missed': 0,
            })
            self._next_display_track_id += 1

        retained = []
        for track_index, track in enumerate(tracks):
            if track_index not in matched_tracks and track['missed'] == 0:
                # Newly created tracks and tracks observed in the previous frame
                # both arrive here. New tracks stay at missed=0.
                if any(track['source'] is item for item, _ in measurements):
                    retained.append(track)
                    continue
            if track_index not in matched_tracks:
                track['missed'] += 1
            hold_frames = self._display_class_hold_frames.get(
                track['source'].name, self._display_hold_frames
            )
            if track['missed'] <= hold_frames:
                retained.append(track)

        self._display_tracks[camera] = retained
        stabilized = [
            self._measurement_detection(track)
            for track in sorted(retained, key=lambda item: item['id'])
        ]
        return stabilized + passthrough

    def _publish_status(self) -> None:
        now = time.monotonic()
        active = sorted(
            camera
            for camera in self._camera_names
            if now - self._last_seen.get(camera, 0.0) <= self._camera_timeout
        )
        missing = sorted(
            camera for camera in self._required_camera_names if camera not in active
        )
        message = VisionStatus()
        message.header.stamp = self.get_clock().now().to_msg()
        message.ready = (
            self._detector is not None
            and bool(self._camera_names)
            and not missing
        )
        message.model_loaded = self._detector is not None
        message.cameras = list(self._camera_names)
        message.active_cameras = active
        message.missing_cameras = missing
        message.inference_count = self._inference_count
        details = [self._model_message]
        if missing:
            details.append('missing camera input: ' + ', '.join(missing))
        message.message = '; '.join(details)
        self._status.publish(message)

    def _on_image(self, message, camera: str, max_fps: float) -> None:
        now = time.monotonic()
        self._last_seen[camera] = now
        # A small tolerance avoids 15 FPS sources aliasing down to 7.5 FPS
        # when arrival jitter lands just below an exact 1/15 s boundary.
        if now - self._last_frame.get(camera, 0.0) < 0.90 / max_fps:
            return
        self._last_frame[camera] = now
        if self._detector is None:
            return

        image = self._decode(message)
        if image is None:
            self.get_logger().warning(f'Could not decode an image from {camera}')
            return

        try:
            detected = self._detector.detect(image)
            detected = self._filter_tray_detections(detected, image)
        except Exception as exc:  # Keep camera callbacks alive after one inference error.
            self.get_logger().error(f'YOLO inference failed for {camera}: {exc}')
            return

        output = Detections()
        output.header = message.header
        output.camera = camera
        output.image_width = int(image.shape[1])
        output.image_height = int(image.shape[0])
        for item in detected:
            part = Part()
            part.name = item.name
            part.class_id = item.class_id
            part.score = item.score
            part.x = item.x
            part.y = item.y
            part.width = item.width
            part.height = item.height
            part.angle_deg = 0.0 if item.angle_deg is None else item.angle_deg
            part.angle_valid = item.angle_deg is not None
            part.depth_m = 0.0
            part.depth_valid = False
            part.camera_x_m = 0.0
            part.camera_y_m = 0.0
            part.camera_z_m = 0.0
            part.position_valid = False
            self._add_aligned_depth(part, message, image.shape[:2], camera)
            output.parts.append(part)
        self._output.publish(output)
        display_detected = self._stabilize_display_detections(camera, detected)
        self._publish_annotated(message, image, display_detected)
        self._inference_count += 1

    def _publish_annotated(self, source_message, image, detected) -> None:
        canvas = image.copy()
        colors = {
            'gpu': (255, 90, 20),
            'hbm': (220, 40, 220),
            'power_module': (0, 165, 255),
            'vrm': (30, 30, 245),
            'inductor': (0, 220, 220),
            'smd_capacitor': (30, 210, 30),
        }
        short_names = {
            'gpu': 'G', 'hbm': 'H', 'power_module': 'P',
            'vrm': 'V', 'inductor': 'I', 'smd_capacitor': 'S',
        }
        counters = Counter()
        height, width = canvas.shape[:2]
        if self._tray_roi_enabled:
            for name, profile in self._class_filters.items():
                polygon = self._tray_polygon(str(profile.get('bin_id', '')), width, height)
                if polygon is not None:
                    base_color = colors.get(name, (180, 180, 180))
                    roi_color = tuple(int(channel * 0.62) for channel in base_color)
                    cv2.polylines(
                        canvas, [np.int32(polygon)], True,
                        roi_color, 2, cv2.LINE_AA,
                    )
        for item in detected:
            color = colors.get(item.name, (255, 120, 20))
            counters[item.name] += 1
            if item.obb_points:
                polygon = np.asarray(item.obb_points, dtype=np.int32).reshape(-1, 1, 2)
                cv2.polylines(canvas, [polygon], True, (20, 20, 20), 4, cv2.LINE_AA)
                cv2.polylines(canvas, [polygon], True, color, 2, cv2.LINE_AA)
            else:
                cv2.rectangle(
                    canvas,
                    (int(item.x), int(item.y)),
                    (int(item.x + item.width), int(item.y + item.height)),
                    color,
                    2,
                    cv2.LINE_AA,
                )

            center = (
                int(round(item.x + item.width * 0.5)),
                int(round(item.y + item.height * 0.5)),
            )
            if self._draw_object_centers:
                cv2.circle(canvas, center, 4, (20, 20, 20), -1, cv2.LINE_AA)
                cv2.circle(canvas, center, 2, color, -1, cv2.LINE_AA)
            if self._draw_object_ids:
                label = f'{short_names.get(item.name, "?")}{counters[item.name]}'
                origin = (center[0] + 7, center[1] - 7)
                cv2.putText(
                    canvas, label, origin, cv2.FONT_HERSHEY_SIMPLEX,
                    0.42, (20, 20, 20), 3, cv2.LINE_AA,
                )
                cv2.putText(
                    canvas, label, origin, cv2.FONT_HERSHEY_SIMPLEX,
                    0.42, color, 1, cv2.LINE_AA,
                )
        banner = np.full((86, width, 3), 18, dtype=np.uint8)
        if self._tray_registration_mode == 'fixed':
            registration = 'FIXED LAYOUT'
        else:
            registration = (
                'TRACKING' if self._tray_registration_is_fresh() else 'NOT REGISTERED'
            )
        registration_color = (
            (40, 230, 40)
            if registration in ('TRACKING', 'FIXED LAYOUT') else (40, 40, 245)
        )
        cv2.putText(
            banner, f'TRAY PART OBB | {registration} | ROI FILTERED', (18, 28),
            cv2.FONT_HERSHEY_SIMPLEX, 0.72, registration_color, 2, cv2.LINE_AA,
        )
        x = 18
        ordered = ['gpu', 'hbm', 'power_module', 'vrm', 'inductor', 'smd_capacitor']
        for name in ordered:
            if name not in self._class_filters:
                continue
            count = counters.get(name, 0)
            expected = int(self._class_filters[name].get('max_count', 0))
            scores = [item.score for item in detected if item.name == name]
            mean_score = sum(scores) / len(scores) if scores else 0.0
            text = f'{short_names[name]} {count}/{expected}  {mean_score:.2f}'
            cv2.putText(banner, text, (x, 66), cv2.FONT_HERSHEY_SIMPLEX,
                        0.52, colors[name], 2, cv2.LINE_AA)
            x += max(135, cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 2)[0][0] + 28)
        canvas = np.vstack([banner, canvas])
        if self._annotated_max_width and canvas.shape[1] > self._annotated_max_width:
            scale = self._annotated_max_width / float(canvas.shape[1])
            canvas = cv2.resize(
                canvas,
                (self._annotated_max_width, int(round(canvas.shape[0] * scale))),
                interpolation=cv2.INTER_AREA,
            )
        success, encoded = cv2.imencode(
            '.jpg', canvas, [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
        )
        if not success:
            return
        annotated = CompressedImage()
        annotated.header = source_message.header
        annotated.format = 'jpeg'
        annotated.data = encoded.tobytes()
        self._annotated.publish(annotated)

    @staticmethod
    def _stamp_seconds(message) -> float:
        stamp = message.header.stamp
        return float(stamp.sec) + float(stamp.nanosec) * 1e-9

    def _on_depth_camera_info(self, message: CameraInfo) -> None:
        self._depth_camera_matrix = np.asarray(message.k, dtype=float).reshape(3, 3)
        self._depth_camera_info_size = (int(message.width), int(message.height))

    def _on_depth(self, message: Image) -> None:
        enc = str(message.encoding).lower()
        if enc in ('16uc1', 'mono16'):
            dtype = np.dtype('>u2' if message.is_bigendian else '<u2')
            scale = self._depth_scale_config
        elif enc == '32fc1':
            dtype = np.dtype('>f4' if message.is_bigendian else '<f4')
            scale = 1.0
        else:
            self.get_logger().warning(f'Unsupported depth encoding: {message.encoding}')
            return
        items_per_row = int(message.step) // dtype.itemsize
        needed = int(message.height) * items_per_row
        values = np.frombuffer(message.data, dtype=dtype, count=needed)
        if values.size != needed or items_per_row < int(message.width):
            self.get_logger().warning('Invalid depth image stride/data length')
            return
        self._depth_image = values.reshape(int(message.height), items_per_row)[
            :, : int(message.width)
        ].copy()
        self._depth_image_scale = scale
        self._depth_received_at = time.monotonic()
        self._depth_stamp = self._stamp_seconds(message)

    def _add_aligned_depth(self, part, color_message, image_shape, camera: str) -> None:
        if camera != self._depth_camera:
            return
        if (
            self._depth_image is None
            or self._depth_camera_matrix is None
            or time.monotonic() - self._depth_received_at > self._depth_max_age
        ):
            return
        height, width = [int(value) for value in image_shape]
        if self._depth_image.shape != (height, width):
            return
        if self._depth_camera_info_size != (width, height):
            return
        color_stamp = self._stamp_seconds(color_message)
        if (
            color_stamp > 0.0
            and self._depth_stamp is not None
            and self._depth_stamp > 0.0
            and abs(color_stamp - self._depth_stamp) > self._depth_sync_tolerance
        ):
            return
        estimate = robust_box_depth(
            self._depth_image,
            (part.x, part.y, part.width, part.height),
            scale_m_per_unit=self._depth_image_scale,
            roi_fraction=self._depth_roi_fraction,
            min_depth_m=self._depth_min_m,
            max_depth_m=self._depth_max_m,
        )
        if estimate is None:
            return
        u, v, depth_m = estimate
        point = deproject_pixel(u, v, depth_m, self._depth_camera_matrix)
        if point is None:
            return
        part.depth_m = depth_m
        part.depth_valid = True
        part.camera_x_m = point.x_m
        part.camera_y_m = point.y_m
        part.camera_z_m = point.z_m
        part.position_valid = True

    @staticmethod
    def _decode(message):
        if isinstance(message, CompressedImage):
            data = np.frombuffer(message.data, dtype=np.uint8)
            return cv2.imdecode(data, cv2.IMREAD_COLOR)

        if not isinstance(message, Image) or message.height == 0 or message.width == 0:
            return None
        channels = 3 if message.encoding in ('bgr8', 'rgb8') else 1
        row = np.frombuffer(message.data, dtype=np.uint8).reshape(message.height, message.step)
        image = row[:, : message.width * channels].reshape(
            message.height, message.width, channels
        )
        if message.encoding == 'rgb8':
            return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        return image


def main(args=None) -> None:
    rclpy.init(args=args)
    node = PartDetector()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        try:
            node.destroy_node()
        except ValueError:
            # Jazzy can remove a remote-image event handler during Ctrl+C
            # before destroy_node() walks the subscription list.
            pass
        if rclpy.ok():
            rclpy.shutdown()
