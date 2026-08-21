#!/usr/bin/env python3
"""Find raised objects in saved tray ROIs. Read-only dry run."""
import argparse, hashlib, json, time
from collections import deque
from pathlib import Path
import cv2
import numpy as np
import rclpy
from fairino_msgs.msg import RobotNonrtState
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import CameraInfo, CompressedImage, Image

COLORS={'black_block':(0,0,255),'long_orange':(0,165,255),
        'marked_white':(0,255,255),'right_white_brown':(0,200,0),
        'gpu':(255,80,0),'hbm':(220,0,220)}

class Detector(Node):
 def __init__(self,a):
  super().__init__('tray_part_detector'); self.a=a
  self.layout=json.loads(a.layout.read_text());self.bins=self.layout['bins']
  self.specs=json.loads(a.specs.read_text())['parts']
  ref=Path(self.layout['reference_image'])
  if not ref.is_absolute():ref=a.layout.parents[2]/ref
  image=cv2.imread(str(ref))
  if image is None:raise RuntimeError(f'Cannot read tray reference: {ref}')
  self.rh,self.rw=image.shape[:2];self.scale=a.registration_scale
  self.sift=cv2.SIFT_create(nfeatures=1600,contrastThreshold=.025)
  self.matcher=cv2.BFMatcher(cv2.NORM_L2);mask=np.zeros((self.rh,self.rw),np.uint8);points=[]
  for item in self.bins:
   poly=self.ref_points(item);points.extend(poly.tolist())
   cv2.polylines(mask,[poly],True,255,a.feature_band_px)
  cv2.polylines(mask,[cv2.convexHull(np.array(points,np.int32))],True,255,a.feature_band_px)
  size=(round(self.rw*self.scale),round(self.rh*self.scale))
  gray=cv2.resize(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),size,interpolation=cv2.INTER_AREA)
  small_mask=cv2.resize(mask,size,interpolation=cv2.INTER_NEAREST)
  self.rkp,self.rdesc=self.sift.detectAndCompute(gray,small_mask)
  if self.rdesc is None or len(self.rkp)<a.min_matches:raise RuntimeError('Not enough reference features')
  self.registration_state=None
  self.history=deque(maxlen=a.history_frames);self.frame_index=0
  payload=json.loads(a.handeye_file.read_text(encoding='utf-8'))
  best=payload.get('best',payload)
  handeye=payload.get('camera_to_flange') or best['camera_to_flange']
  self.euler=best.get('euler_convention','xyz')
  self.T_flange_camera=np.eye(4)
  self.T_flange_camera[:3,:3]=np.asarray(handeye['rotation_matrix'],float)
  self.T_flange_camera[:3,3]=np.asarray(handeye['translation_m'],float)
  self.handeye_sha256=hashlib.sha256(a.handeye_file.read_bytes()).hexdigest()
  self.robot=None;self.robot_time=0.;self.pose_history=deque(maxlen=a.robot_stable_samples)
  self.robot_group=ReentrantCallbackGroup()
  self.previous_robot_pose=None
  self.homography_corners=deque(maxlen=a.homography_smoothing_frames)
  self.depth=self.info=None; self.ds=0; self.last=0.
  self.pub=self.create_publisher(CompressedImage,a.output_topic,qos_profile_sensor_data)
  self.create_subscription(Image,a.depth_topic,self.depth_cb,qos_profile_sensor_data)
  self.create_subscription(CameraInfo,a.info_topic,self.info_cb,qos_profile_sensor_data)
  self.create_subscription(CompressedImage,a.color_topic,self.color_cb,qos_profile_sensor_data)
  self.create_subscription(RobotNonrtState,a.robot_state_topic,self.robot_cb,10,
                           callback_group=self.robot_group)
  self.get_logger().info('Dry-run only: no robot command is sent.')
 @staticmethod
 def stamp(m): return m.header.stamp.sec*1000000000+m.header.stamp.nanosec
 def info_cb(self,m): self.info=m
 def robot_cb(self,m):
  now=time.monotonic()
  pose=np.array([m.flange_x_cur_pos,m.flange_y_cur_pos,m.flange_z_cur_pos,
   m.flange_a_cur_pos,m.flange_b_cur_pos,m.flange_c_cur_pos],float)
  if self.previous_robot_pose is not None and now-self.robot_time<self.a.robot_stream_gap_sec:
   delta=np.abs(pose-self.previous_robot_pose)
   if np.max(delta[:3])>self.a.max_robot_sample_jump_mm or np.max(delta[3:])>self.a.max_robot_sample_jump_deg:
    return
  self.robot=m;self.robot_time=now
  self.previous_robot_pose=pose;self.pose_history.append(pose)
 def depth_cb(self,m):
  if m.encoding not in ('16UC1','mono16'): return
  x=np.frombuffer(m.data,np.uint16).reshape(m.height,m.step//2)
  self.depth=x[:,:m.width].copy(); self.ds=self.stamp(m)
 def ref_points(self,item):
  return np.array([[round(x*self.rw),round(y*self.rh)]
                   for x,y in item['section_polygon_normalized']],np.int32)
 def register(self,image):
  gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
  gray=cv2.resize(gray,None,fx=self.scale,fy=self.scale,interpolation=cv2.INTER_AREA)
  kp,desc=self.sift.detectAndCompute(gray,None)
  if desc is None:return None,0,0
  pairs=self.matcher.knnMatch(self.rdesc,desc,k=2)
  good=[x for x,y in pairs if x.distance<self.a.ratio_test*y.distance]
  if len(good)<self.a.min_matches:return None,len(good),0
  src=np.float32([self.rkp[x.queryIdx].pt for x in good]).reshape(-1,1,2)
  dst=np.float32([kp[x.trainIdx].pt for x in good]).reshape(-1,1,2)
  small,inlier=cv2.findHomography(src,dst,cv2.RANSAC,self.a.ransac_px)
  count=int(inlier.sum()) if inlier is not None else 0
  if small is None or count<self.a.min_inliers:return None,len(good),count
  scale=np.diag([self.scale,self.scale,1.]);full=np.linalg.inv(scale)@small@scale
  corners=np.float32([[[0,0],[self.rw,0],[self.rw,self.rh],[0,self.rh]]])
  moved=cv2.perspectiveTransform(corners,full)[0]
  ratio=abs(cv2.contourArea(moved))/(self.rw*self.rh)
  if not self.a.min_scale_area<=ratio<=self.a.max_scale_area:return None,len(good),count
  self.homography_corners.append(moved)
  smooth=np.median(np.asarray(self.homography_corners),axis=0).astype(np.float32)
  source=corners[0].astype(np.float32)
  full=cv2.getPerspectiveTransform(source,smooth)
  return full,len(good),count
 def find(self,item,fx,fy,cx,cy,H):
  h,w=self.depth.shape
  ref=self.ref_points(item).astype(np.float32).reshape(-1,1,2)
  poly=np.rint(cv2.perspectiveTransform(ref,H)[:,0,:]).astype(np.int32)
  roi=np.zeros((h,w),np.uint8); cv2.fillPoly(roi,[poly],255)
  roi=cv2.erode(roi,np.ones((13,13),np.uint8))
  valid=(roi>0)&(self.depth>100)&(self.depth<2000); sample=self.depth[valid]
  if sample.size<500:return [],poly,0.
  floor=float(np.percentile(sample,82)); part=item['part_spec_id']
  size=self.specs[part]['nominal_size_mm']
  th=max(self.a.min_height_mm,min(self.a.max_height_threshold_mm,size['height']*.35))
  mask=(valid&((floor-self.depth.astype(float))>=th)).astype(np.uint8)*255
  mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
  mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))
  expected=max(20.,fx*size['x']/floor*fy*size['y']/floor); found=[]
  contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
  for contour in contours:
   area=cv2.contourArea(contour)
   if not expected*self.a.min_area_ratio<=area<=expected*self.a.max_area_ratio:continue
   (u,v),(x,y),angle=cv2.minAreaRect(contour)
   if min(x,y)<3:continue
   cm=np.zeros_like(roi);cv2.drawContours(cm,[contour],-1,255,-1)
   values=self.depth[(cm>0)&(self.depth>100)]
   if values.size<10:continue
   zmm=float(np.median(values));z=zmm/1000.;angle=angle if x>=y else angle+90
   angle=((angle+90)%180)-90
   found.append({'center_pixel':[round(u,2),round(v,2)],
    'bbox_size_px':[round(x,2),round(y,2)],'angle_deg':round(angle,2),
    'depth_m':round(z,6),'height_above_tray_mm':round(floor-zmm,3),
    'camera_xyz_m':[round((u-cx)*z/fx,6),round((v-cy)*z/fy,6),round(z,6)],
    'cad_area_match_score':round(float(np.exp(-abs(np.log(max(area,1)/expected)))),3),
    '_contour':contour})
  found.sort(key=lambda q:q['cad_area_match_score'],reverse=True)
  return found[:item['expected_count']],poly,floor
 def stabilize(self,H,fx,fy,cx,cy):
  clusters=[]
  radii={'long_orange':60.,'gpu':45.,'hbm':45.,'black_block':40.,
         'marked_white':26.,'right_white_brown':18.}
  for frame_id,items in self.history:
   for d in items:
    if self.robot is not None and '_flange_pose' in d:
     current=np.array([self.robot.flange_x_cur_pos,self.robot.flange_y_cur_pos,
      self.robot.flange_z_cur_pos,self.robot.flange_a_cur_pos,
      self.robot.flange_b_cur_pos,self.robot.flange_c_cur_pos],float)
     source=np.asarray(d['_flange_pose'],float);delta=np.abs(current-source)
     if np.max(delta[:3])>self.a.history_pose_match_mm or np.max(delta[3:])>self.a.history_pose_match_deg:
      continue
    radius=radii.get(d['part_type'],self.a.track_radius_px)
    point=np.array(d['reference_center_pixel'],float);best=None;distance=1e9
    for cluster in clusters:
     center=np.median(np.array(cluster['points']),axis=0)
     value=float(np.linalg.norm(point-center))
     if value<distance:best,distance=cluster,value
    if best is None or distance>radius:
     best={'part_type':d['part_type'],'display_name':d['display_name'],
           'points':[],'cameras':[],'angles':[],'frames':set(),'scores':[]};clusters.append(best)
    if best['part_type']!=d['part_type']:
     same=[x for x in clusters if x['part_type']==d['part_type']]
     best=None;distance=1e9
     for cluster in same:
      value=float(np.linalg.norm(point-np.median(np.array(cluster['points']),axis=0)))
      if value<distance:best,distance=cluster,value
     if best is None or distance>radius:
      best={'part_type':d['part_type'],'display_name':d['display_name'],
            'points':[],'cameras':[],'angles':[],'frames':set(),'scores':[]};clusters.append(best)
    best['points'].append(point);best['cameras'].append(d['camera_xyz_m'])
    best['angles'].append(d['angle_deg'])
    best['frames'].add(frame_id);best['scores'].append(d['cad_area_match_score'])
  stable=[]
  for cluster in clusters:
   hits=len(cluster['frames'])
   if hits<self.a.min_stable_hits:continue
   ref=np.median(np.array(cluster['points']),axis=0).astype(np.float32).reshape(1,1,2)
   u,v=cv2.perspectiveTransform(ref,H)[0,0];ui,vi=round(float(u)),round(float(v))
   h,w=self.depth.shape
   if not (2<=ui<w-2 and 2<=vi<h-2):continue
   camera=np.median(np.asarray(cluster['cameras'],float),axis=0);z=float(camera[2])
   radians=np.deg2rad(np.array(cluster['angles'])*2.)
   angle=np.rad2deg(np.arctan2(np.median(np.sin(radians)),
                               np.median(np.cos(radians))))/2.
   stable.append({'part_type':cluster['part_type'],
    'display_name':cluster['display_name'],
    'center_pixel':[round(float(u),2),round(float(v),2)],
    'reference_center_pixel':[round(float(ref[0,0,0]),2),round(float(ref[0,0,1]),2)],
    'angle_deg':round(float(angle),2),'depth_m':round(z,6),
    'camera_xyz_m':np.round(camera,6).tolist(),
    'observation_frames':hits,
    'median_cad_area_match_score':round(float(np.median(cluster['scores'])),3)})
  limits={item['part_spec_id']:item['expected_count'] for item in self.bins}
  selected=[]
  for part in limits:
   group=[d for d in stable if d['part_type']==part]
   group.sort(key=lambda d:(d['observation_frames'],
                            d['median_cad_area_match_score']),reverse=True)
   selected.extend(group[:limits[part]])
  stable=selected
  stable.sort(key=lambda d:(d['part_type'],d['reference_center_pixel'][1],
                            d['reference_center_pixel'][0]))
  counts={}
  for d in stable:
   counts[d['part_type']]=counts.get(d['part_type'],0)+1
   d['instance_index']=counts[d['part_type']]
  return stable
 def add_base_coordinates(self,result):
  if self.robot is None or time.monotonic()-self.robot_time>self.a.max_robot_state_age_sec:
   return 'NO_FRESH_ROBOT_STATE'
  if len(self.pose_history)<self.a.robot_stable_samples:return 'ROBOT_STABILITY_PENDING'
  poses=np.asarray(self.pose_history)
  translation_span=float(np.max(np.ptp(poses[:,:3],axis=0)))
  rotation_span=float(np.max(np.ptp(poses[:,3:],axis=0)))
  result['robot_pose_span_mm']=round(translation_span,4)
  result['robot_rotation_span_deg']=round(rotation_span,5)
  if translation_span>self.a.max_robot_translation_span_mm or rotation_span>self.a.max_robot_rotation_span_deg:
   return 'ROBOT_MOVING'
  state=self.robot;T=np.eye(4)
  T[:3,:3]=Rotation.from_euler(self.euler,[state.flange_a_cur_pos,
   state.flange_b_cur_pos,state.flange_c_cur_pos],degrees=True).as_matrix()
  T[:3,3]=np.array([state.flange_x_cur_pos,state.flange_y_cur_pos,
                    state.flange_z_cur_pos],float)/1000.
  T_base_camera=T@self.T_flange_camera
  for detection in result['stable_detections']:
   point=np.r_[np.asarray(detection['camera_xyz_m'],float),1.]
   detection['base_xyz_mm']=np.round((T_base_camera@point)[:3]*1000.,3).tolist()
  result['transform_chain']='p_base=T_base_flange@T_flange_camera@p_camera'
  result['euler_convention']=self.euler
  result['flange_pose_mm_deg']=np.round(poses[-1],5).tolist()
  result['T_base_flange']=np.round(T,10).tolist()
  result['T_flange_camera']=np.round(self.T_flange_camera,10).tolist()
  result['handeye_file']=str(self.a.handeye_file)
  result['handeye_sha256']=self.handeye_sha256
  return 'VALID_COORDINATES_ONLY'
 def color_cb(self,m):
  now=time.monotonic()
  if now-self.last<1/self.a.process_hz or self.depth is None or self.info is None:return
  if abs(self.stamp(m)-self.ds)>self.a.max_sync_ms*1000000:return
  image=cv2.imdecode(np.frombuffer(m.data,np.uint8),cv2.IMREAD_COLOR)
  if image is None or image.shape[:2]!=self.depth.shape:return
  self.last=now;H,matches,inliers=self.register(image)
  fx,fy,cx,cy=self.info.k[0],self.info.k[4],self.info.k[2],self.info.k[5]
  state='TRACKING' if H is not None else 'NOT_REGISTERED'
  if state!=self.registration_state:
   self.get_logger().info(f'Tray state={state}, matches={matches}, inliers={inliers}')
   self.registration_state=state
  result={'schema_version':1,'mode':'tray_detection_dry_run',
          'timestamp_ros_ns':self.stamp(m),'tray_registration':state,
          'registration_matches':matches,'registration_inliers':inliers,'detections':[]}
  if H is None:
   cv2.putText(image,'TRAY NOT REGISTERED - DETECTIONS DISABLED',(35,55),
               cv2.FONT_HERSHEY_SIMPLEX,.85,(0,0,255),3,cv2.LINE_AA)
  else:
   cv2.putText(image,f'TRAY TRACKING - DETECTION ENABLED inliers={inliers}',(35,55),
               cv2.FONT_HERSHEY_SIMPLEX,.72,(0,220,0),3,cv2.LINE_AA)
  if H is not None:
   inverse=np.linalg.inv(H)
   for item in self.bins:
    found,poly,floor=self.find(item,fx,fy,cx,cy,H);part=item['part_spec_id'];color=COLORS[part]
    cv2.polylines(image,[poly],True,color,3)
    for n,d in enumerate(found,1):
     contour=d.pop('_contour');cv2.drawContours(image,[contour],-1,color,3)
     u,v=map(int,d['center_pixel']);cv2.drawMarker(image,(u,v),color,cv2.MARKER_CROSS,22,3)
     cv2.putText(image,f'{part} {n} {d["angle_deg"]:.0f}deg',(u+8,v-8),
                 cv2.FONT_HERSHEY_SIMPLEX,.48,color,2)
     d.update(part_type=part,display_name=item['display_name'],instance_index=n)
     point=np.float32([[d['center_pixel']]])
     ref=cv2.perspectiveTransform(point,inverse)[0,0]
     d['reference_center_pixel']=[round(float(ref[0]),2),round(float(ref[1]),2)]
     result['detections'].append(d)
    cv2.putText(image,f'{part}: {len(found)}/{item["expected_count"]} floor={floor:.1f}mm',
                tuple(poly[0]+[8,24]),cv2.FONT_HERSHEY_SIMPLEX,.48,color,2)
  self.frame_index+=1
  history_items=[dict(d) for d in result['detections']]
  if self.robot is not None:
   pose=[self.robot.flange_x_cur_pos,self.robot.flange_y_cur_pos,
    self.robot.flange_z_cur_pos,self.robot.flange_a_cur_pos,
    self.robot.flange_b_cur_pos,self.robot.flange_c_cur_pos]
   for item in history_items:item['_flange_pose']=pose
  self.history.append((self.frame_index,history_items))
  result['stable_detections']=self.stabilize(H,fx,fy,cx,cy) if H is not None else []
  result['detected_total']=len(result['detections'])
  result['stable_detected_total']=len(result['stable_detections'])
  result['base_transform_status']=self.add_base_coordinates(result) if H is not None else 'TRAY_NOT_REGISTERED'
  result['robot_motion_authorized']=False
  for d in result['stable_detections']:
   u,v=map(int,d['center_pixel']);cv2.circle(image,(u,v),14,(255,255,255),2)
   cv2.putText(image,f'S{d["observation_frames"]}',(u+10,v+18),
               cv2.FONT_HERSHEY_SIMPLEX,.42,(255,255,255),2)
  self.a.output_json.parent.mkdir(parents=True,exist_ok=True)
  tmp=self.a.output_json.with_suffix('.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2));tmp.replace(self.a.output_json)
  ok,jpg=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,88])
  if ok:
   out=CompressedImage();out.header=m.header;out.format='jpeg';out.data=jpg.tobytes();self.pub.publish(out)

