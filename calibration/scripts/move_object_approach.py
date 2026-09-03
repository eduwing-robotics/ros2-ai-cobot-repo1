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


def symmetric_angle_delta_deg(target_deg, current_deg, branch="shortest"):
    """Rotate onto an unoriented axis, optionally selecting its +/-180° branch."""
    delta = (target_deg - current_deg + 90.0) % 180.0 - 90.0
    if branch == "shortest":
        return delta
    if branch == "positive":
        return delta if delta > 0.0 else delta + 180.0
    if branch == "negative":
        return delta if delta < 0.0 else delta - 180.0
    raise ValueError(f"unknown symmetric rotation branch: {branch}")


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

    def refresh_state(self, timeout=3.0):
        self.state = None
        self.wait_state(timeout)
        return self.state

    def wait_motion_done(self, target_pose, target_joints, tool_id, timeout=90.0, tolerance_mm=1.0):
        deadline=time.monotonic()+timeout
        target=np.asarray(target_pose[:3],dtype=float)
        target_rotation=Rotation.from_euler("xyz",target_pose[3:],degrees=True)
        while rclpy.ok() and time.monotonic()<deadline:
            state=self.refresh_state(timeout=min(3.0,max(0.1,deadline-time.monotonic())))
            assert_safe_state(state,tool_id,require_auto=True,require_stationary=False)
            current=np.asarray([state.cart_x_cur_pos,state.cart_y_cur_pos,state.cart_z_cur_pos],dtype=float)
            rotation=Rotation.from_euler("xyz",[state.cart_a_cur_pos,state.cart_b_cur_pos,state.cart_c_cur_pos],degrees=True)
            angle_error=math.degrees((rotation.inv()*target_rotation).magnitude())
            joints=np.asarray([state.j1_cur_pos,state.j2_cur_pos,state.j3_cur_pos,state.j4_cur_pos,state.j5_cur_pos,state.j6_cur_pos],dtype=float)
            joint_error=float(np.max(np.abs(joints-target_joints)))
            if (int(state.robot_motion_done)==1
                    and float(np.linalg.norm(current-target))<=tolerance_mm
                    and angle_error<=1.0 and joint_error<=1.0):
                return state
        raise RuntimeError("robot motion pose/joint verification timeout")

    def request(self, text):
        if not self.client.wait_for_service(timeout_sec=3):
            raise RuntimeError("remote command service unavailable")
        req=RemoteCmdInterface.Request(); req.cmd_str=text
        future=self.client.call_async(req); rclpy.spin_until_future_complete(self,future)
        if future.result() is None:
            raise RuntimeError(f"no response for FAIRINO command: {text}")
        return str(future.result().cmd_res)

    def command(self, text):
        result=self.request(text)
        if result!="0":raise RuntimeError(f"FR5 rejected command: {text}, result={result}")


def assert_safe_state(state, tool_id, require_auto=False, require_stationary=True):
    if int(state.tool_num) != tool_id:
        raise RuntimeError(f"active tool={state.tool_num}, expected {tool_id}")
    if require_auto and int(state.robot_mode) != 0:
        raise RuntimeError(f"robot_mode={state.robot_mode}; AUTO mode 0 required")
    checks = {
        "emergency stop": state.emg,
        "abnormal stop": state.abnormal_stop,
        "main error": state.main_error_code,
        "sub error": state.sub_error_code,
        "collision": state.collision_err,
        "general alarm": state.alarm,
        "safety door": state.safetydoor_alarm,
        "safety plane": state.safetyplanealarm,
        "motion alarm": state.motionalarm,
        "interference zone": state.interferealarm,
        "soft-limit error": state.out_sflimit_err,
        "strange-pose flag": state.strangeposflag,
        "control-box error": state.ctrlboxerror,
        "command-point error": state.cmdpointerror,
        "parameter error": state.paraerror,
    }
    active = [f"{name}={value}" for name, value in checks.items() if float(value) != 0.0]
    if active:
        raise RuntimeError("robot safety state is not clear: " + ", ".join(active))
    if require_stationary and int(state.robot_motion_done) != 1:
        raise RuntimeError("robot is not stationary")


