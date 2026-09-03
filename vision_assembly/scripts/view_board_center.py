#!/usr/bin/env python3
"""Publish a live empty-board center overlay; never commands robot motion."""

import argparse
import itertools
import json
import math
from pathlib import Path

import cv2
import numpy as np
import rclpy
from fairino_msgs.msg import RobotNonrtState
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import CameraInfo, CompressedImage
from std_msgs.msg import String


def ordered_box(points):
    points = np.asarray(points, dtype=np.float32).reshape(4, 2)
    result = np.zeros((4, 2), dtype=np.float32)
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).reshape(-1)
    result[0] = points[np.argmin(sums)]
    result[2] = points[np.argmax(sums)]
    result[1] = points[np.argmin(differences)]
    result[3] = points[np.argmax(differences)]
    return result


def transform(rotation, translation):
    value = np.eye(4)
    value[:3, :3] = rotation
    value[:3, 3] = translation
    return value


def short_slot_label(slot_code):
    prefix, number = str(slot_code).split('-', 1)
    letter = {'GPU': 'G', 'HBM': 'H', 'PM': 'P', 'VRM': 'V', 'IND': 'I', 'CAP': 'C'}[prefix]
    return f'{letter}{int(number)}'


class BoardView(Node):
    def __init__(self, args):
        super().__init__(args.node_name)
        self.args = args
        self.target_slot = args.target_slot
        self.K = None
        self.D = None
        self.robot = None
        payload = json.loads(args.handeye_file.read_text(encoding='utf-8'))
        handeye = payload.get('camera_to_flange') or payload['best']['camera_to_flange']
        self.T_flange_camera = transform(
            np.asarray(handeye['rotation_matrix'], dtype=float),
            np.asarray(handeye['translation_m'], dtype=float),
        )
        slot_payload = json.loads(args.slot_layout_file.read_text(encoding='utf-8'))
        self.display_slots = []
        self.target_aliases = {}
        for slot in slot_payload['slots']:
            item = {
                'slot_id': str(slot['slot_code']), 'label': str(slot['slot_code']),
                'x_mm': float(slot['x_mm']), 'y_mm': float(slot['y_mm']),
                'size_mm': [float(value) for value in slot['size_mm']],
                'long_axis_board_deg': float(slot['long_axis_board_deg']),
                'color': tuple(int(value) for value in slot['color_bgr']),
            }
            self.display_slots.append(item)
            self.target_aliases[item['slot_id'].lower().replace('-', '_')] = item['slot_id']
        for index in range(1, 6):
            self.target_aliases[f'right_white_brown_{index:02d}'] = f'CAP-{index:02d}'
        self.recipe_slots = self.display_slots
        self.completed_slots = set()
        registration = json.loads(args.reference_registration_file.read_text(encoding='utf-8'))
        reference_slots = json.loads(args.reference_slots_file.read_text(encoding='utf-8'))
        self.reference_H = np.asarray(registration['homography_reference_to_live'], dtype=np.float32)
        # Rectify reference annotations into a common board coordinate frame
        # before projecting them into the live camera view.
        reference_corners = np.asarray(registration['reference_corners_pixel'], dtype=np.float32)
        live_corners = np.asarray(registration['live_corners_pixel'], dtype=np.float32)
        self.base_live_corners = live_corners.copy()
        board_plane = np.asarray([[0, 0], [1000, 0], [1000, 800], [0, 800]], dtype=np.float32)
        reference_to_board = cv2.getPerspectiveTransform(reference_corners, board_plane)
        # The operator keeps the reference image in the same viewing
        # orientation as PlaceCamera, so no additional flip is applied here.
        board_to_live = cv2.getPerspectiveTransform(board_plane, live_corners)
        self.place_camera_tcp = np.asarray(registration['place_camera_tcp_base_mm'], dtype=float)
        self.reference_slots = reference_slots['slots']
        self.reference_slot_polygons_live = {}
        for slot in self.reference_slots:
            source = np.asarray(slot['polygon_reference_pixel'], np.float32).reshape(-1, 1, 2)
            board_polygon = cv2.perspectiveTransform(source, reference_to_board)[:, 0]
            low = board_polygon.min(axis=0)
            high = board_polygon.max(axis=0)
            aligned_board_polygon = np.asarray([
                [low[0], low[1]], [high[0], low[1]],
                [high[0], high[1]], [low[0], high[1]],
            ], dtype=np.float32).reshape(-1, 1, 2)
            self.reference_slot_polygons_live[slot['slot_code']] = (
                cv2.perspectiveTransform(aligned_board_polygon, board_to_live)[:, 0]
            )
        hole_calibration = json.loads(
            args.board_holes_file.read_text(encoding='utf-8')
        )
        self.hole_reference_points = np.asarray(
            hole_calibration['hole_centers_pixel'], dtype=np.float32
        )
        self.hole_reference_radii = np.asarray(
            hole_calibration['hole_radii_pixel'], dtype=np.float32
        )
        previous_holes = np.asarray(
            hole_calibration['previous_baseline_hole_centers_pixel'], dtype=np.float32
        )
        holes_old_to_reference = cv2.getPerspectiveTransform(
            previous_holes, self.hole_reference_points
        )
        self.base_live_corners = cv2.perspectiveTransform(
            self.base_live_corners.reshape(-1, 1, 2), holes_old_to_reference
        )[:, 0]
        for code, polygon in self.reference_slot_polygons_live.items():
            self.reference_slot_polygons_live[code] = cv2.perspectiveTransform(
                polygon.reshape(-1, 1, 2), holes_old_to_reference
            )[:, 0]
        place_calibration = json.loads(
            args.place_calibration_file.read_text(encoding='utf-8')
        )
        self.place_templates = place_calibration['placements']
        anchor_codes = ('GPU-01', 'HBM-01', 'HBM-02')
        source_anchors = np.asarray([
            self.reference_slot_polygons_live[code].mean(axis=0)
            for code in anchor_codes
        ], dtype=float)
        target_anchors = np.asarray([
            self.place_templates[code].get('vision_anchor_base_xy_mm', [
                self.place_templates[code]['tcp_pose_base_mm_deg']['x'],
                self.place_templates[code]['tcp_pose_base_mm_deg']['y'],
            ]) for code in anchor_codes
        ], dtype=float)
        source_h = np.column_stack((source_anchors, np.ones(len(source_anchors))))
        coefficients, _, rank, _ = np.linalg.lstsq(source_h, target_anchors, rcond=None)
        if rank != 3:
            raise RuntimeError('placement calibration anchors are collinear')
        self.pixel_to_base_matrix = coefficients[:2, :].T
        self.pixel_to_base_translation = coefficients[2, :]
        baseline_color = cv2.imread(str(Path(hole_calibration['image'])))
        if baseline_color is None:
            raise RuntimeError(f"Cannot load hole baseline: {hole_calibration['image']}")
        hsv = cv2.cvtColor(baseline_color, cv2.COLOR_BGR2HSV)
        yellow = cv2.inRange(hsv, (15, 70, 70), (40, 255, 255))
        count, _, stats, centroids = cv2.connectedComponentsWithStats(yellow)
        bottom = float(self.base_live_corners[[2, 3], 1].mean())
        left = float(self.base_live_corners[:, 0].min())
        right = float(self.base_live_corners[:, 0].max())
        handle_candidates = [
            (int(stats[index, cv2.CC_STAT_AREA]), centroids[index])
            for index in range(1, count)
            if int(stats[index, cv2.CC_STAT_AREA]) >= 100
            and left <= float(centroids[index, 0]) <= right
            and float(centroids[index, 1]) >= bottom
        ]
        if not handle_candidates:
            raise RuntimeError('yellow board handle not found in hole baseline')
        self.handle_reference_pixel = np.asarray(
            max(handle_candidates, key=lambda item: item[0])[1], dtype=np.float32
        )
        self.tracking_scores = []
        self.tracked_holes = self.hole_reference_points.copy()
        self.tracked_live_corners = self.base_live_corners.copy()
        self.publisher = self.create_publisher(CompressedImage, args.output_topic, qos_profile_sensor_data)
        self.target_publisher = self.create_publisher(PoseStamped, args.target_pose_topic, 10)
        self.create_subscription(CameraInfo, args.camera_info_topic, self.info_cb, qos_profile_sensor_data)
        self.create_subscription(RobotNonrtState, args.robot_state_topic, self.robot_cb, 10)
        self.create_subscription(CompressedImage, args.image_topic, self.image_cb, qos_profile_sensor_data)
        self.create_subscription(String, args.target_selection_topic, self.target_selection_cb, 10)
        self.create_subscription(String, args.assembly_progress_topic, self.progress_cb, 10)
        self.get_logger().info(
            f'NO MOTION board overlay: {args.image_topic} -> {args.output_topic}'
        )

    def info_cb(self, message):
        self.K = np.asarray(message.k, dtype=float).reshape(3, 3)
        self.D = np.asarray(message.d, dtype=float)

    def robot_cb(self, message):
        self.robot = message

    def target_selection_cb(self, message):
        requested = message.data.strip()
        self.target_slot = self.target_aliases.get(requested, requested)

    def progress_cb(self, message):
        try:
            state = json.loads(message.data)
            if state.get('schema') != 'fr5.assembly.progress/v1' or not state.get('valid'):
                return
            self.completed_slots = {
                str(item['slot_code']) for item in state.get('assembled', [])
                if item.get('status') == 'ASSEMBLED'
            }
            next_step = state.get('next_step')
            if next_step:
                self.target_slot = str(next_step['slot_code'])
        except Exception:
            pass

    def track_board(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 1.2)
        candidate_groups = []
        search_half = 70
        for reference, expected_radius in zip(
                self.hole_reference_points, self.hole_reference_radii):
            x, y = np.rint(reference).astype(int)
            roi = blurred[y-search_half:y+search_half+1, x-search_half:x+search_half+1]
            if roi.shape != (2 * search_half + 1, 2 * search_half + 1):
                return None
            circles = cv2.HoughCircles(
                roi, cv2.HOUGH_GRADIENT, 1.0, 10,
                param1=90, param2=12, minRadius=5, maxRadius=18,
            )
            if circles is None:
                return None
            candidates = []
            for cx, cy, radius in circles[0]:
                center = np.asarray(
                    [x - search_half + cx, y - search_half + cy], dtype=np.float32
                )
                distance = float(np.linalg.norm(center - reference))
                radius_error = abs(float(radius - expected_radius))
                if distance <= 60.0 and radius_error <= 8.0:
                    candidates.append((center, distance, radius_error, float(radius)))
            if not candidates:
                return None
            candidate_groups.append(candidates[:8])
        best = None
        for combination in itertools.product(*candidate_groups):
            holes = np.asarray([item[0] for item in combination], dtype=np.float32)
            shifts = holes - self.hole_reference_points
            common_shift = np.median(shifts, axis=0)
            shift_error = float(np.sum((shifts - common_shift) ** 2))
            radius_error = float(sum(item[2] ** 2 for item in combination))
            score = shift_error + 0.5 * radius_error
            if best is None or score < best[0]:
                best = (score, holes, combination)
        if best is None:
            return None
        _, holes, combination = best
        reference_distances = np.linalg.norm(
            self.hole_reference_points - np.roll(self.hole_reference_points, -1, axis=0),
            axis=1,
        )
        current_distances = np.linalg.norm(
            holes - np.roll(holes, -1, axis=0), axis=1
        )
        ratios = current_distances / reference_distances
        if float(np.ptp(ratios)) > 0.045 or not 0.94 <= float(np.mean(ratios)) <= 1.06:
            return None
        self.tracked_holes = (
            0.65 * self.tracked_holes + 0.35 * holes
        ).astype(np.float32)
        tracking_H = cv2.getPerspectiveTransform(
            self.hole_reference_points, self.tracked_holes
        )
        candidate_corners = cv2.perspectiveTransform(
            self.base_live_corners.reshape(-1, 1, 2), tracking_H
        )[:, 0]
        base_area = abs(cv2.contourArea(self.base_live_corners))
        area_ratio = abs(cv2.contourArea(candidate_corners)) / max(base_area, 1.0)
        if not 0.90 <= area_ratio <= 1.12:
            return None
        handle = cv2.perspectiveTransform(
            self.handle_reference_pixel.reshape(1, 1, 2), tracking_H
        )[0, 0]
        hx, hy = np.rint(handle).astype(int)
        height, width = gray.shape
        if hx < 12 or hy < 12 or hx >= width - 12 or hy >= height - 12:
            return None
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        handle_roi = hsv[hy-12:hy+13, hx-12:hx+13]
        yellow_fraction = float(np.mean(
            (handle_roi[:, :, 0] >= 15) & (handle_roi[:, :, 0] <= 40)
            & (handle_roi[:, :, 1] >= 70) & (handle_roi[:, :, 2] >= 70)
        ))
        if yellow_fraction < 0.12:
            return None
        self.tracking_scores = [
            max(0.0, 1.0 - item[1] / 60.0 - item[2] / 16.0)
            for item in combination
        ]
        self.tracked_live_corners = candidate_corners.astype(np.float32)
        return tracking_H

    def candidate(self, frame, contour):
        rect = cv2.minAreaRect(contour)
        if min(rect[1]) <= 0:
            return None
        ratio = max(rect[1]) / min(rect[1])
        if abs(ratio - self.args.board_width_mm / self.args.board_height_mm) > 0.13:
            return None
        points = ordered_box(cv2.boxPoints(rect))
        box_area = float(rect[1][0] * rect[1][1])
        rectangularity = float(cv2.contourArea(contour) / box_area)
        if rectangularity < self.args.min_rectangularity:
            return None
        # Ensure edge 0->1 represents the physical long (+X candidate) side,
        # including when the board appears portrait in the camera image.
        if np.linalg.norm(points[1] - points[0]) < np.linalg.norm(points[2] - points[1]):
            points = np.roll(points, -1, axis=0)
        destination = np.float32([[0, 0], [699, 0], [699, 549], [0, 549]])
        warp = cv2.warpPerspective(
            frame, cv2.getPerspectiveTransform(points, destination), (700, 550)
        )
        warp_gray = cv2.cvtColor(warp, cv2.COLOR_BGR2GRAY)
        circles = cv2.HoughCircles(
            warp_gray, cv2.HOUGH_GRADIENT, 1.2, 20,
            param1=100, param2=25, minRadius=8, maxRadius=25,
        )
        circle_values = [] if circles is None else np.round(circles[0]).astype(int)
        corner_holes = [
            value for value in circle_values
            if (value[0] < 200 or value[0] > 500)
            and (value[1] < 140 or value[1] > 410)
        ]
        if len(corner_holes) < self.args.min_corner_holes:
            return None

        def signature(image):
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            gold = (hsv[:, :, 0] < 45) & (hsv[:, :, 1] > 55) & (hsv[:, :, 2] > 80)
            values = np.asarray([
                gold[:275, :350].sum(), gold[:275, 350:].sum(),
                gold[275:, 350:].sum(), gold[275:, :350].sum(),
            ], dtype=float)
            total = float(values.sum())
            return values / total if total > 1.0 else np.zeros(4), float(gold.mean())

        reference = np.asarray(self.args.canonical_gold_signature, dtype=float)
        reference /= reference.sum()
        signature_0, color_fraction = signature(warp)
        signature_180 = np.roll(signature_0, 2)
        distance_0 = float(np.sum(np.abs(signature_0 - reference)))
        distance_180 = float(np.sum(np.abs(signature_180 - reference)))
        if min(distance_0, distance_180) > self.args.max_signature_distance or abs(distance_0 - distance_180) < self.args.min_signature_margin:
            direction = 'unknown'
            canonical_points = points
            signature_distance = min(distance_0, distance_180)
        elif distance_0 < distance_180:
            direction = 'canonical'
            canonical_points = points
            signature_distance = distance_0
        else:
            direction = 'rotated_180_corrected'
            canonical_points = np.roll(points, 2, axis=0)
            signature_distance = distance_180
        return {
            'points': points,
            'canonical_points': canonical_points,
            'color_fraction': color_fraction,
            'direction': direction,
            'signature_distance': signature_distance,
            'corner_holes': len(corner_holes),
            'rectangularity': rectangularity,
        }

    def image_cb(self, message):
        frame = cv2.imdecode(np.frombuffer(message.data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return
        annotated = frame.copy()
        if self.robot is not None and int(self.robot.robot_motion_done) != 1:
            cv2.putText(annotated, 'ROBOT MOVING - BOARD OVERLAY HIDDEN', (35, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 165, 255), 3)
            self.publish(message, annotated)
            return
        if self.robot is not None:
            current = np.asarray([
                self.robot.cart_x_cur_pos, self.robot.cart_y_cur_pos, self.robot.cart_z_cur_pos
            ], dtype=float)
            if float(np.linalg.norm(current - self.place_camera_tcp)) <= self.args.place_camera_tolerance_mm:
                selected_display_id = self.target_aliases.get(self.target_slot, self.target_slot)
                tracking_H = self.track_board(frame)
                tracking_valid = tracking_H is not None
                if tracking_H is None:
                    cv2.putText(annotated, 'BOARD TRACKING LOST - OVERLAY HIDDEN',
                                (35, 60), cv2.FONT_HERSHEY_SIMPLEX, .85,
                                (0, 0, 255), 2)
                    self.publish(message, annotated)
                    return
                tracked_outline = np.rint(self.tracked_live_corners).astype(np.int32)
                cv2.polylines(
                    annotated, [tracked_outline], True, (170, 170, 170), 1, cv2.LINE_AA
                )
                for corner in tracked_outline:
                    cv2.circle(
                        annotated, tuple(corner), 3, (170, 170, 170), 1, cv2.LINE_AA
                    )
                selected_center = None
                for slot in self.reference_slots:
                    base_polygon = self.reference_slot_polygons_live[slot['slot_code']]
                    polygon = np.rint(cv2.perspectiveTransform(
                        base_polygon.reshape(-1, 1, 2), tracking_H
                    )[:, 0]).astype(np.int32)
                    center = np.rint(polygon.mean(axis=0)).astype(int)
                    selected_slot = slot['slot_code'] == selected_display_id
                    if selected_slot:
                        selected_center = center.astype(float)
                    completed = slot['slot_code'] in self.completed_slots
                    color = ((0, 255, 0) if completed else tuple(slot['color_bgr']))
                    thickness = 2 if (selected_slot or completed) else 1
                    cv2.polylines(annotated, [polygon], True, color, thickness, cv2.LINE_AA)
                    cv2.drawMarker(annotated, tuple(center), color, cv2.MARKER_CROSS,
                                   7, 1, cv2.LINE_AA)
                    label_at = tuple(center + np.array([6, -6]))
                    label = short_slot_label(slot['slot_code'])
                    cv2.putText(annotated, label, label_at,
                                cv2.FONT_HERSHEY_SIMPLEX, .42, (10, 14, 18), 4, cv2.LINE_AA)
                    cv2.putText(annotated, label, label_at,
                                cv2.FONT_HERSHEY_SIMPLEX, .42, color, 1, cv2.LINE_AA)
                if tracking_valid and selected_center is not None:
                    prefix = selected_display_id.split('-', 1)[0]
                    template_code = {'GPU': 'GPU-01', 'HBM': 'HBM-01'}.get(prefix)
                    if template_code in self.place_templates:
                        xy = (
                            self.pixel_to_base_matrix @ selected_center
                            + self.pixel_to_base_translation
                        )
                        taught = self.place_templates[template_code]['tcp_pose_base_mm_deg']
                        pose_message = PoseStamped()
                        pose_message.header.stamp = self.get_clock().now().to_msg()
                        pose_message.header.frame_id = 'base_link'
                        pose_message.pose.position.x = float(xy[0] / 1000.0)
                        pose_message.pose.position.y = float(xy[1] / 1000.0)
                        pose_message.pose.position.z = float(taught['z'] / 1000.0)
                        quaternion = Rotation.from_euler(
                            'xyz', [taught['a'], taught['b'], taught['c']], degrees=True
                        ).as_quat()
                        pose_message.pose.orientation.x = float(quaternion[0])
                        pose_message.pose.orientation.y = float(quaternion[1])
                        pose_message.pose.orientation.z = float(quaternion[2])
                        pose_message.pose.orientation.w = float(quaternion[3])
                        self.target_publisher.publish(pose_message)
                cv2.putText(annotated, 'PLACECAMERA TRACKED TARGET - GPU/HBM ONLY', (25, 45),
                            cv2.FONT_HERSHEY_SIMPLEX, .72, (0, 255, 255), 2, cv2.LINE_AA)
                self.publish(message, annotated)
                return
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mask = cv2.threshold(gray, self.args.dark_threshold, 255, cv2.THRESH_BINARY_INV)[1]
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        minimum_area = frame.shape[0] * frame.shape[1] * 0.12
        candidates = []
        for contour in contours:
            if cv2.contourArea(contour) < minimum_area:
                continue
            value = self.candidate(frame, contour)
            if value is not None:
                candidates.append(value)
        if not candidates:
            cv2.putText(annotated, 'BOARD NOT DETECTED', (35, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 0, 255), 3)
            self.publish(message, annotated)
            return

        # The empty board has far fewer colored/bright assembled components.
        selected = min(candidates, key=lambda item: item['color_fraction'])
        for item in candidates:
            points = item['points'].astype(int)
            color = (0, 255, 0) if item is selected else (180, 180, 180)
            cv2.polylines(annotated, [points], True, color, 3)

        points = selected['points']
        center = np.mean(points, axis=0).astype(int)
        cross = self.args.cross_size_px
        cv2.line(annotated, (center[0] - cross, center[1]), (center[0] + cross, center[1]), (0, 0, 255), 4)
        cv2.line(annotated, (center[0], center[1] - cross), (center[0], center[1] + cross), (0, 0, 255), 4)
        cv2.circle(annotated, tuple(center), 9, (255, 255, 255), 2)
        direction = selected['direction']
        direction_color = (0, 255, 0) if direction == 'canonical' else (0, 165, 255)
        normalized_points = selected['canonical_points']
        # The center cross stays aligned with the image. Board axes rotate with
        # the detected canonical board frame so visual position and orientation
        # remain separate.
        board_x_edge = np.mean(normalized_points[[1, 2]], axis=0)
        board_y_edge = np.mean(normalized_points[[2, 3]], axis=0)
        # Extend axis tips slightly beyond the detected board boundary so the
        # axes remain visually separate from component-slot annotations.
        board_x_end = np.rint(center + 1.08 * (board_x_edge - center)).astype(int)
        board_y_end = np.rint(center + 1.08 * (board_y_edge - center)).astype(int)
        cv2.arrowedLine(annotated, tuple(center), tuple(board_x_end), (255, 80, 0), 3, tipLength=0.06)
        cv2.arrowedLine(annotated, tuple(center), tuple(board_y_end), (0, 255, 255), 3, tipLength=0.06)
        def axis_label(text, end, color, side):
            vector = end.astype(float) - center.astype(float)
            unit = vector / max(float(np.linalg.norm(vector)), 1.0)
            normal = np.array([-unit[1], unit[0]])
            anchor = end.astype(float) + unit * 20.0 + normal * (12.0 * side)
            size, baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
            x = int(np.clip(anchor[0] - size[0] * 0.5, 5, annotated.shape[1] - size[0] - 5))
            y = int(np.clip(anchor[1] + size[1] * 0.5, size[1] + 5, annotated.shape[0] - 5))
            cv2.rectangle(
                annotated, (x - 5, y - size[1] - 5),
                (x + size[0] + 5, y + baseline + 4), (18, 24, 30), -1,
            )
            cv2.putText(annotated, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)
        axis_label('+X', board_x_end, (255, 80, 0), -2.0)
        axis_label('+Y', board_y_end, (0, 255, 255), 1.0)
        half_x_mm = self.args.board_width_mm * 0.5
        half_y_mm = self.args.board_height_mm * 0.5
        H_board_image = cv2.getPerspectiveTransform(
            np.float32([
                [-half_x_mm, -half_y_mm], [half_x_mm, -half_y_mm],
                [half_x_mm, half_y_mm], [-half_x_mm, half_y_mm],
            ]),
            normalized_points.astype(np.float32),
        )
        selected_display_id = self.target_aliases.get(self.target_slot, self.target_slot)
        for slot in self.display_slots:
            angle = math.radians(slot['long_axis_board_deg'])
            long_half = max(slot['size_mm']) * 0.5
            short_half = min(slot['size_mm']) * 0.5
            long_vector = np.array([math.cos(angle), math.sin(angle)]) * long_half
            short_vector = np.array([-math.sin(angle), math.cos(angle)]) * short_half
            center_board = np.array([slot['x_mm'], slot['y_mm']])
            corners_board = np.float32([
                center_board - long_vector - short_vector,
                center_board + long_vector - short_vector,
                center_board + long_vector + short_vector,
                center_board - long_vector + short_vector,
            ])
            polygon = cv2.perspectiveTransform(
                corners_board.reshape(-1, 1, 2), H_board_image
            ).reshape(-1, 2).astype(int)
            pixel = np.rint(polygon.mean(axis=0)).astype(int)
            selected_slot = slot['slot_id'] == selected_display_id
            completed = slot['slot_id'] in self.completed_slots
            color = (0, 255, 0) if completed else slot['color']
            thickness = 2 if (selected_slot or completed) else 1
            cv2.polylines(annotated, [polygon], True, color, thickness, cv2.LINE_AA)
            cv2.drawMarker(annotated, tuple(pixel), color, cv2.MARKER_CROSS,
                           7, 1, cv2.LINE_AA)
            label_position = tuple(pixel + np.array([7, -7]))
            label = short_slot_label(slot['slot_id'])
            cv2.putText(annotated, label, label_position,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (10, 14, 18), 4, cv2.LINE_AA)
            cv2.putText(annotated, label, label_position,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)
        x_vector = board_x_end - center
        yaw_image_deg = math.degrees(math.atan2(float(x_vector[1]), float(x_vector[0])))
        assembly_state = 'READY' if direction != 'unknown' else 'CHECK'
        panel = annotated.copy()
        panel_right = min(950, annotated.shape[1] - 20)
        cv2.rectangle(panel, (20, 18), (panel_right, 226), (18, 24, 30), -1)
        cv2.addWeighted(panel, 0.72, annotated, 0.28, 0.0, annotated)
        status_color = (80, 230, 80) if assembly_state == 'READY' else (0, 180, 255)
        cv2.putText(annotated, f'BOARD  {assembly_state}', (42, 58),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.05, status_color, 3)
        target_display = next(
            (slot for slot in self.display_slots if slot['slot_id'] == selected_display_id), None
        )
        target_name = target_display['label'] if target_display is not None else 'NONE'
        cv2.putText(annotated, f'Orientation  {direction.upper()}    Yaw  {yaw_image_deg:+.2f} deg', (42, 98),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.70, (230, 230, 230), 2)
        cv2.putText(annotated, f'Center  {center[0]}, {center[1]} px    Target  {target_name}',
                    (42, 136), cv2.FONT_HERSHEY_SIMPLEX, 0.70,
                    (255, 0, 255) if target_display is not None else (190, 200, 210), 2)
        cv2.putText(annotated, f'geometry  holes={selected["corner_holes"]}  rect={selected["rectangularity"]:.2f}  dirErr={selected["signature_distance"]:.2f}',
                    (42, 174), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (180, 190, 200), 2)

        if self.K is not None and self.robot is not None and direction != 'unknown':
            half_x = self.args.board_width_mm / 2000.0
            half_y = self.args.board_height_mm / 2000.0
            object_points = np.float32([
                [-half_x, -half_y, 0], [half_x, -half_y, 0],
                [half_x, half_y, 0], [-half_x, half_y, 0],
            ])
            ok, rvec, tvec = cv2.solvePnP(
                object_points, normalized_points, self.K, self.D,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )
            if ok:
                R_camera_board, _ = cv2.Rodrigues(rvec)
                T_camera_board = transform(R_camera_board, np.asarray(tvec).reshape(3))
                state = self.robot
                T_base_flange = transform(
                    Rotation.from_euler('xyz', [
                        state.flange_a_cur_pos, state.flange_b_cur_pos, state.flange_c_cur_pos
                    ], degrees=True).as_matrix(),
                    np.asarray([state.flange_x_cur_pos, state.flange_y_cur_pos, state.flange_z_cur_pos]) / 1000.0,
                )
                base_mm = (T_base_flange @ self.T_flange_camera @ T_camera_board)[:3, 3] * 1000.0
                cv2.putText(annotated, f'base XYZ  {base_mm[0]:.1f}, {base_mm[1]:.1f}, {base_mm[2]:.1f} mm',
                            (430, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 230, 80), 2)
                target = next((slot for slot in self.recipe_slots if slot['slot_id'] == self.target_slot), None)
                if target is not None:
                    T_board_slot = np.eye(4)
                    T_board_slot[:3, 3] = [
                        target['x_mm'] / 1000.0, target['y_mm'] / 1000.0, 0.0
                    ]
                    T_base_slot = T_base_flange @ self.T_flange_camera @ T_camera_board @ T_board_slot
                    target_base_mm = T_base_slot[:3, 3] * 1000.0
                    cv2.putText(
                        annotated,
                        f'TARGET {target_name}  XYZ {target_base_mm[0]:.1f}, {target_base_mm[1]:.1f}, {target_base_mm[2]:.1f} mm',
                        (42, 212), cv2.FONT_HERSHEY_SIMPLEX, 0.70, (255, 0, 255), 2,
                    )
                    pose_message = PoseStamped()
                    pose_message.header = message.header
                    pose_message.header.frame_id = 'base'
                    pose_message.pose.position.x = float(T_base_slot[0, 3])
                    pose_message.pose.position.y = float(T_base_slot[1, 3])
                    pose_message.pose.position.z = float(T_base_slot[2, 3])
                    quaternion = Rotation.from_matrix(T_base_slot[:3, :3]).as_quat()
                    pose_message.pose.orientation.x = float(quaternion[0])
                    pose_message.pose.orientation.y = float(quaternion[1])
                    pose_message.pose.orientation.z = float(quaternion[2])
                    pose_message.pose.orientation.w = float(quaternion[3])
                    self.target_publisher.publish(pose_message)
        self.publish(message, annotated)

    def publish(self, source, frame):
        ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.args.jpeg_quality])
        if not ok:
            return
        output = CompressedImage()
        output.header = source.header
        output.format = 'jpeg'
        output.data = encoded.tobytes()
        self.publisher.publish(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--node-name', default='board_view')
    parser.add_argument('--board-width-mm', type=float, default=139.0)
    parser.add_argument('--board-height-mm', type=float, default=110.0)
    parser.add_argument('--dark-threshold', type=int, default=70)
    parser.add_argument('--min-rectangularity', type=float, default=0.78)
    parser.add_argument('--min-corner-holes', type=int, default=6)
    parser.add_argument('--canonical-gold-signature', type=float, nargs=4,
                        default=(0.053, 0.390, 0.300, 0.257))
    parser.add_argument('--max-signature-distance', type=float, default=0.40)
    parser.add_argument('--min-signature-margin', type=float, default=0.10)
    parser.add_argument('--cross-size-px', type=int, default=45)
    parser.add_argument('--jpeg-quality', type=int, default=95)
    parser.add_argument('--image-topic', default='/camera/camera/color/image_raw/compressed')
    parser.add_argument('--camera-info-topic', default='/camera/camera/color/camera_info')
    parser.add_argument('--robot-state-topic', default='/nonrt_state_data')
    parser.add_argument('--output-topic', default='/vision/board/image/compressed')
    parser.add_argument('--target-pose-topic', default='/vision/board/target_pose_legacy_unvalidated')
    parser.add_argument('--target-selection-topic', default='/vision/board/selected_target')
    parser.add_argument('--assembly-progress-topic', default='/assembly/progress')
    project_root = Path(__file__).resolve().parents[2]
    parser.add_argument('--handeye-file', type=Path, default=project_root / 'calibration/data/handeye_result.json')
    parser.add_argument('--layout-file', type=Path, default=project_root / 'vision_assembly/config/board_layout_from_unity.json')
    parser.add_argument('--physical-board-file', type=Path, default=project_root / 'vision_assembly/config/physical_board.json')
    parser.add_argument('--assembly-layout-file', type=Path, default=project_root / 'vision_assembly/config/assembly_layout_approx.json')
    parser.add_argument('--slot-layout-file', type=Path, default=project_root / 'vision_assembly/config/assembly_slots_r1.json')
    parser.add_argument('--reference-registration-file', type=Path, default=project_root / 'vision_assembly/config/assembly_reference_registration.json')
    parser.add_argument('--reference-slots-file', type=Path, default=project_root / 'vision_assembly/config/assembly_reference_slots_r1.json')
    parser.add_argument('--place-calibration-file', type=Path, default=project_root / 'vision_assembly/config/assembly_place_calibration.json')
    parser.add_argument('--board-holes-file', type=Path, default=project_root / 'vision_assembly/config/assembly_board_holes.json')
    parser.add_argument('--direct-slots-file', type=Path, default=project_root / 'vision_assembly/config/assembly_slots_direct.json')
    parser.add_argument('--place-camera-tolerance-mm', type=float, default=12.0)
    parser.add_argument('--show-recipe', default='right_white_brown')
    parser.add_argument('--target-slot', default='GPU-01')
    args = parser.parse_args()
    rclpy.init()
    node = BoardView(args)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