def main():
 root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser()
 p.add_argument('--layout',type=Path,default=root/'config/tray_layout_candidate.json')
 p.add_argument('--specs',type=Path,default=root/'config/part_specs_candidate.json')
 p.add_argument('--output-json',type=Path,default=root/'data/tray_detections_last.json')
 p.add_argument('--handeye-file',type=Path,default=root.parents[0]/'calibration/data/handeye_result.json')
 p.add_argument('--color-topic',default='/camera/camera/color/image_raw/compressed')
 p.add_argument('--depth-topic',default='/camera/camera/aligned_depth_to_color/image_raw')
 p.add_argument('--info-topic',default='/camera/camera/color/camera_info')
 p.add_argument('--output-topic',default='/vision/tray/detections_image/compressed')
 p.add_argument('--feature-band-px',type=int,default=70);p.add_argument('--registration-scale',type=float,default=.4)
 p.add_argument('--ratio-test',type=float,default=.72);p.add_argument('--min-matches',type=int,default=14)
 p.add_argument('--min-inliers',type=int,default=10);p.add_argument('--ransac-px',type=float,default=4.)
 p.add_argument('--min-scale-area',type=float,default=.18);p.add_argument('--max-scale-area',type=float,default=3.)
 p.add_argument('--process-hz',type=float,default=2.);p.add_argument('--max-sync-ms',type=float,default=120.)
 p.add_argument('--min-height-mm',type=float,default=.8);p.add_argument('--max-height-threshold-mm',type=float,default=3.5)
 p.add_argument('--min-area-ratio',type=float,default=.06);p.add_argument('--max-area-ratio',type=float,default=5.0)
 p.add_argument('--history-frames',type=int,default=40);p.add_argument('--min-stable-hits',type=int,default=4)
 p.add_argument('--track-radius-px',type=float,default=16.)
 p.add_argument('--robot-state-topic',default='/nonrt_state_data')
 p.add_argument('--robot-stable-samples',type=int,default=5)
 p.add_argument('--max-robot-state-age-sec',type=float,default=1.)
 p.add_argument('--robot-stream-gap-sec',type=float,default=.5)
 p.add_argument('--max-robot-sample-jump-mm',type=float,default=5.)
 p.add_argument('--max-robot-sample-jump-deg',type=float,default=1.)
 p.add_argument('--max-robot-translation-span-mm',type=float,default=.25)
 p.add_argument('--max-robot-rotation-span-deg',type=float,default=.05)
 p.add_argument('--history-pose-match-mm',type=float,default=.5)
 p.add_argument('--history-pose-match-deg',type=float,default=.1)
 p.add_argument('--homography-smoothing-frames',type=int,default=7)
 a=p.parse_args();rclpy.init();node=Detector(a);executor=MultiThreadedExecutor(num_threads=2)
 executor.add_node(node)
 try:executor.spin()
 except KeyboardInterrupt:pass
 finally:
  executor.shutdown()
  node.destroy_node()
  if rclpy.ok():rclpy.shutdown()
if __name__=='__main__':main()