def parse_response(text, expected_values, label):
    try:
        values=[float(item) for item in text.split(",")]
    except ValueError as exc:
        raise RuntimeError(f"invalid {label} response: {text}") from exc
    if len(values) != expected_values + 1 or int(values[0]) != 0:
        raise RuntimeError(f"{label} query failed: {text}")
    return np.asarray(values[1:], dtype=float)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--x",type=float); p.add_argument("--y",type=float); p.add_argument("--z",type=float)
    p.add_argument("--target-file",type=Path)
    p.add_argument("--align-part",action="store_true",help="align the gripper axis with the detected part long axis")
    p.add_argument("--gripper-axis",choices=("tool_x","tool_y"),default="tool_x")
    p.add_argument(
        "--symmetric-rotation-branch",
        choices=("shortest", "positive", "negative"),
        default="shortest",
        help="select the directed +/-180-degree-equivalent gripper branch",
    )
    p.add_argument("--max-rotation-deg",type=float,default=90.0)
    p.add_argument("--tool-correction-x-mm",type=float,default=-2.05)
    p.add_argument("--tool-correction-y-mm",type=float,default=-2.55)
    p.add_argument("--base-correction-x-mm",type=float,default=0.0)
    p.add_argument("--base-correction-y-mm",type=float,default=0.0)
    p.add_argument("--center-correction",action=argparse.BooleanOptionalAction,default=True)
    p.add_argument("--approach-offset-mm",type=float,default=100.0)
    p.add_argument("--max-target-age-sec",type=float,default=120.0)
    p.add_argument("--speed-percent",type=int,default=50)
    p.add_argument("--descent-speed-percent",type=int,default=50)
    p.add_argument("--rotation-speed-percent",type=int,default=50)
    p.add_argument("--safe-clearance-mm",type=float,default=100); p.add_argument("--max-distance-mm",type=float,default=450)
    p.add_argument("--safe-z-mm",type=float,help="explicit Base-Z travel height; must be at or above current and target Z")
    p.add_argument("--joint-limit-margin-deg",type=float,default=10.0)
    p.add_argument("--max-joint-step-deg",type=float,default=90.0)
    p.add_argument("--min-horizontal-move-mm",type=float,default=1.0,
                   help="minimum XY delta that creates a horizontal waypoint")
    p.add_argument("--workspace-x-min",type=float); p.add_argument("--workspace-x-max",type=float)
    p.add_argument("--workspace-y-min",type=float); p.add_argument("--workspace-y-max",type=float)
    p.add_argument("--workspace-z-min",type=float); p.add_argument("--workspace-z-max",type=float)
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
        if a.approach_offset_mm < 20.0:
            p.error(
                "camera-derived targets must stop at least 20 mm above the detected surface; "
                "verify the hover pose, then use a separate direct-XYZ command for final vertical descent"
            )
        a.x=float(center[0]); a.y=float(center[1]); a.z=float(center[2]+a.approach_offset_mm)
    if a.execute != a.confirm_move:p.error("실제 이동에는 --execute와 --confirm-move가 모두 필요합니다")
    if a.dry_run and a.execute:p.error("--dry-run and --execute cannot be combined")
    if not 1<=a.speed_percent<=50:p.error("--speed-percent must be between 1 and 50")
    if not 1<=a.descent_speed_percent<=50:p.error("--descent-speed-percent must be between 1 and 50")
    if not 1<=a.rotation_speed_percent<=50:p.error("--rotation-speed-percent must be between 1 and 50")
    if not 0<a.max_rotation_deg<=180:p.error("--max-rotation-deg must be in (0, 180]")
    if a.safe_z_mm is None and a.safe_clearance_mm<50:p.error("--safe-clearance-mm must be >= 50")
    if not 0<a.joint_limit_margin_deg<45:p.error("--joint-limit-margin-deg must be in (0, 45)")
    if not 0<a.max_joint_step_deg<=180:p.error("--max-joint-step-deg must be in (0, 180]")
    if not 0<a.min_horizontal_move_mm<=1.0:p.error("--min-horizontal-move-mm must be in (0, 1]")
    workspace_limits = (
        (a.workspace_x_min, a.workspace_x_max, "X"),
        (a.workspace_y_min, a.workspace_y_max, "Y"),
        (a.workspace_z_min, a.workspace_z_max, "Z"),
    )
    for low, high, axis in workspace_limits:
        if (low is None) != (high is None):p.error(f"workspace {axis} requires both min and max")
        if low is not None and low >= high:p.error(f"workspace {axis} min must be less than max")
    rclpy.init(); n=Mover()
    try:
        n.wait_state(); s=n.state
        assert_safe_state(s,a.tool_id,require_auto=a.execute)
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
            rotation_delta=symmetric_angle_delta_deg(
                part_base_angle,
                current_axis_angle,
                a.symmetric_rotation_branch,
            )
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
        correction_base_fixed=np.asarray([
            a.base_correction_x_mm,
            a.base_correction_y_mm,
            0.0,
        ]) if a.center_correction and a.target_file is not None else np.zeros(3)
        correction_base=target_rotation@correction_tool+correction_base_fixed
        a.x+=float(correction_base[0]); a.y+=float(correction_base[1]); a.z+=float(correction_base[2])
        values=np.array([a.x,a.y,a.z],float)
        if not np.all(np.isfinite(values)):raise RuntimeError("target contains NaN/Inf")
        distance=float(np.linalg.norm(values-current))
        if distance>a.max_distance_mm:raise RuntimeError(f"target distance {distance:.1f} mm exceeds limit {a.max_distance_mm:.1f}")
        if a.safe_z_mm is None:
            safe_z=max(float(current[2]),a.z+a.safe_clearance_mm)
        else:
            safe_z=float(a.safe_z_mm)
            if not math.isfinite(safe_z) or safe_z+1e-6<max(float(current[2]),a.z):
                raise RuntimeError("--safe-z-mm must be finite and at or above current and target Z")
        waypoints=[]
        if safe_z-current[2]>1:waypoints.append((current[0],current[1],safe_z,abc,a.descent_speed_percent,"vertical raise"))
        if abs(rotation_delta)>0.5:waypoints.append((current[0],current[1],safe_z,target_abc,a.rotation_speed_percent,"part orientation alignment"))
        horizontal_delta=math.hypot(a.x-current[0],a.y-current[1])
        if horizontal_delta>a.min_horizontal_move_mm:
            waypoints.append((a.x,a.y,safe_z,target_abc,a.speed_percent,"horizontal positioning"))
        if safe_z-a.z>1:waypoints.append((a.x,a.y,a.z,target_abc,a.descent_speed_percent,"vertical approach"))
        current_joints=np.asarray([s.j1_cur_pos,s.j2_cur_pos,s.j3_cur_pos,s.j4_cur_pos,s.j5_cur_pos,s.j6_cur_pos],float)
        soft=parse_response(n.request("GetJointSoftLimitDeg(1)"),12,"joint soft-limit")
        negative=soft[:6]; positive=soft[6:]
        if np.any(current_joints < negative) or np.any(current_joints > positive):
            raise RuntimeError("current joints are outside controller soft limits")
        safety_stop=parse_response(n.request("GetSafetyStopState()"),2,"safety-stop")
        if np.any(safety_stop != 0):raise RuntimeError(f"safety stop is active: SI0/SI1={safety_stop.astype(int).tolist()}")
        planned=[]; reference=current_joints.copy()
        for x,y,z,orientation,speed,name in waypoints:
            point=np.asarray([x,y,z],float)
            for value,(low,high,axis) in zip(point,workspace_limits):
                if low is not None and not low <= value <= high:
                    raise RuntimeError(f"{name}: Base {axis}={value:.1f} mm outside [{low:.1f}, {high:.1f}]")
            pose=[x,y,z,*orientation]
            request="GetInverseKinRef("+",".join(f"{v:.6f}" for v in [0,*pose,*reference])+ ")"
            joints=parse_response(n.request(request),6,f"IK for {name}")
            margins=np.minimum(joints-negative,positive-joints)
            if np.any(margins < a.joint_limit_margin_deg):
                joint=int(np.argmin(margins))+1
                raise RuntimeError(f"{name}: J{joint} soft-limit margin {margins[joint-1]:.1f} deg is below {a.joint_limit_margin_deg:.1f} deg")
            delta=np.abs(joints-reference)
            if np.any(delta > a.max_joint_step_deg):
                joint=int(np.argmax(delta))+1
                raise RuntimeError(f"{name}: J{joint} step {delta[joint-1]:.1f} deg exceeds {a.max_joint_step_deg:.1f} deg")
            planned.append((*pose,speed,name,joints,margins))
            reference=joints
        print("OBJECT APPROACH ONLY - no surface descent, no gripper command")
        print(f"Target TCP/Base [mm]: [{a.x:.3f}, {a.y:.3f}, {a.z:.3f}]")
        print(f"Center correction Tool [mm]: {np.round(correction_tool,3).tolist()}; "
              f"fixed Base [mm]: {np.round(correction_base_fixed,3).tolist()}; "
              f"total Base [mm]: {np.round(correction_base,3).tolist()}")
        if a.align_part:
            print(f"Part long axis/Base XY: {part_base_angle:.3f} deg")
            print(
                f"Gripper alignment: {a.gripper_axis}, "
                f"branch={a.symmetric_rotation_branch}, delta={rotation_delta:.3f} deg, "
                f"target ABC={np.round(target_abc,3).tolist()}"
            )
        else:
            print(f"Current orientation preserved: {np.round(abc,3).tolist()}; distance={distance:.1f} mm")
        print(f"Controller soft limits [deg]: negative={negative.tolist()}, positive={positive.tolist()}")
        for i,w in enumerate(planned,1):
            print(f"Stage {i}/{len(planned)} {w[7]}: [{w[0]:.3f}, {w[1]:.3f}, {w[2]:.3f}], ABC={np.round(w[3:6],3).tolist()}, speed={w[6]}%, joints={np.round(w[8],3).tolist()}, min_limit_margin={float(np.min(w[9])):.1f} deg")
        if not a.execute:
            print("DRY RUN - ROBOT DID NOT MOVE"); return
        n.command(f"SetSpeed({a.speed_percent})")
        for i,(x,y,z,rx,ry,rz,speed,name,joints,margins) in enumerate(planned,1):
            assert_safe_state(n.refresh_state(),a.tool_id,require_auto=True)
            safety_stop=parse_response(n.request("GetSafetyStopState()"),2,"safety-stop")
            if np.any(safety_stop != 0):raise RuntimeError(f"safety stop is active: SI0/SI1={safety_stop.astype(int).tolist()}")
            define="JNTPoint(1,"+",".join(f"{value:.6f}" for value in joints)+")"
            linear=name in ("vertical raise","vertical approach")
            motion="MoveL" if linear else "MoveJ"
            cmd=f"{motion}(JNT1,{speed},{a.tool_id},{a.user_id})"
            print(f"Sending stage {i}/{len(planned)} ({name}): {define}; {cmd}")
            n.command(define)
            n.command(cmd)
            n.wait_motion_done([x,y,z,rx,ry,rz],joints,a.tool_id)
        print("Object safe approach completed; no descent to surface and no gripper actuation")
    finally:
        n.destroy_node()
        if rclpy.ok():rclpy.shutdown()

if __name__=="__main__":main()
