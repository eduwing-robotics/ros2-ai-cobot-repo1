#!/usr/bin/env python3
"""Track a fixed planar tray and draw registered section polygons."""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
from collections import deque
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage
from fairino_msgs.msg import RobotNonrtState
from std_msgs.msg import String

COLORS={'black_block_bin':(0,0,255),'long_orange_bin':(0,165,255),
        'marked_white_bin':(0,255,255),'right_white_brown_bin':(0,200,0),
        'gpu_bin':(255,80,0),'hbm_bin':(220,0,220)}

class Viewer(Node):
 def __init__(self,args):
  super().__init__('tray_section_viewer');self.args=args
  self.config=json.loads(args.config.read_text(encoding='utf-8'))
  ref_path=Path(self.config['reference_image'])
  if not ref_path.is_absolute():ref_path=args.config.parents[2]/ref_path
  self.reference=cv2.imread(str(ref_path))
  if self.reference is None:raise RuntimeError(f'Cannot read reference: {ref_path}')
  self.scale=args.registration_scale
  self.sift=cv2.SIFT_create(nfeatures=1600,contrastThreshold=.025)
  self.matcher=cv2.BFMatcher(cv2.NORM_L2)
  self.ref_gray=cv2.cvtColor(self.reference,cv2.COLOR_BGR2GRAY)
  self.ref_h,self.ref_w=self.ref_gray.shape
  calibrated=self.config.get('trayhome_homography_reference_to_image')
  self.trayhome_homography=np.asarray(calibrated,float) if calibrated is not None else None
  if self.trayhome_homography is not None and self.trayhome_homography.shape!=(3,3):
   raise RuntimeError('Invalid trayhome homography in layout config')
  mask=np.zeros_like(self.ref_gray)
  all_points=[]
  for item in self.config['bins']:
   p=self.reference_points(item,False);all_points.extend(p.tolist())
   cv2.polylines(mask,[p],True,255,args.feature_band_px)
  hull=cv2.convexHull(np.array(all_points,np.int32))
  cv2.polylines(mask,[hull],True,255,args.feature_band_px)
  small_size=(round(self.ref_w*self.scale),round(self.ref_h*self.scale))
  ref_small=cv2.resize(self.ref_gray,small_size,interpolation=cv2.INTER_AREA)
  mask_small=cv2.resize(mask,small_size,interpolation=cv2.INTER_NEAREST)
  self.ref_kp,self.ref_desc=self.sift.detectAndCompute(ref_small,mask_small)
  self.last_state=None
  self.homography_corners=deque(maxlen=args.smoothing_frames)
  self.last_good_corners=None
  self.missed_frames=0
  self.candidate_corners=deque(maxlen=args.initialization_frames)
  self.live_counts={}
  self.counts_time=0.
  self.tray_hull=hull.astype(np.float32)
  # Four points on the same visible tray rim, calibrated in the reference image.
  # They let inexpensive edge fitting pull optical flow back onto the physical tray.
  self.tray_reference_corners=np.float32([[521.07,64.11],[1565.38,70.17],
                                          [1549.71,954.15],[490.45,970.09]])
  self.edge_corners=None
  self.previous_gray=None
  self.track_points=None
  self.last_tracking_time=0.
  self.last_reference_validation=0.
  self.reference_failures=0
  self.last_corner_motion_px=float('inf')
  self.visual_stable_frames=0
  self.trayhome_pose=np.asarray(self.config.get('trayhome_flange_pose_mm_deg',[]),float)
  self.robot_pose=None;self.robot_time=0.;self.at_trayhome=False
  self.image_qos=QoSProfile(history=HistoryPolicy.KEEP_LAST,depth=1,
                            reliability=ReliabilityPolicy.BEST_EFFORT)
  if self.ref_desc is None or len(self.ref_kp)<args.min_matches:
   raise RuntimeError('Not enough reference tray features')
  self.pub=self.create_publisher(CompressedImage,args.output_topic,self.image_qos)
  self.registration_pub=self.create_publisher(String,args.registration_topic,10)
  self.create_subscription(CompressedImage,args.input_topic,self.on_image,self.image_qos)
  self.create_subscription(String,args.counts_topic,self.counts_cb,10)
  self.create_subscription(RobotNonrtState,args.robot_state_topic,self.robot_cb,10)
  self.get_logger().info(f'Tray registration reference: {ref_path}')
  self.get_logger().info(f'Reference features: {len(self.ref_kp)}; no robot commands are sent')

 def robot_cb(self,m):
  self.robot_pose=np.array([m.flange_x_cur_pos,m.flange_y_cur_pos,m.flange_z_cur_pos,
   m.flange_a_cur_pos,m.flange_b_cur_pos,m.flange_c_cur_pos],float)
  self.robot_time=time.monotonic()
 def robot_at_trayhome(self):
  if self.trayhome_pose.shape!=(6,) or self.robot_pose is None:return False
  if time.monotonic()-self.robot_time>self.args.max_robot_state_age_sec:return False
  position_delta=np.abs(self.robot_pose[:3]-self.trayhome_pose[:3])
  # Euler angles wrap at +/-180 degrees. Treat +179.999 and -179.999 as the
  # same pose instead of a 359.998-degree movement.
  angle_delta=np.abs((self.robot_pose[3:]-self.trayhome_pose[3:]+180.)%360.-180.)
  return (np.max(position_delta)<=self.args.trayhome_position_tolerance_mm and
          np.max(angle_delta)<=self.args.trayhome_angle_tolerance_deg)

 def counts_cb(self,message):
  try:
   payload=json.loads(message.data)
   if payload.get('tray_registration')=='TRACKING':
    self.live_counts={str(k):int(v) for k,v in payload.get('counts',{}).items()}
    self.counts_time=time.monotonic()
  except (ValueError,TypeError):
   self.get_logger().warning('Ignored invalid tray part count message')

 def reference_points(self,item,inset=True):
  p=np.array([[round(x*self.ref_w),round(y*self.ref_h)]
              for x,y in item['section_polygon_normalized']],np.int32)
  if inset:
   c=p.astype(float).mean(axis=0);gap=max(4,round(min(self.ref_w,self.ref_h)*.0045))
   p[:,0]+=np.where(p[:,0]<c[0],gap,-gap);p[:,1]+=np.where(p[:,1]<c[1],gap,-gap)
  return p

 def validate_corners(self,moved):
  if not np.all(np.isfinite(moved)):return False
  contour=moved.astype(np.float32)
  if not cv2.isContourConvex(contour):return False
  area=abs(cv2.contourArea(contour));ratio=area/(self.ref_w*self.ref_h)
  if not self.args.min_scale_area<=ratio<=self.args.max_scale_area:return False
  edges=np.linalg.norm(np.roll(moved,-1,axis=0)-moved,axis=1)
  if edges.min()<min(self.ref_w,self.ref_h)*.12:return False
  top=moved[1]-moved[0];bottom=moved[2]-moved[3]
  left=moved[3]-moved[0];right=moved[2]-moved[1]
  # Reject mirrored, upside-down and quarter-turned SIFT homographies.
  if top[0]<=abs(top[1]) or bottom[0]<=abs(bottom[1]):return False
  if left[1]<=abs(left[0]) or right[1]<=abs(right[0]):return False
  return True

 def accept_corners(self,moved):
  self.candidate_corners.append(moved.copy())
  if self.last_good_corners is None:
   if len(self.candidate_corners)<self.args.initialization_support:return None
   candidates=np.asarray(self.candidate_corners)
   distances=np.max(np.linalg.norm(candidates[:,None]-candidates[None,:],axis=3),axis=2)
   medoid=int(np.argmin(np.median(distances,axis=1)))
   members=candidates[distances[medoid]<=self.args.initialization_radius_px]
   if len(members)<self.args.initialization_support:return None
   accepted=np.median(members,axis=0).astype(np.float32)
  elif not self.args.dynamic_registration:
   return self.last_good_corners.copy()
  else:
   jump=float(np.max(np.linalg.norm(moved-self.last_good_corners,axis=1)))
   if jump>self.args.max_corner_jump_px:return None
   accepted=moved
  self.last_good_corners=accepted.copy();self.missed_frames=0
  return accepted

 def reference_visible(self,gray):
  small=cv2.resize(gray,None,fx=self.scale,fy=self.scale,interpolation=cv2.INTER_AREA)
  kp,desc=self.sift.detectAndCompute(small,None)
  if desc is None:return False,0,0
  pairs=self.matcher.knnMatch(self.ref_desc,desc,k=2)
  # FLANN may return fewer than k neighbours for a sparse descriptor set.
  # Ignore incomplete pairs instead of terminating tray registration.
  good=[pair[0] for pair in pairs if len(pair)==2 and
        pair[0].distance<self.args.ratio_test*pair[1].distance]
  if len(good)<self.args.min_matches:return False,len(good),0
  src=np.float32([self.ref_kp[m.queryIdx].pt for m in good]).reshape(-1,1,2)
  dst=np.float32([kp[m.trainIdx].pt for m in good]).reshape(-1,1,2)
  _,inliers=cv2.findHomography(src,dst,cv2.RANSAC,self.args.ransac_px)
  count=int(inliers.sum()) if inliers is not None else 0
  ratio=count/max(1,len(good))
  visible=count>=self.args.min_inliers and ratio>=self.args.min_visibility_inlier_ratio
  return visible,len(good),count

 def register(self,gray):
  small=cv2.resize(gray,None,fx=self.scale,fy=self.scale,interpolation=cv2.INTER_AREA)
  kp,desc=self.sift.detectAndCompute(small,None)
  if desc is None:return None,0,0
  pairs=self.matcher.knnMatch(self.ref_desc,desc,k=2)
  good=[pair[0] for pair in pairs if len(pair)==2 and
        pair[0].distance<self.args.ratio_test*pair[1].distance]
  if len(good)<self.args.min_matches:return None,len(good),0
  src=np.float32([self.ref_kp[m.queryIdx].pt for m in good]).reshape(-1,1,2)
  dst=np.float32([kp[m.trainIdx].pt for m in good]).reshape(-1,1,2)
  H,inliers=cv2.findHomography(src,dst,cv2.RANSAC,self.args.ransac_px)
  count=int(inliers.sum()) if inliers is not None else 0
  if H is None or count<self.args.min_inliers:return None,len(good),count
  scale=np.diag([self.scale,self.scale,1.])
  full=np.linalg.inv(scale)@H@scale
  corners=np.float32([[[0,0],[self.ref_w,0],[self.ref_w,self.ref_h],[0,self.ref_h]]])
  moved=cv2.perspectiveTransform(corners,full)[0]
  if not self.validate_corners(moved):return None,len(good),count
  if self.last_good_corners is None and self.trayhome_homography is not None:
   calibrated_corners=cv2.perspectiveTransform(corners,self.trayhome_homography)[0]
   calibration_error=float(np.max(np.linalg.norm(moved-calibrated_corners,axis=1)))
   if calibration_error>self.args.trayhome_snap_radius_px:return None,len(good),count
  moved=self.accept_corners(moved)
  if moved is None:return None,len(good),count
  self.homography_corners.append(moved)
  smooth=np.median(np.asarray(self.homography_corners),axis=0).astype(np.float32)
  full=cv2.getPerspectiveTransform(corners[0].astype(np.float32),smooth)
  return full,len(good),count

 def held_homography(self):
  if self.last_good_corners is None:return None
  if self.args.dynamic_registration and self.missed_frames>=self.args.hold_frames:return None
  self.missed_frames+=1
  corners=np.float32([[0,0],[self.ref_w,0],[self.ref_w,self.ref_h],[0,self.ref_h]])
  smooth=np.median(np.asarray(self.homography_corners),axis=0).astype(np.float32)
  return cv2.getPerspectiveTransform(corners,smooth)

 def invalidate_registration(self):
  self.last_good_corners=None
  self.homography_corners.clear()
  self.candidate_corners.clear()
  self.missed_frames=0
  self.reference_failures=0
  self.previous_gray=None
  self.track_points=None

 def reset_optical_tracking(self,gray):
  mask=np.zeros_like(gray)
  if self.last_good_corners is not None:
   reference=np.float32([[0,0],[self.ref_w,0],[self.ref_w,self.ref_h],[0,self.ref_h]])
   H=cv2.getPerspectiveTransform(reference,self.last_good_corners.astype(np.float32))
   polygon=cv2.perspectiveTransform(self.tray_hull.reshape(-1,1,2),H)[:,0]
   cv2.fillConvexPoly(mask,np.rint(polygon).astype(np.int32),255)
  self.track_points=cv2.goodFeaturesToTrack(gray,mask=mask,maxCorners=400,
   qualityLevel=.01,minDistance=8,blockSize=7)
  self.previous_gray=gray.copy()

 def refine_with_tray_edges(self,gray,H):
  predicted=cv2.perspectiveTransform(self.tray_reference_corners.reshape(1,-1,2),H)[0]
  edges=cv2.Canny(cv2.GaussianBlur(gray,(5,5),0),
                  self.args.edge_canny_low,self.args.edge_canny_high)
  ys,xs=np.nonzero(edges)
  points=np.column_stack([xs,ys]).astype(np.float32)
  if len(points)<self.args.min_edge_points*4:return None
  fitted=[]
  for index in range(4):
   start=predicted[index];end=predicted[(index+1)%4]
   vector=end-start;length=float(np.linalg.norm(vector))
   if length<80.:return None
   direction=vector/length;normal=np.float32([-direction[1],direction[0]])
   relative=points-start
   along=relative@direction;distance=np.abs(relative@normal)
   selected=points[(along>length*.08)&(along<length*.92)&
                   (distance<self.args.edge_search_radius_px)]
   if len(selected)<self.args.min_edge_points:return None
   selected_along=(selected-start)@direction
   if np.ptp(selected_along)<length*self.args.min_edge_coverage:return None
   line=cv2.fitLine(selected,cv2.DIST_HUBER,0,.01,.01).reshape(-1)
   line_direction=line[:2]/np.linalg.norm(line[:2])
   if abs(float(line_direction@direction))<np.cos(np.deg2rad(self.args.max_edge_angle_deg)):
    return None
   line_normal=np.float32([-line_direction[1],line_direction[0]])
   fitted.append((line_normal,float(line_normal@line[2:])))
  detected=[]
  for index in range(4):
   matrix=np.stack([fitted[(index-1)%4][0],fitted[index][0]])
   if abs(float(np.linalg.det(matrix)))<.2:return None
   detected.append(np.linalg.solve(matrix,np.float32(
    [fitted[(index-1)%4][1],fitted[index][1]])))
  detected=np.asarray(detected,np.float32)
  correction=np.linalg.norm(detected-predicted,axis=1)
  if (not np.all(np.isfinite(detected)) or
      float(correction.max())>self.args.max_edge_correction_px):
   return None
  corrected=predicted+self.args.edge_correction_gain*(detected-predicted)
  if not cv2.isContourConvex(corrected):return None
  self.edge_corners=corrected.copy()
  return cv2.getPerspectiveTransform(self.tray_reference_corners,corrected)

 def track_optical(self,gray):
  if self.previous_gray is None or self.track_points is None or len(self.track_points)<self.args.min_track_points:
   self.reset_optical_tracking(gray);return None,0
  forward,status,_=cv2.calcOpticalFlowPyrLK(self.previous_gray,gray,self.track_points,None,
   winSize=(31,31),maxLevel=4,criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,.01))
  backward,status_back,_=cv2.calcOpticalFlowPyrLK(gray,self.previous_gray,forward,None,
   winSize=(31,31),maxLevel=4,criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,.01))
  error=np.linalg.norm(self.track_points-backward,axis=2).reshape(-1)
  valid=(status.reshape(-1)>0)&(status_back.reshape(-1)>0)&(error<1.5)
  old=self.track_points[valid];new=forward[valid]
  if len(old)<self.args.min_track_points:
   self.reset_optical_tracking(gray);return None,len(old)
  affine,inliers=cv2.estimateAffine2D(old.reshape(-1,2),new.reshape(-1,2),
   method=cv2.RANSAC,ransacReprojThreshold=2.5,maxIters=2000,confidence=.995,refineIters=10)
  count=int(inliers.sum()) if inliers is not None else 0
  if affine is None or count<self.args.min_track_inliers:
   self.reset_optical_tracking(gray);return None,count
  used=old.reshape(-1,2)[inliers.reshape(-1)>0]
  tray_span=np.ptp(self.last_good_corners,axis=0)
  feature_span=np.ptp(used,axis=0)
  if np.any(feature_span<self.args.min_track_coverage*tray_span):
   self.reset_optical_tracking(gray);return None,count
  singular=np.linalg.svd(affine[:,:2],compute_uv=False)
  if np.linalg.det(affine[:,:2])<=0 or singular.min()<.92 or singular.max()>1.08:
   self.reset_optical_tracking(gray);return None,count
  delta=np.vstack([affine,[0.,0.,1.]])
  moved=cv2.perspectiveTransform(self.last_good_corners.reshape(-1,1,2),delta)[:,0]
  jump=float(np.max(np.linalg.norm(moved-self.last_good_corners,axis=1)))
  if not self.validate_corners(moved) or jump>self.args.max_corner_jump_px:
   self.reset_optical_tracking(gray);return None,count
  self.last_corner_motion_px=jump
  self.last_good_corners=moved.astype(np.float32);self.missed_frames=0
  self.previous_gray=gray.copy();self.track_points=new[inliers.reshape(-1)>0].reshape(-1,1,2)
  if len(self.track_points)<self.args.redetect_track_points:self.reset_optical_tracking(gray)
  reference=np.float32([[0,0],[self.ref_w,0],[self.ref_w,self.ref_h],[0,self.ref_h]])
  return cv2.getPerspectiveTransform(reference,self.last_good_corners),count

 def on_image(self,msg):
  now=time.monotonic()
  if now-self.last_tracking_time<1./self.args.tracking_hz:return
  self.last_tracking_time=now
  image=cv2.imdecode(np.frombuffer(msg.data,np.uint8),cv2.IMREAD_COLOR)
  if image is None:return
  gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
  at_trayhome=self.robot_at_trayhome() and self.trayhome_homography is not None
  if at_trayhome:
   corners=np.float32([[0,0],[self.ref_w,0],[self.ref_w,self.ref_h],[0,self.ref_h]])
   if self.at_trayhome and self.last_good_corners is not None:
    seed_H=cv2.getPerspectiveTransform(corners,self.last_good_corners.astype(np.float32))
   else:
    seed_H=self.trayhome_homography.copy()
    self.homography_corners.clear();self.edge_corners=None
   previous_edge_corners=None if self.edge_corners is None else self.edge_corners.copy()
   edge_H=self.refine_with_tray_edges(gray,seed_H)
   if edge_H is not None:
    moved=cv2.perspectiveTransform(corners.reshape(1,-1,2),edge_H)[0]
    jump=(0. if self.last_good_corners is None else
     float(np.max(np.linalg.norm(moved-self.last_good_corners,axis=1))))
    refinement_limit=(self.args.max_trayhome_startup_jump_px
     if len(self.homography_corners)<self.args.smoothing_frames
     else self.args.max_trayhome_refinement_jump_px)
    edge_jump=(0. if previous_edge_corners is None else float(np.max(
     np.linalg.norm(self.edge_corners-previous_edge_corners,axis=1))))
    if previous_edge_corners is not None and edge_jump>refinement_limit:
     edge_H=None;self.edge_corners=previous_edge_corners
    else:
     self.last_corner_motion_px=jump
     self.homography_corners.append(moved.astype(np.float32))
     smooth=np.median(np.asarray(self.homography_corners),axis=0).astype(np.float32)
     H=cv2.getPerspectiveTransform(corners,smooth)
     self.last_good_corners=smooth.copy();self.missed_frames=0
     matches=0;inliers=0;state='TRACKING'
     self.visual_stable_frames=self.args.stable_tracking_frames
     if not self.at_trayhome:self.reset_optical_tracking(gray)
   if edge_H is None:
    matches=0;inliers=0
    if self.at_trayhome and self.last_good_corners is not None:
     H=cv2.getPerspectiveTransform(corners,self.last_good_corners.astype(np.float32))
     state='TRACKING'
     self.edge_corners=previous_edge_corners
    else:
     H=None;state='INITIALIZING'
   self.at_trayhome=True
  elif self.last_good_corners is None:
   H,matches,inliers=self.register(gray)
   if H is not None:
    edge_H=self.refine_with_tray_edges(gray,H)
    if edge_H is not None:
     H=edge_H
     frame=np.float32([[0,0],[self.ref_w,0],[self.ref_w,self.ref_h],[0,self.ref_h]])
     self.last_good_corners=cv2.perspectiveTransform(frame.reshape(1,-1,2),H)[0]
     self.homography_corners.clear();self.homography_corners.append(self.last_good_corners.copy())
    self.reset_optical_tracking(gray)
   state='INITIALIZING' if H is None else 'TRACKING'
  else:
   if self.at_trayhome:self.reset_optical_tracking(gray)
   self.at_trayhome=False
   H,inliers=self.track_optical(gray);matches=0;state='TRACKING'
   if H is not None:
    edge_H=self.refine_with_tray_edges(gray,H)
    if edge_H is not None:
     H=edge_H
     frame=np.float32([[0,0],[self.ref_w,0],[self.ref_w,self.ref_h],[0,self.ref_h]])
     self.last_good_corners=cv2.perspectiveTransform(frame.reshape(1,-1,2),H)[0]
     self.homography_corners.clear();self.homography_corners.append(self.last_good_corners.copy())
    else:self.edge_corners=None
    if self.last_corner_motion_px>self.args.motion_threshold_px:
     self.visual_stable_frames=0
    else:
     self.visual_stable_frames+=1
    if self.visual_stable_frames<self.args.stable_tracking_frames:
     state='CAMERA_MOVING'
   # Optical flow may follow the background after the camera leaves the tray.
   if now-self.last_reference_validation>=self.args.reference_validation_sec:
    self.last_reference_validation=now
    visible,validation_matches,validation_inliers=self.reference_visible(gray)
    if visible:
     self.reference_failures=0
    else:
     self.reference_failures+=1
     if self.reference_failures>=self.args.reference_failure_limit:
      self.invalidate_registration()
      H=None;matches=validation_matches;inliers=validation_inliers
      state='NOT_REGISTERED'
  if H is None:
   H=self.held_homography();state='HELD' if H is not None else 'NOT_REGISTERED'
  if state!=self.last_state:
   self.get_logger().info(f'Tray state={state}, matches={matches}, inliers={inliers}')
   self.last_state=state
  stamp_ns=msg.header.stamp.sec*1000000000+msg.header.stamp.nanosec
  registration={'timestamp_ros_ns':stamp_ns,'state':state}
  if H is not None:
   registration['homography_reference_to_image']=np.asarray(H,float).tolist()
   if self.edge_corners is not None:
    registration['tray_edge_corners_image']=self.edge_corners.tolist()
  self.registration_pub.publish(String(data=json.dumps(registration)))
  if self.args.registration_only:return
  if H is None:
   cv2.putText(image,f'TRAY NOT REGISTERED  matches={matches} inliers={inliers}',
               (35,55),cv2.FONT_HERSHEY_SIMPLEX,.9,(0,0,255),3,cv2.LINE_AA)
  else:
   cv2.putText(image,f'TRAY {state}  inliers={inliers}',(35,55),
               cv2.FONT_HERSHEY_SIMPLEX,.8,(0,220,0),3,cv2.LINE_AA)
   for item in self.config['bins']:
    ref=self.reference_points(item).astype(np.float32).reshape(-1,1,2)
    points=np.rint(cv2.perspectiveTransform(ref,H)[:,0,:]).astype(np.int32)
    color=COLORS.get(item['bin_id'],(255,255,255))
    cv2.polylines(image,[points],True,color,4,cv2.LINE_AA)
    current=self.live_counts.get(item['part_spec_id']) if time.monotonic()-self.counts_time<=self.args.max_counts_age_sec else None
    count_text='?' if current is None else str(current)
    label=f"{item['display_name'].split(' (')[0]} {count_text}/{item['expected_count']}"
    x=int(points[:,0].min())+12;y=int(points[:,1].max())-18
    (tw,th),base=cv2.getTextSize(label,cv2.FONT_HERSHEY_SIMPLEX,.65,2)
    cv2.rectangle(image,(x-7,y-th-7),(x+tw+7,y+base+7),(20,20,20),-1)
    cv2.putText(image,label,(x,y),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),2,cv2.LINE_AA)
  ok,jpg=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,self.args.output_jpeg_quality])
  if ok:
   out=CompressedImage();out.header=msg.header;out.format='jpeg';out.data=jpg.tobytes();self.pub.publish(out)

