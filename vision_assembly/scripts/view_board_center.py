#!/usr/bin/env python3
"""Publish a live empty-board center overlay; never commands robot motion."""

import argparse
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
        layout = json.loads(args.layout_file.read_text(encoding='utf-8'))
        physical = json.loads(args.physical_board_file.read_text(encoding='utf-8'))
        assembly = json.loads(args.assembly_layout_file.read_text(encoding='utf-8'))
        code_by_type = {
            'GPU': 'G', 'HBM': 'H', 'Power Module': 'P',
            'VRM': 'V', 'Inductor': 'I', 'SMD Capacitor': 'S',
        }
        color_by_type = {
            'GPU': (255, 80, 255), 'HBM': (80, 220, 120),
            'Power Module': (70, 150, 255), 'VRM': (220, 120, 255),
            'Inductor': (255, 130, 40), 'SMD Capacitor': (255, 230, 80),
        }
        self.display_slots = []
        self.target_aliases = {}
        for component_type, component in assembly['component_types'].items():
            code = code_by_type[component_type]
            color = color_by_type[component_type]
            for index, slot in enumerate(component['slots'], 1):
                self.display_slots.append({
                    'slot_id': slot['id'], 'label': f'{code}{index}',
                    'x_mm': float(slot['x_mm']), 'y_mm': float(slot['y_mm']),
                    'color': color,
                })
                if component_type == 'SMD Capacitor':
                    self.target_aliases[f'right_white_brown_{index:02d}'] = slot['id']
        scale_x = args.board_width_mm / float(layout['board']['size_mm']['x'])
        scale_y = args.board_height_mm / float(layout['board']['size_mm']['y'])
        self.recipe_slots = []
        for placement in layout['placements']:
            if placement['recipe'] != args.show_recipe:
                continue
            center_board = placement['center_board_mm']
            self.recipe_slots.append({
                'slot_id': placement['slot_id'],
                'x_mm': float(center_board['x']) * scale_x,
                'y_mm': float(center_board['y']) * scale_y,
            })
        override = physical.get('physical_slot_overrides', {}).get(args.show_recipe)
        if override is not None:
            self.recipe_slots = [
                {
                    'slot_id': slot['slot_id'],
                    'x_mm': float(slot['x_mm']),
                    'y_mm': float(slot['y_mm']),
                }
                for slot in override['slots']
            ]
        self.inferred_slots = []
        if override is None and len(self.recipe_slots) >= 2:
            ordered = sorted(self.recipe_slots, key=lambda slot: slot['y_mm'])
            spacing = float(np.median(np.diff([slot['y_mm'] for slot in ordered])))
            self.inferred_slots = [
                {
                    'slot_id': 'candidate_A_above_S1',
                    'x_mm': ordered[0]['x_mm'],
                    'y_mm': ordered[0]['y_mm'] - spacing,
                    'label': 'A',
                },
                {
                    'slot_id': 'candidate_B_below_S4',
                    'x_mm': ordered[-1]['x_mm'],
                    'y_mm': ordered[-1]['y_mm'] + spacing,
                    'label': 'B',
                },
            ]
        self.publisher = self.create_publisher(CompressedImage, args.output_topic, qos_profile_sensor_data)
        self.target_publisher = self.create_publisher(PoseStamped, args.target_pose_topic, 10)
        self.create_subscription(CameraInfo, args.camera_info_topic, self.info_cb, qos_profile_sensor_data)
        self.create_subscription(RobotNonrtState, args.robot_state_topic, self.robot_cb, 10)
        self.create_subscription(CompressedImage, args.image_topic, self.image_cb, qos_profile_sensor_data)
        self.create_subscription(String, args.target_selection_topic, self.target_selection_cb, 10)
        self.get_logger().info(
            f'NO MOTION board overlay: {args.image_topic} -> {args.output_topic}'
        )

    def info_cb(self, message):
        self.K = np.asarray(message.k, dtype=float).reshape(3, 3)
        self.D = np.asarray(message.d, dtype=float)

    def robot_cb(self, message):
        self.robot = message

    def target_selection_cb(self, message):
        self.target_slot = message.data.strip()

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
            pixel = cv2.perspectiveTransform(
                np.float32([[[slot['x_mm'], slot['y_mm']]]]), H_board_image
            ).reshape(2).astype(int)
            selected_slot = slot['slot_id'] == selected_display_id
            color = (255, 0, 255) if selected_slot else slot['color']
            marker_size = 20 if selected_slot else 13
            thickness = 3 if selected_slot else 2
            cv2.drawMarker(annotated, tuple(pixel), color, cv2.MARKER_CROSS, marker_size, thickness)
            label_position = tuple(pixel + np.array([7, -7]))
            cv2.putText(annotated, slot['label'], label_position,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (10, 14, 18), 4, cv2.LINE_AA)
            cv2.putText(annotated, slot['label'], label_position,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, color, 2, cv2.LINE_AA)
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
    parser.add_argument('--target-pose-topic', default='/vision/board/target_pose')
    parser.add_argument('--target-selection-topic', default='/vision/board/selected_target')
    project_root = Path(__file__).resolve().parents[2]
    parser.add_argument('--handeye-file', type=Path, default=project_root / 'calibration/data/handeye_result.json')
    parser.add_argument('--layout-file', type=Path, default=project_root / 'vision_assembly/config/board_layout_from_unity.json')
    parser.add_argument('--physical-board-file', type=Path, default=project_root / 'vision_assembly/config/physical_board.json')
    parser.add_argument('--assembly-layout-file', type=Path, default=project_root / 'vision_assembly/config/assembly_layout_approx.json')
    parser.add_argument('--show-recipe', default='right_white_brown')
    parser.add_argument('--target-slot', default='')
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
