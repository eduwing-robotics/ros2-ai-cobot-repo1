#!/usr/bin/env python3
"""Capture a robust close-view SMD target. Read-only: never commands the robot."""
import argparse, hashlib, json, math, sys, time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from fairino_msgs.msg import RobotNonrtState
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import CameraInfo, CompressedImage, Image
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smd_set_selection import select_smd_set
from smd_grasp_center_audit import describe_center
from smd_terminal_axis import canonical_axis_angle_deg, terminal_axis_from_source_obb, unwrap_axis_angles_deg


def unwrap(values):
    return unwrap_axis_angles_deg(values)

def canonical_axis_base_angle(center,angle,inv,fx,fy,Tbc):
    theta=math.radians(float(angle))
    c=np.asarray(center,float)
    canonical=np.float32([c,c+20*np.array([math.cos(theta),math.sin(theta)])]).reshape(-1,1,2)
    src=cv2.perspectiveTransform(canonical,inv)[:,0,:]; du,dv=src[1]-src[0]
    base_axis=Tbc[:3,:3]@np.array([du/fx,dv/fy,0.])
    raw_angle=math.degrees(math.atan2(base_axis[1],base_axis[0]))
    return canonical_axis_angle_deg(raw_angle)


class Capture(Node):
    def __init__(self, args):
        super().__init__('capture_smd_close_target'); self.a=args
        self.info=self.depth=self.robot=None; self.last_stamp=-1
        self.cfg=json.loads(args.config.read_text(encoding='utf-8'))
        obb_config=self.cfg['obb_detection']
        self.set_layout=self.cfg['set_layout']
        self.layout_capacity=int(self.set_layout['required_count'])
        self.required_count=int(self.set_layout['parts_per_set'])
        self.set_index=int(args.set_index)
        if int(obb_config['required_count'])!=self.layout_capacity:
            raise RuntimeError('OBB count and SMD layout capacity disagree')
        if self.required_count<1:
            raise RuntimeError('invalid SMD close-view count configuration')
        if not 0 <= args.consumed_prefix_count < self.required_count:
            raise RuntimeError('invalid operator-confirmed consumed prefix')
        self.target_instances=(list(range(args.consumed_prefix_count+1,self.required_count+1))
                               if args.all_instances else [args.instance])
        if any(index<1 or index>self.required_count for index in self.target_instances):
            raise RuntimeError('requested SMD instance is outside the selected set')
        if any(index<=args.consumed_prefix_count for index in self.target_instances):
            raise RuntimeError('requested SMD instance has already been consumed')
        self.samples={index:[] for index in self.target_instances}
        self.rectified_frames=[]; self.angle_contexts=[]
        self.model=YOLO(str(args.model)); self.width,self.height=map(int,self.cfg['canonical_size'])
        payload=json.loads(args.handeye.read_text(encoding='utf-8')); best=payload.get('best',payload)
        handeye=payload.get('camera_to_flange') or best['camera_to_flange']; self.euler=best.get('euler_convention','xyz')
        self.Tfc=np.eye(4); self.Tfc[:3,:3]=np.asarray(handeye['rotation_matrix'],float); self.Tfc[:3,3]=np.asarray(handeye['translation_m'],float)
        self.create_subscription(CameraInfo,args.info_topic,self.info_cb,qos_profile_sensor_data)
        self.create_subscription(Image,args.depth_topic,self.depth_cb,qos_profile_sensor_data)
        self.create_subscription(RobotNonrtState,args.robot_topic,self.robot_cb,10)
        if getattr(args, 'raw_color_topic', None):
            self.create_subscription(Image,args.raw_color_topic,self.raw_color_cb,qos_profile_sensor_data)
        else:
            self.create_subscription(CompressedImage,args.color_topic,self.color_cb,qos_profile_sensor_data)
    def raw_color_cb(self, m):
        # PNG is a lossless adapter to the existing compressed-image callback.
        # It preserves the source header and all detection/geometry gates.
        if m.encoding not in ('rgb8', 'bgr8') or m.step < m.width * 3:
            raise RuntimeError('expected RGB8/BGR8 raw color image')
        pixels=np.frombuffer(m.data,np.uint8).reshape(int(m.height),int(m.step))
        bgr=pixels[:,:int(m.width)*3].reshape(int(m.height),int(m.width),3)
        if m.encoding == 'rgb8': bgr=cv2.cvtColor(bgr,cv2.COLOR_RGB2BGR)
        ok,encoded=cv2.imencode('.png',bgr)
        if not ok: raise RuntimeError('lossless raw frame adapter failed')
        message=CompressedImage();message.header=m.header;message.format='png'
        message.data=encoded.tobytes()
        self.color_cb(message)

    def info_cb(self,m): self.info=m
    def depth_cb(self,m):
        dtype=np.dtype('>u2' if bool(m.is_bigendian) else '<u2')
        row=np.frombuffer(m.data,dtype=dtype).reshape(int(m.height),int(m.step)//2)
        self.depth=row[:,:int(m.width)].copy()
    def robot_cb(self,m): self.robot=m
    def complete(self):return all(len(samples)>=self.a.frames for samples in self.samples.values())

    def color_cb(self,m):
        if self.complete() or self.info is None or self.depth is None or self.robot is None:return
        stamp=int(m.header.stamp.sec)*1000000000+int(m.header.stamp.nanosec)
        if stamp==self.last_stamp:return
        s=self.robot
        if int(s.robot_motion_done)!=1:return
        errors=[getattr(s,n) for n in ('emg','abnormal_stop','main_error_code','sub_error_code','collision_err','alarm','safetydoor_alarm','safetyplanealarm','motionalarm','interferealarm','out_sflimit_err','strangeposflag','ctrlboxerror','cmdpointerror','paraerror')]
        if any(float(v)!=0 for v in errors):raise RuntimeError('robot safety state is not clear')
        image=cv2.imdecode(np.frombuffer(m.data,np.uint8),cv2.IMREAD_COLOR)
        if image is None or image.shape[:2]!=self.depth.shape[:2]:return
        reference=np.asarray(self.cfg['reference_tcp_base'],float)
        pose_now=np.array([s.cart_x_cur_pos,s.cart_y_cur_pos,s.cart_z_cur_pos,s.cart_a_cur_pos,s.cart_b_cur_pos,s.cart_c_cur_pos],float)
        if np.max(np.abs(pose_now[:3]-reference[:3]))>1.0 or np.max(np.abs((pose_now[3:]-reference[3:]+180.)%360.-180.))>0.2:
            raise RuntimeError(f'fixed SMD polygon requires reference TCP; current={pose_now.tolist()} reference={reference.tolist()}')
        source_size=np.asarray(self.cfg.get('source_image_size',[image.shape[1],image.shape[0]]),float)
        source_scale=np.array([image.shape[1]/source_size[0],image.shape[0]/source_size[1]],np.float32)
        section=np.asarray(self.cfg['section_polygon_pixel'],np.float32)*source_scale
        reg={'mode':'fixed_polygon_at_verified_reference_tcp','inliers':0}
        dst=np.float32([[0,0],[self.width-1,0],[self.width-1,self.height-1],[0,self.height-1]])
        H=cv2.getPerspectiveTransform(section.astype(np.float32),dst); inv=np.linalg.inv(H)
        rect=cv2.warpPerspective(image,H,(self.width,self.height),flags=cv2.INTER_CUBIC)
        pred=self.model.predict(rect,imgsz=self.a.image_size,conf=self.a.confidence,device='0',verbose=False)[0]
        count=0 if pred.obb is None else len(pred.obb)
        items=[]
        if pred.obb is not None:
            boxes=pred.obb.xyxyxyxy.cpu().numpy(); scores=pred.obb.conf.cpu().numpy()
            for box,score in zip(boxes,scores):items.append({'box':box,'center':box.mean(0),'confidence':float(score)})
        try:
            ordered=select_smd_set(items,self.set_layout,self.set_index,
                                  consumed_prefix_count=self.a.consumed_prefix_count)
        except RuntimeError as exc:
            self.get_logger().warning(f'rejected frame: total OBBs={count}; {exc}')
            return
        fx,fy,cx,cy=float(self.info.k[0]),float(self.info.k[4]),float(self.info.k[2]),float(self.info.k[5])
        pose=np.array([s.flange_x_cur_pos,s.flange_y_cur_pos,s.flange_z_cur_pos,s.flange_a_cur_pos,s.flange_b_cur_pos,s.flange_c_cur_pos],float)
        Tbf=np.eye(4);Tbf[:3,:3]=Rotation.from_euler(self.euler,pose[3:],degrees=True).as_matrix();Tbf[:3,3]=pose[:3]/1000.;Tbc=Tbf@self.Tfc
        resolved=[]
        try:
            for instance in self.target_instances:
                item=ordered[instance-1]
                if item is None:raise RuntimeError('requested SMD slot is empty')
                terminal=terminal_axis_from_source_obb(item['box'],inv,minimum_axis_ratio=self.a.min_axis_ratio)
                resolved.append((instance,item,terminal))
        except ValueError as exc:
            self.get_logger().warning(f'rejected frame: SMD-{instance:02d} trained OBB axis validation failed: {exc}')
            return
        for instance,item,terminal in resolved:
            c=item['center']; terminal_angle=float(terminal['angle_canonical_deg'])
            canonical=np.float32([c,c+[20.0,0.0]]).reshape(-1,1,2)
            src=cv2.perspectiveTransform(canonical,inv)[:,0,:]; u,v=src[0]
            camera_ray=np.array([(u-cx)/fx,(v-cy)/fy,1.0]); base_ray=Tbc[:3,:3]@camera_ray
            surface_z_m=-47.291/1000.0
            scale=(surface_z_m-Tbc[2,3])/base_ray[2]
            if not np.isfinite(scale) or scale<=0:raise RuntimeError('SMD surface-plane ray intersection is invalid')
            camera=camera_ray*scale; base=(Tbc[:3,3]+base_ray*scale)*1000.; z=float(camera[2])
            base_angle=canonical_axis_base_angle(c,terminal_angle,inv,fx,fy,Tbc)
            self.samples[instance].append({'center':c.tolist(),'angle':terminal_angle,'axis_ratio':terminal['axis_ratio'],'confidence':item['confidence'],'source':src[0].tolist(),'depth_m':z,'base':base.tolist(),'base_angle':base_angle,'pose':pose.tolist(),'inliers':reg['inliers'],'terminal_axis':terminal})
        self.rectified_frames.append(rect.copy())
        self.angle_contexts.append({'inv':inv.copy(),'fx':fx,'fy':fy,'Tbc':Tbc.copy()})
        self.last_stamp=stamp
        accepted=min(len(samples) for samples in self.samples.values())
        self.get_logger().info(f'accepted all targets {accepted}/{self.a.frames}')


def summarize_samples(instance,samples,frames,config,rectified_frames,angle_contexts):
    if frames<24 or len(rectified_frames)!=frames or len(angle_contexts)!=frames:
        raise RuntimeError('SMD terminal-axis validation requires exactly captured frames and at least 24 frames')
    centers=np.asarray([s['center'] for s in samples]);per_frame_angles=unwrap([s['angle'] for s in samples])
    poses=np.asarray([s['pose'] for s in samples]);bases=np.asarray([s['base'] for s in samples])
    pose_angles=np.column_stack([unwrap(poses[:,i]) for i in range(3,6)])
    temporal=config['temporal_median_gate'];batch_count=int(temporal['batch_count'])
    if batch_count<3 or frames%batch_count!=0:
        raise RuntimeError('SMD frame count must split evenly into at least three temporal batches')
    batch_indices=np.split(np.arange(frames),batch_count)
    batch_angles=[];batch_base_angles=[];batch_details=[]
    for indices in batch_indices:
        center=np.median(centers[indices],axis=0)
        angle=float(np.median(unwrap([samples[int(i)]['angle'] for i in indices])))
        terminal_rows=[samples[int(i)]['terminal_axis'] for i in indices]
        terminal={'method':'trained_terminal_inclusive_obb_source_geometry_v1','axis_ratio_frame':'source_image',
                  'angle_canonical_deg':angle,
                  'endpoints_canonical_pixel':np.round(np.median(np.asarray([row['endpoints_canonical_pixel'] for row in terminal_rows],float),axis=0),3).tolist(),
                  'axis_ratio_median':round(float(np.median([row['axis_ratio'] for row in terminal_rows])),4),
                  'axis_ratio_min':round(min(float(row['axis_ratio']) for row in terminal_rows),4)}
        mapped=[canonical_axis_base_angle(center,angle,angle_contexts[int(i)]['inv'],angle_contexts[int(i)]['fx'],angle_contexts[int(i)]['fy'],angle_contexts[int(i)]['Tbc']) for i in indices]
        base_angle=float(np.median(unwrap(mapped)))
        batch_angles.append(angle);batch_base_angles.append(base_angle)
        batch_details.append({'frame_indices':[int(i)+1 for i in indices],'angle_canonical_deg':round(angle,4),'angle_base_deg':round(base_angle,4),'terminal_axis':terminal})
    batch_angles=unwrap(batch_angles);batch_base_angles=unwrap(batch_base_angles)
    med=float(np.median(batch_angles));mad=float(np.median(np.abs(batch_angles-med)));batch_span=float(np.ptp(batch_angles))
    center_span=np.ptp(centers,axis=0);pose_t=float(np.max(np.ptp(poses[:,:3],axis=0)));pose_r=float(np.max(np.ptp(pose_angles,axis=0)))
    passed=(float(center_span.max())<=float(config['max_center_span_canonical_px'])
            and mad<=float(temporal['median_absolute_deviation_max_deg'])
            and batch_span<=float(temporal['max_batch_span_deg'])
            and pose_t<=.5 and pose_r<=.1)
    return {'part_type':'right_white_brown','instance_index':instance,
     'part_center_base_mm':np.round(np.median(bases,axis=0),3).tolist(),
     'long_axis_angle_base_deg':round(float(np.median(batch_base_angles)),3),
     'long_axis_angle_canonical_deg':round(med,3),'frame_count':frames,
     'confidence_median':round(float(np.median([s['confidence'] for s in samples])),4),
     'center_span_canonical_px':np.round(center_span,3).tolist(),
     'axis_ratio_median':round(float(np.median([s['axis_ratio'] for s in samples])),4),
     'axis_ratio_min':round(min(float(s['axis_ratio']) for s in samples),4),
     'angle_mad_deg':round(mad,4),'angle_batch_span_deg':round(batch_span,4),
     'temporal_batch_count':batch_count,'frames_per_temporal_batch':frames//batch_count,
     'per_frame_angle_mad_diagnostic_deg':round(float(np.median(np.abs(per_frame_angles-np.median(per_frame_angles)))),4),
     'base_xyz_span_mm':np.round(np.ptp(bases,axis=0),3).tolist(),
     'robot_pose_translation_span_mm':round(pose_t,4),
     'robot_pose_rotation_span_deg':round(pose_r,5),
     'validation_passed':bool(passed),'axis_ratio_frame':'source_image','angle_source':'trained terminal-inclusive OBB pilot_06 mapped through three temporal frame batches',
     'temporal_batches':batch_details,'samples':samples}


def main():
    root=Path(__file__).resolve().parents[1]; p=argparse.ArgumentParser()
    p.add_argument('--instance',type=int,default=1);p.add_argument('--all-instances',action='store_true')
    p.add_argument('--set-index',type=int,choices=(1,2),default=1)
    p.add_argument('--consumed-prefix-count',type=int,default=0,
                   help='operator-confirmed empty leading slots; remaining parts must stay in their original order')
    p.add_argument('--frames',type=int,default=24)
    p.add_argument('--config',type=Path,default=root/'config/smd_section_view.json');p.add_argument('--model',type=Path,default=root/'models/smd_obb/pilot_06/weights/best.pt')
    p.add_argument('--handeye',type=Path,default=root.parent/'calibration/data/handeye_result.json');p.add_argument('--output',type=Path,default=root/'data/smd_close_targets_current.json')
    p.add_argument('--color-topic',default='/camera/camera/color/image_raw/compressed');p.add_argument('--depth-topic',default='/camera/camera/aligned_depth_to_color/image_raw');p.add_argument('--info-topic',default='/camera/camera/color/camera_info');p.add_argument('--robot-topic',default='/nonrt_state_data')
    p.add_argument('--raw-color-topic', help='Use lossless raw RGB/BGR instead of JPEG; same detection gates')
    p.add_argument('--confidence',type=float,default=.5);p.add_argument('--image-size',type=int,default=960);p.add_argument('--timeout',type=float,default=45.)
    p.add_argument('--min-axis-ratio',type=float,default=1.35)
    a=p.parse_args()
    if a.frames<24 or a.frames%3!=0:p.error('--frames must be at least 24 and divisible by 3')
    rclpy.init();n=Capture(a);deadline=time.monotonic()+a.timeout
    try:
        while rclpy.ok() and not n.complete() and time.monotonic()<deadline:rclpy.spin_once(n,timeout_sec=.1)
        if not n.complete():
            progress={index:len(samples) for index,samples in n.samples.items()}
            print(f'incomplete valid frames: {progress}, required={a.frames}', flush=True)
            raise SystemExit(3)  # Retryable observation timeout; no target output.
        parts=[summarize_samples(index,n.samples[index],a.frames,n.cfg['obb_detection'],n.rectified_frames,n.angle_contexts)
               for index in n.target_instances]
        for part in parts:
            part['set_index']=n.set_index
            part['physical_instance_index']=(n.set_index-1)*n.required_count+int(part['instance_index'])
        recipes_path=root/'config/part_gripper_recipes.json'
        recipe=json.loads(recipes_path.read_text())['parts']['right_white_brown']
        correction=recipe['grasp_center_correction_base_mm']
        for part in parts:
            part['fixed_base_correction_mm']=[float(correction['x']),float(correction['y']),0.0]
            part['center_correction_applied']=False
            part['grasp_center_diagnostic']=describe_center(recipe,part['part_center_base_mm'][:2])
        payload={'schema_version':2,
         'mode':('smd_close_multiframe_base_targets' if a.all_instances
                 else 'smd_close_multiframe_base_target'),
         'timestamp_unix':time.time(),'robot_motion_authorized':False,
         'set_index':n.set_index,'required_count':n.required_count,
         'layout_capacity':n.layout_capacity,
         'operator_confirmed_consumed_prefix_count':a.consumed_prefix_count,
         'validation_passed':all(part['validation_passed'] for part in parts),
         'handeye_sha256':hashlib.sha256(a.handeye.read_bytes()).hexdigest(),
         'model_sha256':hashlib.sha256(a.model.read_bytes()).hexdigest(),
         'axis_geometry_version':'source_image_v1',
         'parts':parts}
        if not a.all_instances:payload.update(parts[0])
        a.output.write_text(json.dumps(payload,indent=2),encoding='utf-8');print(json.dumps(payload,indent=2))
        if not payload['validation_passed']:raise SystemExit(2)
    finally:n.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