def main():
 root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser()
 p.add_argument('--config',type=Path,default=root/'config/tray_layout_candidate.json')
 p.add_argument('--input-topic',default='/camera/camera/color/image_raw/compressed')
 p.add_argument('--output-topic',default='/vision/tray/sections_image/compressed')
 p.add_argument('--counts-topic',default='/vision/tray/part_counts')
 p.add_argument('--registration-topic',default='/vision/tray/registration')
 p.add_argument('--robot-state-topic',default='/nonrt_state_data')
 p.add_argument('--max-robot-state-age-sec',type=float,default=5.0)
 p.add_argument('--trayhome-position-tolerance-mm',type=float,default=.8)
 p.add_argument('--trayhome-angle-tolerance-deg',type=float,default=.15)
 p.add_argument('--tracking-hz',type=float,default=7.)
 p.add_argument('--reference-validation-sec',type=float,default=1.0)
 p.add_argument('--reference-failure-limit',type=int,default=2)
 p.add_argument('--registration-only',action='store_true')
 p.add_argument('--max-counts-age-sec',type=float,default=3.)
 p.add_argument('--output-jpeg-quality',type=int,default=80)
 p.add_argument('--feature-band-px',type=int,default=120)
 p.add_argument('--registration-scale',type=float,default=.7)
 p.add_argument('--smoothing-frames',type=int,default=15)
 p.add_argument('--ratio-test',type=float,default=.78);p.add_argument('--min-matches',type=int,default=12)
 p.add_argument('--min-inliers',type=int,default=6);p.add_argument('--ransac-px',type=float,default=4.)
 p.add_argument('--min-visibility-inlier-ratio',type=float,default=.15)
 p.add_argument('--min-scale-area',type=float,default=.18);p.add_argument('--max-scale-area',type=float,default=3.0)
 p.add_argument('--max-corner-jump-px',type=float,default=45.)
 p.add_argument('--hold-frames',type=int,default=20)
 p.add_argument('--initialization-frames',type=int,default=20)
 p.add_argument('--initialization-support',type=int,default=5)
 p.add_argument('--initialization-radius-px',type=float,default=35.)
 p.add_argument('--trayhome-snap-radius-px',type=float,default=55.)
 p.add_argument('--dynamic-registration',action='store_true')
 p.add_argument('--min-track-points',type=int,default=30)
 p.add_argument('--min-track-inliers',type=int,default=30)
 p.add_argument('--redetect-track-points',type=int,default=80)
 p.add_argument('--min-track-coverage',type=float,default=.45)
 p.add_argument('--edge-search-radius-px',type=float,default=24.)
 p.add_argument('--min-edge-points',type=int,default=80)
 p.add_argument('--min-edge-coverage',type=float,default=.55)
 p.add_argument('--max-edge-angle-deg',type=float,default=8.)
 p.add_argument('--max-edge-correction-px',type=float,default=32.)
 p.add_argument('--max-trayhome-startup-jump-px',type=float,default=10.)
 p.add_argument('--max-trayhome-refinement-jump-px',type=float,default=3.)
 p.add_argument('--edge-correction-gain',type=float,default=.65)
 p.add_argument('--edge-canny-low',type=int,default=45)
 p.add_argument('--edge-canny-high',type=int,default=120)
 p.add_argument('--motion-threshold-px',type=float,default=1.5)
 p.add_argument('--stable-tracking-frames',type=int,default=3)
 p.set_defaults(dynamic_registration=True)
 a=p.parse_args();rclpy.init();node=Viewer(a)
 try:rclpy.spin(node)
 except (KeyboardInterrupt, ExternalShutdownException):pass
 finally:
  node.destroy_node()
  if rclpy.ok():rclpy.shutdown()
if __name__=='__main__':main()
