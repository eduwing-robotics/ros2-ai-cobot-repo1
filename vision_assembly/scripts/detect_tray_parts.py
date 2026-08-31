#!/usr/bin/env python3
"""Find raised objects in saved tray ROIs. Read-only dry run."""
import argparse, hashlib, json, threading, time, traceback
from collections import deque
from pathlib import Path
import cv2
import numpy as np
import rclpy
from fairino_msgs.msg import RobotNonrtState
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import CameraInfo, CompressedImage, Image
from std_msgs.msg import String

COLORS={'black_block':(0,0,255),'long_orange':(0,165,255),
        'marked_white':(0,255,255),'right_white_brown':(0,200,0),
        'gpu':(255,80,0),'hbm':(220,0,220)}

def wrapped_angle_delta(current,reference):
 return np.abs((np.asarray(current,float)-np.asarray(reference,float)+180.)%360.-180.)

def wrapped_angle_span(samples):
 angles=np.asarray(samples,float);reference=angles[0]
 unwrapped=reference+(angles-reference+180.)%360.-180.
 return np.ptp(unwrapped,axis=0)

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
  self.inductor_background=None
  self.seg_model=None
  self.seg_class_ids={'black_block':0,'marked_white':1,'right_white_brown':2,
                      'long_orange':3,'gpu':4,'hbm':5}
  # Median single-instance mask areas measured from the 1,860 hand-checked labels.
  self.seg_single_areas={'black_block':1331.5,'marked_white':401.5,'right_white_brown':271.5,
                         'long_orange':5959.7,'gpu':13619.0,'hbm':1284.5}
  if a.seg_model is not None:
   from ultralytics import YOLO
   if not a.seg_model.is_file():raise FileNotFoundError(f'Segmentation model not found: {a.seg_model}')
   self.seg_model=YOLO(str(a.seg_model))
   self.get_logger().info(f'Learned tray segmentation: {a.seg_model}')
  if a.inductor_background.exists():
   background=cv2.imread(str(a.inductor_background))
   if background is not None and background.shape[:2]==(self.rh,self.rw):
    self.inductor_background=background
    self.get_logger().info(f'Inductor empty background: {a.inductor_background}')
   else:self.get_logger().warning('Ignored invalid inductor background image')
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
  self.count_history=deque(maxlen=a.count_smoothing_frames)
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
  # Drop overlapping GPU inference callbacks to prevent latency and CUDA memory growth.
  self.processing_lock=threading.Lock()
  self.display_lock=threading.Lock()
  self.snapshot_lock=threading.Lock()
  self.display_tracks={}
  self.display_counts={}
  self.last_display=0.
  self.processing_errors=0
  self.background_captured=False
  self.overlay_frame=0;self.overlay_tracks={};self.overlay_counts={}
  self.image_qos=QoSProfile(history=HistoryPolicy.KEEP_LAST,depth=1,
                            reliability=ReliabilityPolicy.BEST_EFFORT)
  self.shared_homography=None;self.shared_registration_stamp_ns=0;self.shared_registration_state='NONE'
  self.registration_generation=0
  self.pub=self.create_publisher(CompressedImage,a.output_topic,self.image_qos)
  self.counts_pub=self.create_publisher(String,a.counts_topic,10)
  self.overlay_state_pub=self.create_publisher(String,a.overlay_state_topic,10)
  self.unity_state_pub=self.create_publisher(String,a.unity_state_topic,10)
  self.create_subscription(Image,a.depth_topic,self.depth_cb,self.image_qos)
  self.create_subscription(CameraInfo,a.info_topic,self.info_cb,self.image_qos)
  self.create_subscription(CompressedImage,a.color_topic,self.color_cb,self.image_qos)
  self.create_subscription(String,a.registration_topic,self.registration_cb,10)
  self.create_subscription(RobotNonrtState,a.robot_state_topic,self.robot_cb,10,
                           callback_group=self.robot_group)
  self.get_logger().info('Dry-run only: no robot command is sent.')
 @staticmethod
 def stamp(m): return m.header.stamp.sec*1000000000+m.header.stamp.nanosec
 def info_cb(self,m): self.info=m
 def registration_cb(self,message):
  try:
   payload=json.loads(message.data)
   state=str(payload.get('state','NONE'))
   stamp_ns=int(payload['timestamp_ros_ns'])
   if state!='TRACKING':
    if self.shared_registration_state=='TRACKING':self.registration_generation+=1
    self.shared_homography=None;self.shared_registration_stamp_ns=stamp_ns
    self.shared_registration_state=state
    with self.snapshot_lock:
     self.display_tracks={};self.display_counts={}
    return
   H=np.asarray(payload['homography_reference_to_image'],float)
   if H.shape!=(3,3) or not np.all(np.isfinite(H)):return
   if self.shared_homography is not None and self.shared_registration_state=='TRACKING':
    corners=np.float32([[[0,0],[self.rw,0],[self.rw,self.rh],[0,self.rh]]])
    previous=cv2.perspectiveTransform(corners,self.shared_homography)[0]
    current=cv2.perspectiveTransform(corners,H)[0]
    jump=float(np.max(np.linalg.norm(current-previous,axis=1)))
    if jump>self.a.max_shared_homography_jump_px:
     self.registration_generation+=1
     with self.snapshot_lock:
      self.display_tracks={};self.display_counts={}
     self.get_logger().warning(
      f'Tray homography jumped {jump:.2f}px; cleared stale overlays')
   self.shared_homography=H;self.shared_registration_stamp_ns=stamp_ns
   self.shared_registration_state=state
  except (KeyError,ValueError,TypeError):
   self.get_logger().warning('Ignored invalid shared tray registration')
 def robot_cb(self,m):
  now=time.monotonic()
  pose=np.array([m.flange_x_cur_pos,m.flange_y_cur_pos,m.flange_z_cur_pos,
   m.flange_a_cur_pos,m.flange_b_cur_pos,m.flange_c_cur_pos],float)
  if self.previous_robot_pose is not None and now-self.robot_time<self.a.robot_stream_gap_sec:
   translation_delta=np.abs(pose[:3]-self.previous_robot_pose[:3])
   angle_delta=wrapped_angle_delta(pose[3:],self.previous_robot_pose[3:])
   if np.max(translation_delta)>self.a.max_robot_sample_jump_mm or np.max(angle_delta)>self.a.max_robot_sample_jump_deg:
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
 @staticmethod
 def split_connected_contour(contour,single_area,max_instances,ratio_threshold=1.55):
  """Split a touching component into spatially compact instance contours."""
  contour=np.asarray(contour)
  if contour.size<6 or not np.all(np.isfinite(contour)):return []
  contour=np.rint(contour).astype(np.int32).reshape(-1,1,2)
  area=float(cv2.contourArea(contour))
  if single_area<=0 or area<single_area*ratio_threshold:return [contour]
  count=int(np.clip(round(area/single_area),2,max_instances))
  x,y,w,h=cv2.boundingRect(contour)
  local=np.zeros((h,w),np.uint8)
  shifted=contour.copy();shifted[:,:,0]-=x;shifted[:,:,1]-=y
  cv2.drawContours(local,[shifted],-1,255,-1)
  yy,xx=np.where(local>0)
  if len(xx)<count*6:return [contour]
  samples=np.column_stack((xx,yy)).astype(np.float32)
  criteria=(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,50,.15)
  _,labels,_=cv2.kmeans(samples,count,None,criteria,5,cv2.KMEANS_PP_CENTERS)
  pieces=[]
  for index in range(count):
   piece=np.zeros_like(local);points=samples[labels.ravel()==index].astype(np.int32)
   if len(points)<6:continue
   piece[points[:,1],points[:,0]]=255
   pcs,_=cv2.findContours(piece,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
   if not pcs:continue
   pc=max(pcs,key=cv2.contourArea);pc[:,:,0]+=x;pc[:,:,1]+=y
   if cv2.contourArea(pc)>=single_area*.35:pieces.append(pc)
  return pieces if len(pieces)==count else [contour]
 def register(self,image):
  gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
  gray=cv2.resize(gray,None,fx=self.scale,fy=self.scale,interpolation=cv2.INTER_AREA)
  kp,desc=self.sift.detectAndCompute(gray,None)
  if desc is None:return None,0,0
  pairs=self.matcher.knnMatch(self.rdesc,desc,k=2)
  good=[pair[0] for pair in pairs if len(pair)==2 and
        pair[0].distance<self.a.ratio_test*pair[1].distance]
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
 def find(self,item,image,background_delta,depth_float,hue,saturation,value_channel,fx,fy,cx,cy,H):
  h,w=self.depth.shape
  ref=self.ref_points(item).astype(np.float32).reshape(-1,1,2)
  poly=np.rint(cv2.perspectiveTransform(ref,H)[:,0,:]).astype(np.int32)
  roi=np.zeros((h,w),np.uint8); cv2.fillPoly(roi,[poly],255)
  inset=35 if item['part_spec_id']=='marked_white' else 13
  roi=cv2.erode(roi,np.ones((inset,inset),np.uint8))
  color_roi=roi>0
  valid=color_roi&(self.depth>100)&(self.depth<2000); sample=self.depth[valid]
  if sample.size<500:return [],poly,0.
  floor=float(np.percentile(sample,82)); part=item['part_spec_id']
  size=self.specs[part]['nominal_size_mm']
  th=max(self.a.min_height_mm,min(self.a.max_height_threshold_mm,size['height']*.35))
  if part in ('black_block','hbm','gpu'):
   mask=(color_roi&(value_channel<self.a.vrm_max_value)).astype(np.uint8)*255
  elif part=='long_orange':
   mask=(color_roi&(hue>=self.a.orange_hue_min)&(hue<=self.a.orange_hue_max)&
         (saturation>=self.a.orange_saturation_min)&(value_channel>=self.a.orange_value_min)).astype(np.uint8)*255
  elif part=='right_white_brown':
   mask=(color_roi&(saturation>=self.a.smd_saturation_min)&
         (value_channel<=self.a.smd_value_max)).astype(np.uint8)*255
  elif part=='marked_white' and background_delta is not None:
   illumination_offset=float(np.median(background_delta[color_roi]))
   local_delta=np.abs(background_delta-illumination_offset)
   mask=(color_roi&(local_delta>=self.a.inductor_diff_threshold)).astype(np.uint8)*255
  else:
   mask=(valid&((floor-depth_float)>=th)).astype(np.uint8)*255
  if part=='right_white_brown':open_size,close_size=1,3
  elif part=='marked_white':open_size,close_size=3,11
  else:open_size,close_size=5,9
  mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(open_size,open_size)))
  mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(close_size,close_size)))
  expected=max(20.,fx*size['x']/floor*fy*size['y']/floor); found=[]
  contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
  if part=='marked_white':
   seed_mask=(color_roi&(value_channel<self.a.inductor_marker_max_value)).astype(np.uint8)*255
   seed_mask=cv2.morphologyEx(seed_mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
   seed_mask=cv2.morphologyEx(seed_mask,cv2.MORPH_CLOSE,np.ones((7,7),np.uint8))
   seed_contours,_=cv2.findContours(seed_mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
   seeds=[];synthetic=[]
   for seed in sorted(seed_contours,key=cv2.contourArea,reverse=True):
    seed_area=cv2.contourArea(seed)
    if not self.a.inductor_marker_min_area_px<=seed_area<=expected*.8:continue
    (su,sv),_,seed_angle=cv2.minAreaRect(seed)
    center=np.array([su,sv],float)
    if any(np.linalg.norm(center-old)<np.sqrt(expected)*1.05 for old in seeds):continue
    seeds.append(center)
    side=np.sqrt(expected*self.a.inductor_outline_area_scale)
    box=cv2.boxPoints(((su,sv),(side,side),seed_angle))
    synthetic.append(np.rint(box).astype(np.int32).reshape(-1,1,2))
   if synthetic:contours=synthetic
  if part not in ('marked_white','right_white_brown'):
   split=[]
   for contour in contours:
    split.extend(self.split_connected_contour(contour,expected,item['expected_count']))
   contours=split
  for contour in contours:
   area=cv2.contourArea(contour)
   if not expected*self.a.min_area_ratio<=area<=expected*self.a.max_area_ratio:continue
   (_, _),(x,y),angle=cv2.minAreaRect(contour)
   if min(x,y)<3:continue
   long_side=max(x,y);short_side=min(x,y)
   aspect=long_side/max(short_side,1e-6)
   expected_aspect=max(size['x'],size['y'])/max(min(size['x'],size['y']),1e-6)
   aspect_score=float(np.exp(-abs(np.log(aspect/expected_aspect))))
   rectangularity=float(area/max(x*y,1.))
   area_score=float(np.exp(-abs(np.log(max(area,1)/expected))))
   shape_score=float((area_score*aspect_score*max(0.,min(1.,rectangularity)))**(1/3))
   if part=='black_block' and (shape_score<self.a.vrm_min_shape_score or rectangularity<self.a.vrm_min_rectangularity):continue
   if part not in ('right_white_brown','marked_white') and (area_score<self.a.min_area_score or
      aspect_score<self.a.min_aspect_score or rectangularity<self.a.min_rectangularity):continue
   if part=='marked_white' and not (.05<=area/expected<=2.0 and rectangularity>=.2):continue
   moments=cv2.moments(contour)
   if abs(moments['m00'])<1e-6:continue
   u=float(moments['m10']/moments['m00']);v=float(moments['m01']/moments['m00'])
   cm=np.zeros_like(roi);cv2.drawContours(cm,[contour],-1,255,-1)
   values=self.depth[(cm>0)&(self.depth>100)]
   if values.size<10:
    expanded=cv2.dilate(cm,np.ones((9,9),np.uint8))
    values=self.depth[(expanded>0)&(self.depth>100)&(self.depth<2000)]
   if values.size<10:continue
   zmm=float(np.median(values));z=zmm/1000.;measured_height=floor-zmm
   if part=='right_white_brown' and measured_height>max(8.,size['height']*2.5):continue
   area_ratio=float(area/expected)
   instance_estimate=int(np.clip(round(area_ratio),1,4)) if part=='right_white_brown' else 1
   angle=angle if x>=y else angle+90
   angle=((angle+90)%180)-90
   found.append({'center_pixel':[round(u,2),round(v,2)],
    'bbox_size_px':[round(x,2),round(y,2)],'angle_deg':round(angle,2),
    'depth_m':round(z,6),'height_above_tray_mm':round(measured_height,3),
    'area_ratio':round(area_ratio,3),'instance_estimate':instance_estimate,
    'camera_xyz_m':[round((u-cx)*z/fx,6),round((v-cy)*z/fy,6),round(z,6)],
    'cad_area_match_score':round(area_score,3),
    'aspect_ratio':round(aspect,3),'aspect_match_score':round(aspect_score,3),
    'rectangularity':round(rectangularity,3),'shape_score':round(shape_score,3),
    '_contour':contour})
  found.sort(key=lambda q:q['cad_area_match_score'],reverse=True)
  return found[:item['expected_count']],poly,floor
 def find_segmented(self,item,canonical,image,depth_float,fx,fy,cx,cy,H,prediction=None):
  part=item['part_spec_id'];x1,y1,x2,y2=map(int,item['roi_px']);pad=self.a.seg_crop_padding
  x1=max(0,x1-pad);y1=max(0,y1-pad);x2=min(self.rw,x2+pad);y2=min(self.rh,y2+pad)
  crop=canonical[y1:y2,x1:x2]
  confidence=self.a.power_seg_confidence if part=='long_orange' else self.a.seg_confidence
  result=prediction if prediction is not None else self.seg_model.predict(crop,imgsz=self.a.seg_image_size,conf=confidence,
   device=self.a.seg_device,iou=self.a.seg_nms_iou,retina_masks=True,verbose=False)[0]
  candidates=[];class_id=self.seg_class_ids[part]
  if result.masks is not None and result.boxes is not None:
   for score,cls,points in zip(result.boxes.conf.cpu().tolist(),result.boxes.cls.cpu().tolist(),result.masks.xy):
    if int(cls)!=class_id or float(score)<confidence or len(points)<3:continue
    reference=np.asarray(points,np.float32)+np.array([x1,y1],np.float32)
    base_reference=np.rint(reference).astype(np.int32).reshape(-1,1,2)
    references=[base_reference]
    if part=='long_orange':
     (_, _),(mw,mh),_=cv2.minAreaRect(base_reference)
     mask_aspect=max(mw,mh)/max(1.,min(mw,mh))
     expected_size=self.specs[part]['nominal_size_mm']
     expected_aspect=max(expected_size['x'],expected_size['y'])/max(1e-6,min(expected_size['x'],expected_size['y']))
     # A squat mask spans multiple modules or overlaps a valid instance.
     # Reject it instead of drawing a false double outline or fabricated split.
     if mask_aspect<expected_aspect*.68:continue
    for reference in references:
     reference=reference.reshape(-1,2).astype(np.float32)
     moments=cv2.moments(reference)
     if abs(moments['m00'])<1e-6:continue
     center=np.array([moments['m10']/moments['m00'],moments['m01']/moments['m00']],float)
     candidates.append((float(score),center,reference))
  radius={'black_block':14.,'marked_white':12.,'right_white_brown':7.,
          'long_orange':30.,'gpu':35.,'hbm':12.}[part]
  def candidate_priority(candidate):
   score,_,polygon=candidate
   (_, _),(pw,ph),_=cv2.minAreaRect(polygon.astype(np.float32))
   aspect=max(pw,ph)/max(1.,min(pw,ph))
   expected_size=self.specs[part]['nominal_size_mm']
   expected_aspect=max(expected_size['x'],expected_size['y'])/max(1e-6,min(expected_size['x'],expected_size['y']))
   shape=float(np.exp(-abs(np.log(max(aspect,1e-6)/expected_aspect))))
   return (shape,score) if part=='long_orange' else (score,shape)
  def overlap_fraction(first,second):
   hull_a=cv2.convexHull(first.astype(np.float32))
   hull_b=cv2.convexHull(second.astype(np.float32))
   area_a=abs(float(cv2.contourArea(hull_a)));area_b=abs(float(cv2.contourArea(hull_b)))
   if min(area_a,area_b)<1.:return 0.
   intersection,_=cv2.intersectConvexConvex(hull_a,hull_b)
   return float(intersection/min(area_a,area_b))
  accepted=[]
  for score,center,reference in sorted(candidates,key=candidate_priority,reverse=True):
   if any(np.linalg.norm(center-old[1])<radius for old in accepted):continue
   # Suppress a merged/duplicate Power Module mask drawn over an already
   # selected instance. Merely touching instance masks have near-zero overlap.
   if part=='long_orange' and any(overlap_fraction(reference,old[2])>.35 for old in accepted):continue
   accepted.append((score,center,reference))
  found=[]
  for score,_,reference in accepted:
   # Preserve sub-pixel mask geometry for center/orientation estimation.
   # Rounding the transformed YOLO polygon before minAreaRect caused small
   # HBM masks to jump by roughly one degree as an edge crossed a pixel.
   contour_float=cv2.perspectiveTransform(
    reference.reshape(-1,1,2).astype(np.float32),H).astype(np.float32)
   contour=np.rint(contour_float).astype(np.int32)
   area=float(cv2.contourArea(contour_float));moments=cv2.moments(contour_float)
   if area<3 or abs(moments['m00'])<1e-6:continue
   u=float(moments['m10']/moments['m00']);v=float(moments['m01']/moments['m00'])
   (_, _),(bw,bh),angle=cv2.minAreaRect(contour_float)
   if bw<bh:angle+=90.
   angle=((angle+90.)%180.)-90.
   cm=np.zeros(image.shape[:2],np.uint8);cv2.drawContours(cm,[contour],-1,255,-1)
   # Reject mixed edge pixels where aligned depth can blend the package top
   # with the tray floor.  Keep the full mask as a fallback for tiny parts.
   depth_mask=cv2.erode(cm,np.ones((5,5),np.uint8)) if part in ('gpu','hbm') else cm
   values=self.depth[(depth_mask>0)&(self.depth>100)&(self.depth<2000)]
   if values.size<3:
    values=self.depth[(cv2.dilate(cm,np.ones((5,5),np.uint8))>0)&(self.depth>100)&(self.depth<2000)]
   if values.size<3:continue
   zmm=float(np.median(values));z=zmm/1000.
   found.append({'center_pixel':[round(u,2),round(v,2)],
    'bbox_size_px':[round(float(bw),2),round(float(bh),2)],'angle_deg':round(float(angle),2),
    'depth_m':round(z,6),'height_above_tray_mm':None,'area_ratio':None,'instance_estimate':1,
    'camera_xyz_m':[round((u-cx)*z/fx,6),round((v-cy)*z/fy,6),round(z,6)],
    'cad_area_match_score':round(score,4),'aspect_ratio':round(max(bw,bh)/max(1.,min(bw,bh)),3),
    'aspect_match_score':None,'rectangularity':round(area/max(1.,bw*bh),3),
    'shape_score':round(score,4),'segmentation_confidence':round(score,4),'detector':'yolo26_seg',
    '_contour':contour})
  poly=np.rint(cv2.perspectiveTransform(self.ref_points(item).astype(np.float32).reshape(-1,1,2),H)[:,0,:]).astype(np.int32)
  found.sort(key=lambda item:item['segmentation_confidence'],reverse=True)
  return found[:item['expected_count']],poly,0.
 def remember_overlay(self,part,contour,inverse):
  reference=cv2.perspectiveTransform(contour.astype(np.float32),inverse)
  moments=cv2.moments(reference)
  if abs(moments['m00'])<1e-6:return
  center=np.array([moments['m10']/moments['m00'],moments['m01']/moments['m00']],float)
  tracks=self.overlay_tracks.setdefault(part,[])
  radius={'right_white_brown':12.,'marked_white':20.}.get(part,45.)
  # A track may be assigned only once per frame. Without this guard two close
  # SMDs can update the same track, leaving ten contours but a count of nine.
  candidates=[(float(np.linalg.norm(center-track['center'])),track) for track in tracks
              if track['last_seen']!=self.overlay_frame]
  distance,track=min(candidates,key=lambda pair:pair[0]) if candidates else (float('inf'),None)
  if track is None or distance>radius:
   tracks.append({'center':center,'contour':reference,'last_seen':self.overlay_frame})
  else:track.update(center=center,contour=reference,last_seen=self.overlay_frame)
 def draw_held_overlays(self,image,H):
  visible={}
  for part,tracks in list(self.overlay_tracks.items()):
   color=COLORS[part];kept=[]
   for track in tracks:
    age=self.overlay_frame-track['last_seen']
    if age>self.a.overlay_hold_frames:continue
    kept.append(track)
    if age==0:continue
    contour=np.rint(cv2.perspectiveTransform(track['contour'],H)).astype(np.int32)
    contour_thickness=1 if part in ('right_white_brown','marked_white') else 2
    cv2.drawContours(image,[contour],-1,color,contour_thickness,cv2.LINE_AA)
    moments=cv2.moments(contour)
    if abs(moments['m00'])>=1e-6:
     u=int(round(moments['m10']/moments['m00']));v=int(round(moments['m01']/moments['m00']))
     self.draw_center_marker(image,(u,v))
   self.overlay_tracks[part]=kept
   visible[part]=len(kept)
  self.overlay_counts=visible
 def draw_center_marker(self,image,center):
  # Two-pass black/white marker stays visible on every part and background.
  cv2.drawMarker(image,center,(0,0,0),cv2.MARKER_CROSS,7,3,cv2.LINE_AA)
  cv2.drawMarker(image,center,(255,255,255),cv2.MARKER_CROSS,7,1,cv2.LINE_AA)
 def order_part_instances(self,part,group):
  def x(item):return item['reference_center_pixel'][0]
  def y(item):return item['reference_center_pixel'][1]
  if part=='gpu':
   return sorted(group,key=x)
  if part=='black_block':
   # VRM numbering is row-major: top row 1..5, bottom row 6..10.
   # Same-row Y jitter must not scramble the left-to-right numbering.
   by_y=sorted(group,key=y)
   ordered=[]
   for row_start in range(0,len(by_y),5):
    ordered.extend(sorted(by_y[row_start:row_start+5],key=x))
   return ordered
  if part not in ('hbm','long_orange'):
   return sorted(group,key=lambda item:(y(item),x(item)))
  # Complete the left set before the right set. Within each set,
  # form two-part rows from top to bottom, then order each row left to right.
  ordered=[]
  by_x=sorted(group,key=x)
  set_size=8 if part=='hbm' else 4
  for start in range(0,len(by_x),set_size):
   one_set=sorted(by_x[start:start+set_size],key=y)
   for row_start in range(0,len(one_set),2):
    ordered.extend(sorted(one_set[row_start:row_start+2],key=x))
  return ordered
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
     source=np.asarray(d['_flange_pose'],float)
     translation_delta=np.abs(current[:3]-source[:3])
     angle_delta=wrapped_angle_delta(current[3:],source[3:])
     if np.max(translation_delta)>self.a.history_pose_match_mm or np.max(angle_delta)>self.a.history_pose_match_deg:
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
   selected.extend(self.order_part_instances(part,group[:limits[part]]))
  stable=selected
  counts={}
  for d in stable:
   counts[d['part_type']]=counts.get(d['part_type'],0)+1
   d['instance_index']=counts[d['part_type']]
  return stable
 def add_base_coordinates(self,result,fx,fy):
  if self.robot is None or time.monotonic()-self.robot_time>self.a.max_robot_state_age_sec:
   return 'NO_FRESH_ROBOT_STATE'
  if len(self.pose_history)<self.a.robot_stable_samples:return 'ROBOT_STABILITY_PENDING'
  poses=np.asarray(self.pose_history)
  translation_span=float(np.max(np.ptp(poses[:,:3],axis=0)))
  rotation_span=float(np.max(wrapped_angle_span(poses[:,3:])))
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
   angle=np.deg2rad(float(detection['angle_deg']))
   ray=np.array([np.cos(angle)/fx,np.sin(angle)/fy,0.0])
   base_axis=T_base_camera[:3,:3]@ray
   detection['long_axis_angle_base_deg']=round(float(np.degrees(np.arctan2(base_axis[1],base_axis[0]))),3)
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
  if (self.a.display_hz>0 and now-self.last_display>=1./self.a.display_hz and
      self.display_lock.acquire(blocking=False)):
   self.last_display=now
   threading.Thread(target=self.display_worker,args=(m,),daemon=True).start()
  if not self.processing_lock.acquire(blocking=False):return
  threading.Thread(target=self.inference_worker,args=(m,),daemon=True).start()
 def display_worker(self,m):
  try:self.publish_live_display(m)
  except Exception as exc:
   self.get_logger().error(f'Live display frame failed; continuing: {exc}')
  finally:self.display_lock.release()
 def inference_worker(self,m):
  try:
   self.process_color(m)
   self.processing_errors=0
  except Exception as exc:
   self.processing_errors+=1
   self.get_logger().error(f"Detection frame failed ({self.processing_errors}); continuing: {exc}\n{traceback.format_exc()}")
  finally:
   self.processing_lock.release()
 def publish_live_display(self,m):
  image=cv2.imdecode(np.frombuffer(m.data,np.uint8),cv2.IMREAD_COLOR)
  if image is None:return
  age_ms=abs(self.stamp(m)-self.shared_registration_stamp_ns)/1000000.
  valid=(self.shared_homography is not None and self.shared_registration_state=='TRACKING' and
         age_ms<=self.a.max_registration_age_ms and self.robot_is_stable())
  H=self.shared_homography.copy() if valid else None
  with self.snapshot_lock:
   tracks={part:[contour.copy() for contour in contours]
           for part,contours in self.display_tracks.items()}
   counts=dict(self.display_counts)
  if H is None:
   label='CAMERA MOVING / TRAY NOT REGISTERED - DETECTIONS DISABLED'
   cv2.putText(image,label,(25,50),cv2.FONT_HERSHEY_SIMPLEX,.62,(0,0,255),2,cv2.LINE_AA)
  else:
   cv2.putText(image,'LIVE VIEW - DETECTION ENABLED',(25,42),
               cv2.FONT_HERSHEY_SIMPLEX,.65,(0,220,0),2,cv2.LINE_AA)
   for part,contours in tracks.items():
    color=COLORS.get(part,(255,255,255))
    thickness=1 if part in ('right_white_brown','marked_white') else 2
    for reference in contours:
     contour=np.rint(cv2.perspectiveTransform(reference.astype(np.float32),H)).astype(np.int32)
     cv2.drawContours(image,[contour],-1,color,thickness,cv2.LINE_AA)
     moments=cv2.moments(contour)
     if abs(moments['m00'])>=1e-6:
      self.draw_center_marker(image,(int(round(moments['m10']/moments['m00'])),
                                     int(round(moments['m01']/moments['m00']))))
   for item in self.bins:
    part=item['part_spec_id'];color=COLORS[part]
    ref=self.ref_points(item).astype(np.float32).reshape(-1,1,2)
    poly=np.rint(cv2.perspectiveTransform(ref,H)[:,0,:]).astype(np.int32)
    cv2.polylines(image,[poly],True,color,2,cv2.LINE_AA)
    value=counts.get(part,0)
    label=f"{item['display_name'].split(' (')[0]} {value}/{item['expected_count']}"
    x=int(poly[:,0].min())+10;y=int(poly[:,1].max())-14
    cv2.putText(image,label,(x,y),cv2.FONT_HERSHEY_SIMPLEX,.43,color,1,cv2.LINE_AA)
  if self.a.display_scale!=1.0:
   image=cv2.resize(image,None,fx=self.a.display_scale,fy=self.a.display_scale,interpolation=cv2.INTER_AREA)
  ok,jpg=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,self.a.display_jpeg_quality])
  if ok:
   out=CompressedImage();out.header=m.header;out.format='jpeg';out.data=jpg.tobytes();self.pub.publish(out)
 def robot_is_stable(self):
  now=time.monotonic()
  # The visual tracker remains the safety gate when the robot-state driver is absent.
  if self.robot is None or now-self.robot_time>self.a.max_robot_state_age_sec:return True
  if len(self.pose_history)<self.a.robot_stable_samples:return False
  poses=np.asarray(self.pose_history,float)
  translation_span=float(np.max(np.ptp(poses[:,:3],axis=0)))
  rotation_span=float(np.max(wrapped_angle_span(poses[:,3:])))
  return (translation_span<=self.a.max_robot_translation_span_mm and
          rotation_span<=self.a.max_robot_rotation_span_deg)
 def process_color(self,m):
  now=time.monotonic()
  if now-self.last<1/self.a.process_hz or self.depth is None or self.info is None:return
  if abs(self.stamp(m)-self.ds)>self.a.max_sync_ms*1000000:return
  image=cv2.imdecode(np.frombuffer(m.data,np.uint8),cv2.IMREAD_COLOR)
  if image is None or image.shape[:2]!=self.depth.shape:return
  self.last=now
  image_stamp_ns=self.stamp(m)
  registration_generation=self.registration_generation
  registration_age_ms=abs(image_stamp_ns-self.shared_registration_stamp_ns)/1000000.
  robot_stable=self.robot_is_stable()
  if (self.shared_homography is not None and self.shared_registration_state=='TRACKING' and
      registration_age_ms<=self.a.max_registration_age_ms and robot_stable):
   H=self.shared_homography.copy();matches=0;inliers=0;registration_source='shared_section_tracker'
  else:
   H=None;matches=0;inliers=0;registration_source='unavailable'
  fx,fy,cx,cy=self.info.k[0],self.info.k[4],self.info.k[2],self.info.k[5]
  if H is not None:state='TRACKING'
  elif not robot_stable:state='ROBOT_MOVING'
  else:state='NOT_REGISTERED'
  if state!=self.registration_state:
   self.get_logger().info(f'Tray state={state}, matches={matches}, inliers={inliers}')
   self.registration_state=state
  result={'schema_version':1,'mode':'tray_detection_dry_run',
          'timestamp_ros_ns':self.stamp(m),'tray_registration':state,
          'registration_matches':matches,'registration_inliers':inliers,
          'registration_source':registration_source,'registration_age_ms':round(registration_age_ms,1),
          'detections':[]}
  if H is not None and self.a.capture_inductor_background is not None and not self.background_captured:
   canonical=cv2.warpPerspective(image,np.linalg.inv(H),(self.rw,self.rh),flags=cv2.INTER_LINEAR)
   output=self.a.capture_inductor_background
   output.parent.mkdir(parents=True,exist_ok=True)
   if not cv2.imwrite(str(output),canonical):raise RuntimeError(f'Failed to save inductor background: {output}')
   metadata=output.with_suffix('.json')
   metadata.write_text(json.dumps({'schema_version':1,'source_timestamp_ros_ns':image_stamp_ns,
    'reference_width':self.rw,'reference_height':self.rh,'layout':str(self.a.layout),
    'robot_motion_authorized':False},indent=2))
   self.background_captured=True
   self.get_logger().info(f'Captured canonical empty-inductor background: {output}')
   rclpy.shutdown();return
  if H is None:
   cv2.putText(image,'TRAY NOT REGISTERED - DETECTIONS DISABLED',(35,55),
               cv2.FONT_HERSHEY_SIMPLEX,.85,(0,0,255),3,cv2.LINE_AA)
  else:
   cv2.putText(image,f'TRAY TRACKING - DETECTION ENABLED inliers={inliers}',(35,55),
               cv2.FONT_HERSHEY_SIMPLEX,.72,(0,220,0),3,cv2.LINE_AA)
  if H is not None:
   self.overlay_frame+=1
   inverse=np.linalg.inv(H)
   canonical=cv2.warpPerspective(image,inverse,(self.rw,self.rh),flags=cv2.INTER_LINEAR)
   depth_float=self.depth.astype(np.float32,copy=False)
   hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
   hue,saturation,value_channel=cv2.split(hsv)
   background_delta=None
   if self.inductor_background is not None:
    projected_background=cv2.warpPerspective(self.inductor_background,H,
      (image.shape[1],image.shape[0]),flags=cv2.INTER_LINEAR)
    current_gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY).astype(np.float32)
    background_gray=cv2.cvtColor(projected_background,cv2.COLOR_BGR2GRAY).astype(np.float32)
    background_delta=cv2.GaussianBlur(current_gray-background_gray,(5,5),0)
   seg_results={}
   if self.seg_model is not None:
    seg_items=[item for item in self.bins if item['part_spec_id'] in self.seg_class_ids]
    seg_crops=[]
    for seg_item in seg_items:
     sx1,sy1,sx2,sy2=map(int,seg_item['roi_px']);pad=self.a.seg_crop_padding
     sx1=max(0,sx1-pad);sy1=max(0,sy1-pad);sx2=min(self.rw,sx2+pad);sy2=min(self.rh,sy2+pad)
     seg_crops.append(canonical[sy1:sy2,sx1:sx2])
    predictions=self.seg_model.predict(seg_crops,imgsz=self.a.seg_image_size,
     conf=min(self.a.seg_confidence,self.a.power_seg_confidence),device=self.a.seg_device,
     iou=self.a.seg_nms_iou,retina_masks=True,verbose=False,batch=len(seg_crops))
    seg_results={item['part_spec_id']:prediction for item,prediction in zip(seg_items,predictions)}
   for item in self.bins:
    part=item['part_spec_id']
    if self.seg_model is not None and part in self.seg_class_ids:
     found,poly,floor=self.find_segmented(item,canonical,image,depth_float,fx,fy,cx,cy,H,seg_results[part])
    else:found,poly,floor=self.find(item,image,background_delta,depth_float,hue,saturation,value_channel,fx,fy,cx,cy,H)
    color=COLORS[part]
    cv2.polylines(image,[poly],True,color,3)
    for n,d in enumerate(found,1):
     contour=d.pop('_contour')
     self.remember_overlay(part,contour,inverse)
     contour_thickness=1 if part in ('right_white_brown','marked_white') else 2
     cv2.drawContours(image,[contour],-1,color,contour_thickness,cv2.LINE_AA)
     u,v=map(int,d['center_pixel'])
     self.draw_center_marker(image,(u,v))
     d.update(part_type=part,display_name=item['display_name'],instance_index=n)
     point=np.float32([[d['center_pixel']]])
     ref=cv2.perspectiveTransform(point,inverse)[0,0]
     d['reference_center_pixel']=[round(float(ref[0]),2),round(float(ref[1]),2)]
     result['detections'].append(d)
   self.draw_held_overlays(image,H)
  self.frame_index+=1
  history_items=[dict(d) for d in result['detections']]
  if self.robot is not None:
   pose=[self.robot.flange_x_cur_pos,self.robot.flange_y_cur_pos,
    self.robot.flange_z_cur_pos,self.robot.flange_a_cur_pos,
    self.robot.flange_b_cur_pos,self.robot.flange_c_cur_pos]
   for item in history_items:item['_flange_pose']=pose
  self.history.append((self.frame_index,history_items))
  # Never mix contours from different frames; stale history created ghost parts.
  result['stable_detections']=self.stabilize(H,fx,fy,cx,cy) if H is not None else []
  result['detected_total']=len(result['detections'])
  result['stable_detected_total']=len(result['stable_detections'])
  instant_counts={item['part_spec_id']:0 for item in self.bins}
  for detection in result['detections']:
   instant_counts[detection['part_type']]+=int(detection.get('instance_estimate',1))
  required={item['part_spec_id']:item['expected_count'] for item in self.bins}
  instant_counts={part:min(count,required[part]) for part,count in instant_counts.items()}
  if H is not None:self.count_history.append(instant_counts)
  counts={part:int(round(np.median([frame[part] for frame in self.count_history])))
   for part in instant_counts} if self.count_history else instant_counts
  for part in self.seg_class_ids:
   if part in self.overlay_counts:counts[part]=min(required[part],self.overlay_counts[part])
  result['display_counts']=counts
  fresh_registration=(H is not None and
   registration_generation==self.registration_generation and
   self.shared_registration_state=='TRACKING')
  with self.snapshot_lock:
   self.display_tracks={part:[track['contour'].copy() for track in tracks]
                        for part,tracks in self.overlay_tracks.items()} if fresh_registration else {}
   self.display_counts=dict(counts) if fresh_registration else {}
  if not fresh_registration:
   self.overlay_tracks.clear();self.overlay_counts.clear()
   self.history.clear();self.count_history.clear()
  overlay_payload={'timestamp_ros_ns':image_stamp_ns,'valid':fresh_registration,
   'counts':self.display_counts,'tracks':{part:[np.asarray(contour).reshape(-1,2).tolist() for contour in contours]
   for part,contours in self.display_tracks.items()}}
  self.overlay_state_pub.publish(String(data=json.dumps(overlay_payload,separators=(',',':'))))
  count_message={'timestamp_ros_ns':result['timestamp_ros_ns'],
   'tray_registration':result['tray_registration'],'counts':counts,'required':required}
  self.counts_pub.publish(String(data=json.dumps(count_message,ensure_ascii=False)))
  if H is not None:
   for item in self.bins:
    part=item['part_spec_id'];color=COLORS[part]
    ref=self.ref_points(item).astype(np.float32).reshape(-1,1,2)
    poly=np.rint(cv2.perspectiveTransform(ref,H)[:,0,:]).astype(np.int32)
    label=f"{item['display_name'].split(' (')[0]} {counts[part]}/{item['expected_count']}"
    x=int(poly[:,0].min())+12;y=int(poly[:,1].max())-18
    (tw,th),base=cv2.getTextSize(label,cv2.FONT_HERSHEY_SIMPLEX,.45,1)
    cv2.rectangle(image,(x-4,y-th-4),(x+tw+4,y+base+4),(20,20,20),-1)
    cv2.putText(image,label,(x,y),cv2.FONT_HERSHEY_SIMPLEX,.45,color,1,cv2.LINE_AA)
  result['base_transform_status']=self.add_base_coordinates(result,fx,fy) if H is not None else 'TRAY_NOT_REGISTERED'
  result['robot_motion_authorized']=False
  unity_parts=[]
  for detection in result['stable_detections']:
   unity_parts.append({
    'id':f"{detection['part_type']}:{int(detection['instance_index']):02d}",
    'part_type':detection['part_type'],
    'display_name':detection['display_name'],
    'instance_index':int(detection['instance_index']),
    'reference_xy_px':detection.get('reference_center_pixel'),
    'camera_xyz_m':detection.get('camera_xyz_m'),
    'base_xyz_mm':detection.get('base_xyz_mm'),
    'angle_base_deg':detection.get('long_axis_angle_base_deg'),
    'observation_frames':int(detection.get('observation_frames',0)),
   })
  unity_payload={
   'schema':'fr5.tray.unity_state/v1',
   'sequence':self.frame_index,
   'timestamp_ros_ns':result['timestamp_ros_ns'],
   'valid':bool(fresh_registration and result['base_transform_status']=='OK'),
   'registration_state':result['tray_registration'],
   'coordinate_frame':'FR5_BASE',
   'position_units':'mm',
   'counts':counts,
   'required':required,
   'parts':unity_parts,
  }
  self.unity_state_pub.publish(String(data=json.dumps(unity_payload,ensure_ascii=False,separators=(',',':'))))
  self.a.output_json.parent.mkdir(parents=True,exist_ok=True)
  tmp=self.a.output_json.with_suffix('.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False));tmp.replace(self.a.output_json)

def main():
 root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser()
 p.add_argument('--layout',type=Path,default=root/'config/tray_layout_candidate.json')
 p.add_argument('--specs',type=Path,default=root/'config/part_specs_candidate.json')
 p.add_argument('--output-json',type=Path,default=root/'data/tray_detections_last.json')
 p.add_argument('--capture-inductor-background',type=Path,default=None)
 p.add_argument('--inductor-background',type=Path,default=root/'data/inductor_empty_background.jpg')
 p.add_argument('--inductor-diff-threshold',type=int,default=8)
 p.add_argument('--inductor-min-height-mm',type=float,default=.6)
 p.add_argument('--inductor-marker-max-value',type=int,default=155)
 p.add_argument('--inductor-marker-min-area-px',type=float,default=8.)
 p.add_argument('--inductor-outline-area-scale',type=float,default=1.2)
 p.add_argument('--seg-model',type=Path,default=root/'models/tray_segmentation/pilot_05/weights/best.pt')
 p.add_argument('--seg-confidence',type=float,default=.20)
 p.add_argument('--power-seg-confidence',type=float,default=.05)
 p.add_argument('--seg-image-size',type=int,default=640)
 p.add_argument('--seg-device',default='0');p.add_argument('--seg-nms-iou',type=float,default=.99)
 p.add_argument('--seg-crop-padding',type=int,default=20)
 p.add_argument('--handeye-file',type=Path,default=root.parents[0]/'calibration/data/handeye_result.json')
 p.add_argument('--color-topic',default='/camera/camera/color/image_raw/compressed')
 p.add_argument('--depth-topic',default='/camera/camera/aligned_depth_to_color/image_raw')
 p.add_argument('--info-topic',default='/camera/camera/color/camera_info')
 p.add_argument('--output-topic',default='/vision/tray/detections_image/compressed')
 p.add_argument('--counts-topic',default='/vision/tray/part_counts')
 p.add_argument('--overlay-state-topic',default='/vision/tray/detection_overlay_state')
 p.add_argument('--unity-state-topic',default='/vision/tray/unity_state')
 p.add_argument('--registration-topic',default='/vision/tray/registration')
 p.add_argument('--max-registration-age-ms',type=float,default=5000.)
 p.add_argument('--max-shared-homography-jump-px',type=float,default=5.)
 p.add_argument('--feature-band-px',type=int,default=120);p.add_argument('--registration-scale',type=float,default=.7)
 p.add_argument('--ratio-test',type=float,default=.72);p.add_argument('--min-matches',type=int,default=14)
 p.add_argument('--min-inliers',type=int,default=10);p.add_argument('--ransac-px',type=float,default=4.)
 p.add_argument('--min-scale-area',type=float,default=.18);p.add_argument('--max-scale-area',type=float,default=3.)
 p.add_argument('--process-hz',type=float,default=2.);p.add_argument('--max-sync-ms',type=float,default=120.)
 p.add_argument('--display-hz',type=float,default=10.)
 p.add_argument('--display-jpeg-quality',type=int,default=75)
 p.add_argument('--display-scale',type=float,default=.75)
 p.add_argument('--min-height-mm',type=float,default=.8);p.add_argument('--max-height-threshold-mm',type=float,default=3.5)
 p.add_argument('--vrm-max-value',type=int,default=105)
 p.add_argument('--orange-hue-min',type=int,default=2)
 p.add_argument('--orange-hue-max',type=int,default=42)
 p.add_argument('--orange-saturation-min',type=int,default=40)
 p.add_argument('--orange-value-min',type=int,default=55)
 p.add_argument('--smd-saturation-min',type=int,default=18)
 p.add_argument('--smd-value-max',type=int,default=225)
 p.add_argument('--min-valid-part-height-mm',type=float,default=.5)
 p.add_argument('--vrm-min-shape-score',type=float,default=.75)
 p.add_argument('--vrm-min-rectangularity',type=float,default=.80)
 p.add_argument('--min-area-score',type=float,default=.52)
 p.add_argument('--min-aspect-score',type=float,default=.58)
 p.add_argument('--min-rectangularity',type=float,default=.52)
 p.add_argument('--min-area-ratio',type=float,default=.06);p.add_argument('--max-area-ratio',type=float,default=5.0)
 p.add_argument('--history-frames',type=int,default=40);p.add_argument('--min-stable-hits',type=int,default=2)
 p.add_argument('--max-missing-frames',type=int,default=3)
 p.add_argument('--count-smoothing-frames',type=int,default=7)
 p.add_argument('--overlay-hold-frames',type=int,default=5)
 p.add_argument('--track-radius-px',type=float,default=16.)
 p.add_argument('--robot-state-topic',default='/nonrt_state_data')
 p.add_argument('--robot-stable-samples',type=int,default=5)
 p.add_argument('--max-robot-state-age-sec',type=float,default=1.)
 p.add_argument('--robot-stream-gap-sec',type=float,default=.5)
 p.add_argument('--max-robot-sample-jump-mm',type=float,default=5.)
 p.add_argument('--max-robot-sample-jump-deg',type=float,default=1.)
 p.add_argument('--max-robot-translation-span-mm',type=float,default=1.0)
 p.add_argument('--max-robot-rotation-span-deg',type=float,default=.2)
 p.add_argument('--history-pose-match-mm',type=float,default=.5)
 p.add_argument('--history-pose-match-deg',type=float,default=.1)
 p.add_argument('--homography-smoothing-frames',type=int,default=7)
 a=p.parse_args();rclpy.init();node=Detector(a);executor=MultiThreadedExecutor(num_threads=4)
 executor.add_node(node)
 try:executor.spin()
 except KeyboardInterrupt:pass
 finally:
  executor.shutdown()
  node.destroy_node()
  if rclpy.ok():rclpy.shutdown()
if __name__=='__main__':main()
