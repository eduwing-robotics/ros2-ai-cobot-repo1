#!/usr/bin/env python3
"""Move the FR5 TCP to a precomputed non-contact object approach point."""

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import rclpy
from fairino_msgs.msg import RobotNonrtState
from fairino_msgs.srv import RemoteCmdInterface
from rclpy.node import Node
from scipy.spatial.transform import Rotation


def symmetric_angle_delta_deg(target_deg, current_deg):
    """Smallest rotation aligning an unoriented rectangular axis (period 180°)."""
    return (target_deg - current_deg + 90.0) % 180.0 - 90.0


class Mover(Node):
    def __init__(self):
        super().__init__("move_object_approach")
        self.state = None
        self.create_subscription(RobotNonrtState, "/nonrt_state_data", self.cb, 10)
        self.client = self.create_client(RemoteCmdInterface, "/fairino_remote_command_service")

    def cb(self, msg): self.state = msg

    def wait_state(self, timeout=8.0):
        end=time.monotonic()+timeout
        while rclpy.ok() and time.monotonic()<end:
            rclpy.spin_once(self,timeout_sec=.1)
            if self.state is not None:return
        raise RuntimeError("No /nonrt_state_data received")

    def command(self, text):
        req=RemoteCmdInterface.Request(); req.cmd_str=text
        future=self.client.call_async(req); rclpy.spin_until_future_complete(self,future)
        result=str(future.result().cmd_res)
        if result!="0":raise RuntimeError(f"FR5 rejected command: {text}, result={result}")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--x",type=float); p.add_argument("--y",type=float); p.add_argument("--z",type=float)
    p.add_argument("--target-file",type=Path)
    p.add_argument("--align-part",action="store_true",help="align the gripper axis with the detected part long axis")
    p.add_argument("--gripper-axis",choices=("tool_x","tool_y"),default="tool_x")
    p.add_argument("--max-rotation-deg",type=float,default=90.0)
    p.add_argument("--tool-correction-x-mm",type=float,default=-2.05)
    p.add_argument("--tool-correction-y-mm",type=float,default=-2.55)
    p.add_argument("--center-correction",action=argparse.BooleanOptionalAction,default=True)
    p.add_argument("--approach-offset-mm",type=float,default=100.0)
    p.add_argument("--max-target-age-sec",type=float,default=120.0)
    p.add_argument("--speed-percent",type=int,default=50)
    p.add_argument("--descent-speed-percent",type=int,default=50)
    p.add_argument("--rotation-speed-percent",type=int,default=50)
    p.add_argument("--safe-clearance-mm",type=float,default=100); p.add_argument("--max-distance-mm",type=float,default=450)
    p.add_argument("--tool-id",type=int,default=1); p.add_argument("--user-id",type=int,default=0)
    p.add_argument("--dry-run",action="store_true"); p.add_argument("--execute",action="store_true"); p.add_argument("--confirm-move",action="store_true")
    a=p.parse_args()
    direct_values = (a.x, a.y, a.z)
    if a.target_file is not None and any(value is not None for value in direct_values):
        p.error("--target-file cannot be combined with --x/--y/--z")
    if a.target_file is None and not all(value is not None for value in direct_values):
        p.error("provide either --target-file or all of --x --y --z")
    if a.target_file is not None:
        try:
            payload=json.loads(a.target_file.read_text(encoding="utf-8"))
            age=time.time()-float(payload["timestamp_unix"])
            center=np.asarray(payload["part_center_base_mm"],dtype=float)
            part_base_angle=float(payload.get("long_axis_angle_base_deg", "nan"))
        except (OSError,KeyError,ValueError,TypeError,json.JSONDecodeError) as exc:
            p.error(f"cannot load target file: {exc}")
        if age < -5 or age > a.max_target_age_sec:
            p.error(f"target file is stale ({age:.1f} s); detect the part again")
        a.x=float(center[0]); a.y=float(center[1]); a.z=float(center[2]+a.approach_offset_mm)
    if a.execute != a.confirm_move:p.error("실제 이동에는 --execute와 --confirm-move가 모두 필요합니다")
    if a.dry_run and a.execute:p.error("--dry-run and --execute cannot be combined")
    if not 1<=a.speed_percent<=50:p.error("--speed-percent must be between 1 and 50")
    if not 1<=a.descent_speed_percent<=50:p.error("--descent-speed-percent must be between 1 and 50")
    if not 1<=a.rotation_speed_percent<=50:p.error("--rotation-speed-percent must be between 1 and 50")
    if not 0<a.max_rotation_deg<=90:p.error("--max-rotation-deg must be in (0, 90]")
    if a.safe_clearance_mm<50:p.error("--safe-clearance-mm must be >= 50")
    rclpy.init(); n=Mover()
    try:
        n.wait_state(); s=n.state
        if int(s.tool_num)!=a.tool_id:raise RuntimeError(f"active tool={s.tool_num}, expected {a.tool_id}")
        if a.execute and int(s.robot_mode)!=0:raise RuntimeError(f"robot_mode={s.robot_mode}; AUTO mode 0 required")
        if a.execute and int(s.emg)!=0:raise RuntimeError("emergency stop is active")
        if a.execute and int(s.robot_motion_done)!=1:raise RuntimeError("robot is not stationary")
        current=np.array([s.cart_x_cur_pos,s.cart_y_cur_pos,s.cart_z_cur_pos],float)
        abc=[float(s.cart_a_cur_pos),float(s.cart_b_cur_pos),float(s.cart_c_cur_pos)]
        target_abc=list(abc)
        target_rotation=Rotation.from_euler("xyz",target_abc,degrees=True).as_matrix()
        rotation_delta=0.0
        if a.align_part:
            if a.target_file is None:
                p.error("--align-part requires --target-file")
            if not math.isfinite(part_base_angle):
                raise RuntimeError("target file has no valid Base-frame part angle; detect the part again")
            current_rotation=Rotation.from_euler("xyz",abc,degrees=True).as_matrix()
            axis_index=0 if a.gripper_axis=="tool_x" else 1
            axis_xy=current_rotation[:2,axis_index]
            if np.linalg.norm(axis_xy)<0.5:
                raise RuntimeError(f"{a.gripper_axis} is nearly vertical; cannot align in Base XY")
            current_axis_angle=math.degrees(math.atan2(axis_xy[1],axis_xy[0]))
            rotation_delta=symmetric_angle_delta_deg(part_base_angle,current_axis_angle)
            if abs(rotation_delta)>a.max_rotation_deg+1e-6:
                raise RuntimeError(f"required rotation {rotation_delta:.1f} deg exceeds limit {a.max_rotation_deg:.1f}")
            base_z_rotation=Rotation.from_euler("z",rotation_delta,degrees=True).as_matrix()
            target_rotation=base_z_rotation@current_rotation
            target_abc=Rotation.from_matrix(target_rotation).as_euler("xyz",degrees=True).tolist()
        correction_tool=np.asarray([
            a.tool_correction_x_mm,
            a.tool_correction_y_mm,
            0.0,
        ]) if a.center_correction and a.target_file is not None else np.zeros(3)
        correction_base=target_rotation@correction_tool
        a.x+=float(correction_base[0]); a.y+=float(correction_base[1]); a.z+=float(correction_base[2])
        values=np.array([a.x,a.y,a.z],float)
        if not np.all(np.isfinite(values)):raise RuntimeError("target contains NaN/Inf")
        distance=float(np.linalg.norm(values-current))
        if distance>a.max_distance_mm:raise RuntimeError(f"target distance {distance:.1f} mm exceeds limit {a.max_distance_mm:.1f}")
        safe_z=max(float(current[2]),a.z+a.safe_clearance_mm)
        waypoints=[]
        if safe_z-current[2]>1:waypoints.append((current[0],current[1],safe_z,abc,a.descent_speed_percent,"vertical raise"))
        if abs(rotation_delta)>0.5:waypoints.append((current[0],current[1],safe_z,target_abc,a.rotation_speed_percent,"part orientation alignment"))
        waypoints.append((a.x,a.y,safe_z,target_abc,a.speed_percent,"horizontal positioning"))
        if safe_z-a.z>1:waypoints.append((a.x,a.y,a.z,target_abc,a.descent_speed_percent,"vertical approach"))
        print("OBJECT APPROACH ONLY - no surface descent, no gripper command")
        print(f"Target TCP/Base [mm]: [{a.x:.3f}, {a.y:.3f}, {a.z:.3f}]")
        print(f"Center correction Tool [mm]: {np.round(correction_tool,3).tolist()}; Base [mm]: {np.round(correction_base,3).tolist()}")
        if a.align_part:
            print(f"Part long axis/Base XY: {part_base_angle:.3f} deg")
            print(f"Gripper alignment: {a.gripper_axis}, delta={rotation_delta:.3f} deg, target ABC={np.round(target_abc,3).tolist()}")
        else:
            print(f"Current orientation preserved: {np.round(abc,3).tolist()}; distance={distance:.1f} mm")
        for i,w in enumerate(waypoints,1):print(f"Stage {i}/{len(waypoints)} {w[5]}: [{w[0]:.3f}, {w[1]:.3f}, {w[2]:.3f}], ABC={np.round(w[3],3).tolist()}, speed={w[4]}%")
        if not a.execute:
            print("DRY RUN - ROBOT DID NOT MOVE"); return
        if not n.client.wait_for_service(timeout_sec=3):raise RuntimeError("remote command service unavailable")
        n.command(f"SetSpeed({a.speed_percent})")
        for i,(x,y,z,orientation,speed,name) in enumerate(waypoints,1):
            cmd=f"MoveCart({x:.3f},{y:.3f},{z:.3f},{orientation[0]:.3f},{orientation[1]:.3f},{orientation[2]:.3f},{a.tool_id},{a.user_id},{speed},{speed},{speed},-1,-1)"
            print(f"Sending stage {i}/{len(waypoints)} ({name}): {cmd}"); n.command(cmd)
        print("Object safe approach completed; no descent to surface and no gripper actuation")
    finally:
        n.destroy_node()
        if rclpy.ok():rclpy.shutdown()

if __name__=="__main__":main()
