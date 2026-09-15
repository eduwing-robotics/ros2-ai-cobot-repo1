#!/usr/bin/env python3
"""Close the gripper at the current pick pose and lift vertically."""

import argparse
import math
import time

import numpy as np

import rclpy
from fairino_msgs.msg import RobotNonrtState
from fairino_msgs.srv import RemoteCmdInterface
from rclpy.node import Node
from scipy.spatial.transform import Rotation


class LiftNode(Node):
    def __init__(self):
        super().__init__('lift_grasped_part')
        self.state = None
        self.create_subscription(RobotNonrtState, '/nonrt_state_data', self.cb, 10)
        self.client = self.create_client(RemoteCmdInterface, '/fairino_remote_command_service')

    def cb(self, message): self.state = message

    def wait_state(self):
        deadline = time.monotonic() + 8.0
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.state is not None: return
        raise RuntimeError('No robot state')

    def command(self, text):
        request = RemoteCmdInterface.Request(); request.cmd_str = text
        future = self.client.call_async(request); rclpy.spin_until_future_complete(self, future)
        result = str(future.result().cmd_res)
        if result.split(',', 1)[0] != '0': raise RuntimeError(f'FR5 rejected {text}: {result}')
        return result

    def wait_gripper_complete(self, timeout=6.0):
        # Do not trust the state received before MoveGripper.  Allow the
        # controller/gripper to start, then require a fresh completion state.
        time.sleep(0.35)
        deadline = time.monotonic() + timeout
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.state is not None and int(self.state.grip_motion_done) in (1, 2):
                return int(self.state.grip_motion_done)
        raise RuntimeError('Gripper did not report completion; lift blocked')

    def get_gripper_position(self):
        result = self.command('GetGripperCurPosition(1)')
        values = result.split(',')
        if len(values) < 3:
            raise RuntimeError(f'Unexpected gripper-position response: {result}')
        return int(float(values[-1]))

    def wait_motion_done(self, target_pose, target_joints, timeout=90.0, tolerance_mm=1.0):
        deadline=time.monotonic()+timeout
        target=np.asarray(target_pose[:3],dtype=float)
        target_rotation=Rotation.from_euler('xyz',target_pose[3:],degrees=True)
        while rclpy.ok() and time.monotonic()<deadline:
            rclpy.spin_once(self,timeout_sec=0.1)
            if self.state is None:continue
            if (int(self.state.emg)!=0 or int(self.state.abnormal_stop)!=0
                    or int(self.state.main_error_code)!=0 or float(self.state.collision_err)!=0.0):
                raise RuntimeError('robot emergency/stop/error/collision state is not clear')
            current=np.asarray([self.state.cart_x_cur_pos,self.state.cart_y_cur_pos,self.state.cart_z_cur_pos],dtype=float)
            rotation=Rotation.from_euler('xyz',[self.state.cart_a_cur_pos,self.state.cart_b_cur_pos,self.state.cart_c_cur_pos],degrees=True)
            angle_error=math.degrees((rotation.inv()*target_rotation).magnitude())
            joints=np.asarray([self.state.j1_cur_pos,self.state.j2_cur_pos,self.state.j3_cur_pos,self.state.j4_cur_pos,self.state.j5_cur_pos,self.state.j6_cur_pos],dtype=float)
            if (int(self.state.robot_motion_done)==1
                    and float(np.linalg.norm(current-target))<=tolerance_mm
                    and angle_error<=1.0
                    and float(np.max(np.abs(joints-target_joints)))<=1.0):
                return
        raise RuntimeError('lift pose/joint verification timeout')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lift-mm', type=float, default=100.0)
    parser.add_argument('--speed-percent', type=int, default=15)
    parser.add_argument('--close-position', type=int, default=5)
    parser.add_argument('--skip-close', action='store_true', help='lift only after verifying the gripper is already closed')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-grasp', action='store_true')
    args = parser.parse_args()
    if args.execute != args.confirm_grasp: parser.error('requires --execute --confirm-grasp')
    if not 1 <= args.lift_mm <= 120: parser.error('--lift-mm must be 1..120')
    rclpy.init(); node = LiftNode()
    try:
        node.wait_state(); state = node.state
        if int(state.robot_mode) != 0: raise RuntimeError('AUTO mode required')
        pose = [state.cart_x_cur_pos, state.cart_y_cur_pos, state.cart_z_cur_pos,
                state.cart_a_cur_pos, state.cart_b_cur_pos, state.cart_c_cur_pos]
        target = list(pose); target[2] += args.lift_mm
        print('GRASP AND VERTICAL LIFT')
        print('Current TCP/Base:', [round(float(v), 3) for v in pose])
        print('Lift target:', [round(float(v), 3) for v in target])
        if not args.execute:
            print('DRY RUN - ROBOT DID NOT MOVE'); return
        if not node.client.wait_for_service(timeout_sec=3): raise RuntimeError('command service unavailable')
        before = node.get_gripper_position()
        print(f'Gripper position before close: {before}')
        if args.skip_close:
            after=before;grip_state=int(state.grip_motion_done)
            print(f'Gripper close skipped; verified current position={after}')
        else:
            node.command(f'MoveGripper(1,{args.close_position})')
            grip_state = node.wait_gripper_complete()
            time.sleep(0.5)
            after = node.get_gripper_position()
            print(
                f'Gripper close completed: command={args.close_position}, '
                f'actual={after}, state={grip_state}'
            )
        # A fully open reading after a close command means the part was not
        # grasped.  Never lift in that state.  When a part is held, the actual
        # position may legitimately stop above the commanded value.
        if after >= 95:
            raise RuntimeError(
                f'Gripper remained open (actual={after}); lift blocked'
            )
        time.sleep(0.5)
        reference=np.asarray([
            state.j1_cur_pos,state.j2_cur_pos,state.j3_cur_pos,
            state.j4_cur_pos,state.j5_cur_pos,state.j6_cur_pos,
        ],dtype=float)
        soft=np.asarray([float(value) for value in node.command('GetJointSoftLimitDeg(1)').split(',')[1:13]])
        negative,positive=soft[:6],soft[6:]
        safety=np.asarray([float(value) for value in node.command('GetSafetyStopState()').split(',')[1:3]])
        if np.any(safety!=0.0):
            raise RuntimeError(f'safety stop active: {safety.astype(int).tolist()}')
        ik_command='GetInverseKinRef('+','.join(
            f'{value:.6f}' for value in [0.0,*target,*reference.tolist()]
        )+')'
        target_joints=np.asarray([float(value) for value in node.command(ik_command).split(',')[1:7]])
        margins=np.minimum(target_joints-negative,positive-target_joints)
        if np.any(margins<10.0) or np.any(np.abs(target_joints-reference)>90.0):
            raise RuntimeError('vertical lift IK violates joint margin or branch-change limit')
        node.command('JNTPoint(1,'+','.join(f'{value:.6f}' for value in target_joints)+')')
        node.command(f'MoveL(JNT1,{args.speed_percent},1,0)')
        node.wait_motion_done(target,target_joints)
        print(f'Initial slow lift completed: {args.lift_mm:.1f} mm')
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()


if __name__ == '__main__': main()
