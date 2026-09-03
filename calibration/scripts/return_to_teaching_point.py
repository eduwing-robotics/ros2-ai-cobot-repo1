#!/usr/bin/env python3
"""Return the FR5 TCP safely to a named controller teaching point."""

import argparse
import math
import time

import numpy as np
import rclpy
from fairino_msgs.msg import RobotNonrtState
from fairino_msgs.srv import RemoteCmdInterface
from rclpy.node import Node
from scipy.spatial.transform import Rotation


class ReturnMover(Node):
    def __init__(self):
        super().__init__('return_to_teaching_point')
        self.state = None
        self.create_subscription(RobotNonrtState, '/nonrt_state_data', self.state_cb, 10)
        self.client = self.create_client(RemoteCmdInterface, '/fairino_remote_command_service')

    def state_cb(self, message):
        self.state = message

    def wait_state(self, timeout=8.0):
        deadline = time.monotonic() + timeout
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.state is not None:
                return
        raise RuntimeError('No /nonrt_state_data received')

    def command(self, text, timeout=90.0):
        request = RemoteCmdInterface.Request()
        request.cmd_str = text
        future = self.client.call_async(request)
        deadline = time.monotonic() + timeout
        while rclpy.ok() and not future.done() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
        if not future.done():
            raise RuntimeError(f"Command timeout; no later waypoint sent: {text}")
        if future.result() is None:
            raise RuntimeError(f'No response: {text}')
        result = str(future.result().cmd_res)
        if result.split(',', 1)[0] != '0':
            raise RuntimeError(f'FR5 rejected {text}: {result}')
        return result

    def wait_pose(self, target_pose, target_joints, timeout=90.0):
        target_xyz=np.asarray(target_pose[:3],dtype=float)
        target_rotation=Rotation.from_euler('xyz',target_pose[3:],degrees=True)
        deadline=time.monotonic()+timeout
        while rclpy.ok() and time.monotonic()<deadline:
            rclpy.spin_once(self,timeout_sec=0.1)
            state=self.state
            if state is None: continue
            if (int(state.emg)!=0 or int(state.abnormal_stop)!=0
                    or int(state.main_error_code)!=0 or float(state.collision_err)!=0.0):
                raise RuntimeError('robot safety fault during teaching-point return')
            xyz=np.asarray([state.cart_x_cur_pos,state.cart_y_cur_pos,state.cart_z_cur_pos])
            rotation=Rotation.from_euler('xyz',[state.cart_a_cur_pos,state.cart_b_cur_pos,state.cart_c_cur_pos],degrees=True)
            angle_error=math.degrees((rotation.inv()*target_rotation).magnitude())
            joints=np.asarray([state.j1_cur_pos,state.j2_cur_pos,state.j3_cur_pos,state.j4_cur_pos,state.j5_cur_pos,state.j6_cur_pos])
            if (int(state.robot_motion_done)==1
                    and float(np.linalg.norm(xyz-target_xyz))<=1.0
                    and angle_error<=1.0
                    and float(np.max(np.abs(joints-target_joints)))<=1.0):
                return
        raise RuntimeError('teaching-point return pose/joint verification timeout')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--point-name', default='TrayHome')
    parser.add_argument('--speed-percent', type=int, default=40)
    parser.add_argument('--vertical-speed-percent', type=int, default=20)
    parser.add_argument('--safe-clearance-mm', type=float, default=100.0)
    parser.add_argument('--horizontal-z-mm', type=float, help='explicit safe horizontal travel Z; must be at least current Z and 100 mm')
    parser.add_argument('--max-distance-mm', type=float, default=500.0)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-return', action='store_true')
    args = parser.parse_args()

    if args.execute != args.confirm_return:
        parser.error('actual return requires --execute and --confirm-return')
    if args.dry_run and args.execute:
        parser.error('--dry-run and --execute cannot be combined')
    if not 1 <= args.speed_percent <= 50 or not 1 <= args.vertical_speed_percent <= 50:
        parser.error('speed values must be between 1 and 50')
    if args.safe_clearance_mm < 50.0:
        parser.error('--safe-clearance-mm must be at least 50')

    rclpy.init()
    node = ReturnMover()
    try:
        if not node.client.wait_for_service(timeout_sec=3.0):
            raise RuntimeError('/fairino_remote_command_service unavailable')
        point_result = node.command(f'GetRobotTeachingPoint({args.point_name})')
        fields = point_result.split(',')
        if len(fields) < 15:
            raise RuntimeError(f'invalid teaching-point response: {point_result}')
        values = [float(value) for value in fields[1:]]
        target = values[:6]
        tool_id = int(round(values[12]))
        user_id = int(round(values[13]))
        if not all(math.isfinite(value) for value in target):
            raise RuntimeError('teaching point contains NaN/Inf')

        node.wait_state()
        state = node.state
        current = [
            float(state.cart_x_cur_pos), float(state.cart_y_cur_pos),
            float(state.cart_z_cur_pos), float(state.cart_a_cur_pos),
            float(state.cart_b_cur_pos), float(state.cart_c_cur_pos),
        ]
        distance = math.dist(current[:3], target[:3])
        if distance > args.max_distance_mm:
            raise RuntimeError(f'return distance {distance:.1f} mm exceeds {args.max_distance_mm:.1f} mm')
        if int(state.tool_num) != tool_id:
            raise RuntimeError(f'active tool={state.tool_num}, teaching point tool={tool_id}')
        if args.execute and int(state.robot_mode) != 0:
            raise RuntimeError(f'robot_mode={state.robot_mode}; AUTO mode 0 required')
        if int(state.emg) != 0 or int(state.main_error_code) != 0:
            raise RuntimeError('robot emergency/error state is not clear')

        safe_z = float(args.horizontal_z_mm) if args.horizontal_z_mm is not None else max(current[2], target[2] + args.safe_clearance_mm)
        if not math.isfinite(safe_z) or safe_z < current[2] - 1.0 or safe_z < 100.0:
            raise RuntimeError(f"unsafe horizontal Z {safe_z:.1f}; current Z={current[2]:.1f}, minimum=100.0")
        waypoints = []
        if safe_z - current[2] > 1.0:
            waypoints.append((current[:2] + [safe_z] + current[3:], args.vertical_speed_percent, 'vertical raise'))
        waypoints.append(([target[0], target[1], safe_z] + target[3:], args.speed_percent, 'horizontal return'))
        if abs(safe_z - target[2]) > 1.0:
            final_label = 'final ascent' if target[2] > safe_z else 'final descent'
            waypoints.append((target, args.vertical_speed_percent, final_label))

        print(f"RETURN TO TEACHING POINT: {args.point_name}")
        print(f"Target TCP/Base: {[round(value, 3) for value in target]}, tool={tool_id}, user={user_id}")
        for index, (pose, speed, label) in enumerate(waypoints, 1):
            print(f"Stage {index}/{len(waypoints)} {label}: {[round(value, 3) for value in pose]}, speed={speed}%")
        if not args.execute:
            print('DRY RUN - ROBOT DID NOT MOVE')
            return
        node.command(f'SetSpeed({args.speed_percent})')
        print(f'Controller global speed set to {args.speed_percent}%')
        reference=np.asarray([
            state.j1_cur_pos,state.j2_cur_pos,state.j3_cur_pos,
            state.j4_cur_pos,state.j5_cur_pos,state.j6_cur_pos,
        ],dtype=float)
        soft=np.asarray([float(value) for value in node.command('GetJointSoftLimitDeg(1)').split(',')[1:13]])
        negative,positive=soft[:6],soft[6:]
        for index, (pose, speed, label) in enumerate(waypoints, 1):
            safety=np.asarray([float(value) for value in node.command('GetSafetyStopState()').split(',')[1:3]])
            if np.any(safety!=0.0):
                raise RuntimeError(f'safety stop active: {safety.astype(int).tolist()}')
            ik_command='GetInverseKinRef('+','.join(
                f'{value:.6f}' for value in [0.0,*pose,*reference.tolist()]
            )+')'
            joints=np.asarray([float(value) for value in node.command(ik_command).split(',')[1:7]])
            margins=np.minimum(joints-negative,positive-joints)
            if np.any(margins<10.0) or np.any(np.abs(joints-reference)>95.0):
                raise RuntimeError(f'{label} IK violates joint margin or branch-change limit')
            define='JNTPoint(1,'+','.join(f'{value:.6f}' for value in joints)+')'
            linear=label in ('vertical raise','final ascent','final descent')
            motion='MoveL' if linear else 'MoveJ'
            command=f'{motion}(JNT1,{speed},{tool_id},{user_id})'
            print(f'Sending stage {index}/{len(waypoints)} ({label}): {define}; {command}')
            node.command(define)
            node.command(command)
            node.wait_pose(pose,joints)
            reference=joints
        print(f'Returned to teaching point {args.point_name}')
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
