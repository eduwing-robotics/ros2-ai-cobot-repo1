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
  fixed_payload=json.loads(a.fixed_view_pose_file.read_text(encoding='utf-8'))
  self.fixed_view_pose=np.asarray(fixed_payload['pose_mm_deg'],float)
  self.fixed_view_homography=np.asarray(
   fixed_payload.get('reference_to_live_homography',np.eye(3)),float)
  self.fixed_position_tolerance_mm=float(fixed_payload.get('position_tolerance_mm',1.0))
  self.fixed_rotation_tolerance_deg=float(fixed_payload.get('rotation_tolerance_deg',.3))
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
  self.last_robot_motion_time=0.
  self.robot_group=ReentrantCallbackGroup()
  self.previous_robot_pose=None
  self.homography_corners=deque(maxlen=a.homography_smoothing_frames)
  self.cached_homography=None;self.cached_registration_time=0.
  self.cached_matches=0;self.cached_inliers=0;self.last_registration_attempt=0.
  self.depth=self.info=None; self.ds=0; self.last=0.
  self.last_debug_write=0.
  self.pub=self.create_publisher(CompressedImage,a.output_topic,qos_profile_sensor_data)
  self.create_subscription(Image,a.depth_topic,self.depth_cb,qos_profile_sensor_data)
  self.create_subscription(CameraInfo,a.info_topic,self.info_cb,qos_profile_sensor_data)
  self.create_subscription(CompressedImage,a.color_topic,self.color_cb,qos_profile_sensor_data)
  self.create_subscription(RobotNonrtState,a.robot_state_topic,self.robot_cb,10,
                           callback_group=self.robot_group)
  self.get_logger().info('Dry-run only: no robot command is sent.')
 @staticmethod
 def stamp(m): return m.header.stamp.sec*1000000000+m.header.stamp.nanosec
 @staticmethod
 def angular_abs_delta_deg(a,b):
  """Smallest absolute Euler-component delta; +180 and -180 are identical."""
  return np.abs((np.asarray(a,float)-np.asarray(b,float)+180.0)%360.0-180.0)
 @staticmethod
 def directed_angle(angle_deg,center,marker):
  """Resolve a rectangle's 180-degree ambiguity with an asymmetric marker."""
  radians=np.deg2rad(float(angle_deg))
  axis=np.array([np.cos(radians),np.sin(radians)],float)
  marker_vector=np.asarray(marker,float)-np.asarray(center,float)
  directed=float(angle_deg)+(180.0 if float(np.dot(axis,marker_vector))<0 else 0.0)
  return round(directed%360.0,2)
 def info_cb(self,m): self.info=m
 def robot_cb(self,m):
  now=time.monotonic()
  pose=np.array([m.flange_x_cur_pos,m.flange_y_cur_pos,m.flange_z_cur_pos,
   m.flange_a_cur_pos,m.flange_b_cur_pos,m.flange_c_cur_pos],float)
  moved=False
  if self.previous_robot_pose is not None:
   translation_delta=np.abs(pose[:3]-self.previous_robot_pose[:3])
   rotation_delta=self.angular_abs_delta_deg(pose[3:],self.previous_robot_pose[3:])
   moved=(np.max(translation_delta)>self.a.robot_motion_delta_mm or
          np.max(rotation_delta)>self.a.robot_motion_delta_deg)
   if moved:
    # Do not combine frames recorded before/during a robot move with the final
    # flange pose. This was the source of unstable Base targets after a return
    # to the tray view.
    self.last_robot_motion_time=now;self.pose_history.clear();self.history.clear()
    self.homography_corners.clear()
    self.cached_homography=None;self.cached_registration_time=0.
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
 def find(self,item,fx,fy,cx,cy,H,image):
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
  height_mask=valid&((floor-self.depth.astype(float))>=th)
  mask=height_mask.astype(np.uint8)*255
  hsv=lab=None
  if part=='gpu':
   # Segment the black body from colour first. Shadows may also be dark, so a
   # candidate is accepted only when enough pixels are physically raised.
   hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
   lab=cv2.cvtColor(image,cv2.COLOR_BGR2LAB)
   dark=(valid & (hsv[:,:,2]<=self.a.gpu_hsv_v_max) &
         (lab[:,:,0]<=self.a.gpu_lab_l_max))
   mask=dark.astype(np.uint8)*255
  open_size=3 if part=='gpu' else 5
  close_size=15 if part=='gpu' else 9
  mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(open_size,open_size)))
  mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(close_size,close_size)))
  expected=max(20.,fx*size['x']/floor*fy*size['y']/floor); found=[]
  contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
  diagnostics=[]
  for contour in contours:
   area=cv2.contourArea(contour)
   diagnostic={'area_px':round(float(area),1),
               'area_ratio':round(float(area/expected),3)}
   min_ratio=self.a.gpu_min_area_ratio if part=='gpu' else self.a.min_area_ratio
   max_ratio=self.a.gpu_max_area_ratio if part=='gpu' else self.a.max_area_ratio
   if not expected*min_ratio<=area<=expected*max_ratio:
    diagnostic['rejected']='color_area';diagnostics.append(diagnostic);continue
   cm=np.zeros_like(roi);cv2.drawContours(cm,[contour],-1,255,-1)
   (_, _),(color_x,color_y),_=cv2.minAreaRect(contour)
   color_bbox_size=[float(max(color_x,color_y)),float(min(color_x,color_y))]
   contour_valid=(cm>0)&valid
   values=self.depth[contour_valid]
   if values.size<10:
    diagnostic['rejected']='no_valid_depth';diagnostics.append(diagnostic);continue
   raised=contour_valid&height_mask
   raised_fraction=float(np.count_nonzero(raised)/max(np.count_nonzero(contour_valid),1))
   diagnostic['raised_fraction']=round(raised_fraction,3)
   if part=='gpu' and raised_fraction<self.a.gpu_min_raised_ratio:
    diagnostic['rejected']='raised_fraction';diagnostics.append(diagnostic);continue
   geometry_contour=contour
   geometry_area=area
   if part=='gpu':
    geometry_mask=raised.astype(np.uint8)*255
    geometry_mask=cv2.morphologyEx(
     geometry_mask,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))
    raised_contours,_=cv2.findContours(
     geometry_mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if not raised_contours:
     diagnostic['rejected']='no_raised_contour';diagnostics.append(diagnostic);continue
    geometry_contour=max(raised_contours,key=cv2.contourArea)
    geometry_area=cv2.contourArea(geometry_contour)
    diagnostic['geometry_area_ratio']=round(float(geometry_area/expected),3)
    if geometry_area<expected*self.a.gpu_min_geometry_area_ratio:
     diagnostic['rejected']='geometry_area';diagnostics.append(diagnostic);continue
   (u,v),(x,y),raw_angle=cv2.minAreaRect(geometry_contour)
   if min(x,y)<3:
    diagnostic['rejected']='short_side';diagnostics.append(diagnostic);continue
   surface_values=self.depth[raised] if part=='gpu' else values
   if surface_values.size<10:
    diagnostic['rejected']='no_surface_depth';diagnostics.append(diagnostic);continue
   zmm=float(np.median(surface_values));z=zmm/1000.
   # Keep one unambiguous box convention: width=long side, height=short side,
   # and angle follows the long side. OpenCV otherwise swaps x/y and angle.
   if x>=y:long_side,short_side,box_angle=x,y,raw_angle
   else:long_side,short_side,box_angle=y,x,raw_angle+90
   box_angle=((box_angle+90)%180)-90
   measured_long_side=float(long_side);measured_short_side=float(short_side)
   if part=='gpu':
    # A dark GPU face can be split by reflections or the printed logo.  The
    # contour gives the centre and heading, but neither its area nor aspect
    # ratio should resize the target. Project the known physical 57x27 mm
    # footprint with the camera intrinsics/depth, so shadows and reflections
    # cannot make the box grow or shrink between frames.
    cad_long=max(float(size['x']),float(size['y']))
    cad_short=min(float(size['x']),float(size['y']))
    cad_aspect=cad_long/cad_short
    long_side=float(np.sqrt(expected*cad_aspect))*self.a.gpu_box_scale
    short_side=float(long_side/cad_aspect)
   fitted_box=np.rint(cv2.boxPoints(((float(u),float(v)),
                                    (float(long_side),float(short_side)),
                                    float(box_angle)))).astype(np.int32)
   found.append({'center_pixel':[round(u,2),round(v,2)],
    'bbox_size_px':[round(long_side,2),round(short_side,2)],'angle_deg':round(box_angle,2),
    'measured_bbox_size_px':[round(measured_long_side,2),round(measured_short_side,2)],
    'color_bbox_size_px':[round(color_bbox_size[0],2),round(color_bbox_size[1],2)],
    'depth_m':round(z,6),'height_above_tray_mm':round(floor-zmm,3),
    'camera_xyz_m':[round((u-cx)*z/fx,6),round((v-cy)*z/fy,6),round(z,6)],
    'cad_area_match_score':round(float(np.exp(-abs(np.log(max(geometry_area,1)/expected)))),3),
    'raised_fraction':round(raised_fraction,3),
    '_contour':geometry_contour,'_fitted_box':fitted_box})
   diagnostic['accepted']=True;diagnostic['center_pixel']=[round(u,1),round(v,1)]
   diagnostics.append(diagnostic)
  if part=='gpu':self.gpu_diagnostics=diagnostics
  found.sort(key=lambda q:q['cad_area_match_score'],reverse=True)
  return found[:item['expected_count']],poly,floor
 def find_gpu_orientation_dot(self,image,box):
  """Find the small white corner dot used to disambiguate GPU orientation."""
  region=np.zeros(image.shape[:2],np.uint8);cv2.fillPoly(region,[box],255)
  # Do not expand beyond the fitted GPU box. At a body corner the white dot
  # otherwise joins the surrounding white tray and becomes one huge contour.
  region=cv2.erode(region,np.ones((3,3),np.uint8))
  hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV);gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
  dark_context=cv2.boxFilter((gray<90).astype(np.float32),-1,(11,11),
                             normalize=True)
  white=((region>0)&(gray>=110)&(hsv[:,:,1]<=180)&
         (dark_context>=.25)).astype(np.uint8)*255
  dots,_=cv2.findContours(white,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
  corners=np.asarray(box,float)
  short_side=float(np.min(np.linalg.norm(np.roll(corners,-1,axis=0)-corners,axis=1)))
  max_corner_distance=max(18.0,min(55.0,short_side*.60))
  best=None;best_score=-float('inf')
  for candidate in dots:
   area=cv2.contourArea(candidate)
   if not 1.0<=area<=120.0:continue
   perimeter=cv2.arcLength(candidate,True)
   circularity=4*np.pi*area/(perimeter*perimeter) if perimeter>1e-6 else 0.0
   moments=cv2.moments(candidate)
   if moments['m00']==0:continue
   point=np.array([moments['m10']/moments['m00'],moments['m01']/moments['m00']])
   if circularity<.42:continue
   # The marker is at a corner; logo text is farther from every corner.
   corner_distance=float(np.min(np.linalg.norm(corners-point,axis=1)))
   # The real orientation dot is printed at a body corner. NVIDIA logo text
   # may be bright/circular too, but is far from every corner.
   if corner_distance>max_corner_distance:continue
   score=-corner_distance+0.1*circularity
   if score>best_score:best_score=score;best=point
  return None if best is None else [round(float(best[0]),2),round(float(best[1]),2)]
 def find_gpu_green_logo(self,image,box):
  """Return the green NVIDIA logo centroid as a robust 180-degree cue."""
  region=np.zeros(image.shape[:2],np.uint8);cv2.fillPoly(region,[box],255)
  region=cv2.erode(region,np.ones((5,5),np.uint8))
  hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
  green=((region>0)&(hsv[:,:,0]>=35)&(hsv[:,:,0]<=95)&
         (hsv[:,:,1]>=55)&(hsv[:,:,2]>=40)).astype(np.uint8)*255
  green=cv2.morphologyEx(
   green,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3)))
  green=cv2.morphologyEx(
   green,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
  contours,_=cv2.findContours(green,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
  candidates=[c for c in contours if 15.0<=cv2.contourArea(c)<=1800.0]
  if not candidates:return None
  candidate=max(candidates,key=cv2.contourArea);moments=cv2.moments(candidate)
  if moments['m00']==0:return None
  return [round(float(moments['m10']/moments['m00']),2),
          round(float(moments['m01']/moments['m00']),2)]
 def stabilize(self,H,fx,fy,cx,cy):
  clusters=[]
  radii={'long_orange':60.,'gpu':45.,'hbm':45.,'black_block':40.,
         'marked_white':26.,'right_white_brown':18.}
  # Robot-state callback can clear history when a move is detected. Iterate a
  # snapshot because this node uses a multi-threaded executor.
  for frame_id,items in list(self.history):
   for d in items:
    if self.robot is not None and '_flange_pose' in d:
     current=np.array([self.robot.flange_x_cur_pos,self.robot.flange_y_cur_pos,
      self.robot.flange_z_cur_pos,self.robot.flange_a_cur_pos,
      self.robot.flange_b_cur_pos,self.robot.flange_c_cur_pos],float)
     source=np.asarray(d['_flange_pose'],float)
     translation_delta=np.abs(current[:3]-source[:3])
     rotation_delta=self.angular_abs_delta_deg(current[3:],source[3:])
     if (np.max(translation_delta)>self.a.history_pose_match_mm or
         np.max(rotation_delta)>self.a.history_pose_match_deg):
      continue
    radius=radii.get(d['part_type'],self.a.track_radius_px)
    point=np.array(d['reference_center_pixel'],float);best=None;distance=1e9
    for cluster in clusters:
     center=np.median(np.array(cluster['points']),axis=0)
     value=float(np.linalg.norm(point-center))
     if value<distance:best,distance=cluster,value
    if best is None or distance>radius:
     best={'part_type':d['part_type'],'display_name':d['display_name'],
           'points':[],'cameras':[],'angles':[],'sizes':[],'measured_sizes':[],'color_sizes':[],'dots':[],'marker_sources':[],
           'frames':set(),'scores':[]};clusters.append(best)
    if best['part_type']!=d['part_type']:
     same=[x for x in clusters if x['part_type']==d['part_type']]
     best=None;distance=1e9
     for cluster in same:
      value=float(np.linalg.norm(point-np.median(np.array(cluster['points']),axis=0)))
      if value<distance:best,distance=cluster,value
     if best is None or distance>radius:
      best={'part_type':d['part_type'],'display_name':d['display_name'],
            'points':[],'cameras':[],'angles':[],'sizes':[],'measured_sizes':[],'color_sizes':[],'dots':[],'marker_sources':[],
            'frames':set(),'scores':[]};clusters.append(best)
    best['points'].append(point);best['cameras'].append(d['camera_xyz_m'])
    best['angles'].append(d['angle_deg'])
    best['sizes'].append(d['bbox_size_px'])
    best['measured_sizes'].append(d.get('measured_bbox_size_px',d['bbox_size_px']))
    best['color_sizes'].append(d.get('color_bbox_size_px',d['bbox_size_px']))
    if d.get('reference_orientation_marker_pixel') is not None:
     best['dots'].append(d['reference_orientation_marker_pixel'])
     best['marker_sources'].append(d.get('orientation_marker_source','unknown'))
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
   entry={'part_type':cluster['part_type'],
    'display_name':cluster['display_name'],
    'center_pixel':[round(float(u),2),round(float(v),2)],
    'reference_center_pixel':[round(float(ref[0,0,0]),2),round(float(ref[0,0,1]),2)],
    'angle_deg':round(float(angle),2),'depth_m':round(z,6),
    'bbox_size_px':np.round(np.median(np.asarray(cluster['sizes'],float),axis=0),2).tolist(),
    'measured_bbox_size_px':np.round(
     np.median(np.asarray(cluster['measured_sizes'],float),axis=0),2).tolist(),
    'color_bbox_size_px':np.round(
     np.median(np.asarray(cluster['color_sizes'],float),axis=0),2).tolist(),
    'camera_xyz_m':np.round(camera,6).tolist(),
    'observation_frames':hits,
    'median_cad_area_match_score':round(float(np.median(cluster['scores'])),3)}
   required_dot_hits=max(self.a.min_stable_hits,int(np.ceil(hits*.5)))
   if len(cluster['dots'])>=required_dot_hits:
    dot_ref=np.median(np.asarray(cluster['dots'],float),axis=0).astype(np.float32).reshape(1,1,2)
    dot=cv2.perspectiveTransform(dot_ref,H)[0,0]
    entry['orientation_marker_pixel']=[round(float(dot[0]),2),round(float(dot[1]),2)]
    if cluster['marker_sources']:
     entry['orientation_marker_source']=max(
      set(cluster['marker_sources']),key=cluster['marker_sources'].count)
    entry['directed_angle_deg']=self.directed_angle(
     entry['angle_deg'],entry['center_pixel'],entry['orientation_marker_pixel'])
   stable.append(entry)
  limits={item['part_spec_id']:item['expected_count'] for item in self.bins}
  selected=[]
  for part in limits:
   group=[d for d in stable if d['part_type']==part]
   group.sort(key=lambda d:(d['observation_frames'],
                            d['median_cad_area_match_score']),reverse=True)
   selected.extend(group[:limits[part]])
  stable=selected
  # The two GPU slots are laid out left-to-right in the tray.  Sorting them
  # by Y first made nearly level GPUs swap their instance numbers whenever a
  # one-pixel measurement fluctuation changed their vertical order.
  stable.sort(key=lambda d:(
   d['part_type'],
   d['reference_center_pixel'][0] if d['part_type']=='gpu' else d['reference_center_pixel'][1],
   d['reference_center_pixel'][1] if d['part_type']=='gpu' else d['reference_center_pixel'][0]))
  counts={}
  for d in stable:
   counts[d['part_type']]=counts.get(d['part_type'],0)+1
   d['instance_index']=counts[d['part_type']]
  return stable
 def add_base_coordinates(self,result):
  if self.robot is None or time.monotonic()-self.robot_time>self.a.max_robot_state_age_sec:
   return 'NO_FRESH_ROBOT_STATE'
  if time.monotonic()-self.last_robot_motion_time<self.a.robot_settle_sec:
   return 'ROBOT_SETTLING'
  if len(self.pose_history)<self.a.robot_stable_samples:return 'ROBOT_STABILITY_PENDING'
  poses=np.asarray(self.pose_history)
  translation_span=float(np.max(np.ptp(poses[:,:3],axis=0)))
  # Unwrap each Euler component before measuring span so the equivalent
  # +180/-180 representation does not look like a 360-degree robot move.
  unwrapped_deg=np.rad2deg(np.unwrap(np.deg2rad(poses[:,3:]),axis=0))
  rotation_span=float(np.max(np.ptp(unwrapped_deg,axis=0)))
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
   # Convert the image long-axis direction to Base XY. Image x/y follow the
   # optical-frame x/y axes; fx/fy remove unequal pixel scaling. The result is
   # an unoriented rectangular axis (period 180 degrees).
   image_angle=np.deg2rad(float(detection['angle_deg']))
   camera_axis=np.array([np.cos(image_angle)/float(self.info.k[0]),
                         np.sin(image_angle)/float(self.info.k[4]),0.0])
   base_axis=T_base_camera[:3,:3]@camera_axis
   detection['long_axis_angle_base_deg']=round(float(np.degrees(
    np.arctan2(base_axis[1],base_axis[0]))),3)
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
  raw_debug=image.copy() if self.a.debug_image is not None else None
  self.last=now
  if self.a.registration_mode=='fixed_view':
   # Identity ROIs are valid only at the explicitly saved tray-view flange
   # pose. Disable detections immediately when the eye-in-hand camera moves.
   H=None;matches=inliers=0
   if self.robot is not None:
    current=np.array([self.robot.flange_x_cur_pos,self.robot.flange_y_cur_pos,
     self.robot.flange_z_cur_pos,self.robot.flange_a_cur_pos,
     self.robot.flange_b_cur_pos,self.robot.flange_c_cur_pos],float)
    position_error=float(np.max(np.abs(current[:3]-self.fixed_view_pose[:3])))
    rotation_error=float(np.max(self.angular_abs_delta_deg(current[3:],self.fixed_view_pose[3:])))
    if (position_error<=self.fixed_position_tolerance_mm and
        rotation_error<=self.fixed_rotation_tolerance_deg):
     H=self.fixed_view_homography.astype(np.float32)
  else:
   # SIFT is the dominant 1080p cost. Refresh tray registration at a lower
   # rate and reuse the recent transform for the faster object/overlay loop.
   if now-self.last_registration_attempt>=1.0/self.a.registration_hz:
    self.last_registration_attempt=now
    candidate,matches,inliers=self.register(image)
    self.cached_matches=matches;self.cached_inliers=inliers
    if candidate is not None:
     self.cached_homography=candidate;self.cached_registration_time=now
   H=(self.cached_homography if
      now-self.cached_registration_time<=self.a.registration_timeout_sec else None)
   matches=self.cached_matches;inliers=self.cached_inliers
  fx,fy,cx,cy=self.info.k[0],self.info.k[4],self.info.k[2],self.info.k[5]
  state=('TRACKING_FIXED_VIEW' if self.a.registration_mode=='fixed_view' else 'TRACKING') if H is not None else 'NOT_REGISTERED'
  if state!=self.registration_state:
   self.get_logger().info(f'Tray state={state}, matches={matches}, inliers={inliers}')
   self.registration_state=state
  result={'schema_version':1,'mode':'tray_detection_dry_run',
          # ROS time can have a different epoch. Keep wall time so motion
          # helpers can safely reject an old saved target.
          'timestamp_unix':time.time(),'timestamp_ros_ns':self.stamp(m),'tray_registration':state,
          'registration_matches':matches,'registration_inliers':inliers,'detections':[]}
  result['reference_to_live_homography']=(
   np.round(H,10).tolist() if H is not None else None)
  self.gpu_diagnostics=[]
  if H is None:
   cv2.putText(image,'TRAY NOT REGISTERED - DETECTIONS DISABLED',(35,55),
               cv2.FONT_HERSHEY_SIMPLEX,.85,(0,0,255),3,cv2.LINE_AA)
  else:
   mode='FIXED VIEW' if self.a.registration_mode=='fixed_view' else f'SIFT inliers={inliers}'
   cv2.putText(image,f'TRAY TRACKING ({mode}) - DETECTION ENABLED',(35,55),
               cv2.FONT_HERSHEY_SIMPLEX,.72,(0,220,0),3,cv2.LINE_AA)
  if H is not None:
   inverse=np.linalg.inv(H)
   for item in self.bins:
    if self.a.only_part_type and item['part_spec_id']!=self.a.only_part_type:continue
    found,poly,floor=self.find(item,fx,fy,cx,cy,H,image);part=item['part_spec_id'];color=COLORS[part]
    cv2.polylines(image,[poly],True,color,3)
    for n,d in enumerate(found,1):
     contour=d.pop('_contour')
     fitted_box=d.pop('_fitted_box')
     if part=='gpu':
      if self.a.resolve_gpu_orientation:
       # Orientation is intentionally opt-in.  A single-frame logo/dot
       # candidate is never drawn because it flickers as highlights change.
       # Only its temporally stable median is rendered below.
       dot=self.find_gpu_orientation_dot(image,fitted_box)
       if dot is not None:
        d['white_dot_candidate_pixel']=dot
       logo=self.find_gpu_green_logo(image,fitted_box)
       if logo is not None:
        d['orientation_marker_pixel']=logo
        d['orientation_marker_source']='green_logo'
        d['directed_angle_deg']=self.directed_angle(
         d['angle_deg'],d['center_pixel'],d['orientation_marker_pixel'])
      # Never draw the raw GPU contour/center. Its segmentation boundary is
      # intentionally permissive and moves with reflections. The stable CAD
      # box is drawn after temporal filtering below.
     else:
      cv2.drawContours(image,[contour],-1,color,3)
      u,v=map(int,d['center_pixel']);cv2.drawMarker(image,(u,v),color,cv2.MARKER_CROSS,22,3)
      cv2.putText(image,f'{part} {n} {d["angle_deg"]:.0f}deg',(u+8,v-8),
                  cv2.FONT_HERSHEY_SIMPLEX,.48,color,2)
     d.update(part_type=part,display_name=item['display_name'],instance_index=n)
     point=np.float32([[d['center_pixel']]])
     ref=cv2.perspectiveTransform(point,inverse)[0,0]
     d['reference_center_pixel']=[round(float(ref[0]),2),round(float(ref[1]),2)]
     if d.get('orientation_marker_pixel') is not None:
      dot=np.float32([[d['orientation_marker_pixel']]])
      dot_ref=cv2.perspectiveTransform(dot,inverse)[0,0]
      d['reference_orientation_marker_pixel']=[round(float(dot_ref[0]),2),
                                                round(float(dot_ref[1]),2)]
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
  result['gpu_candidate_diagnostics']=self.gpu_diagnostics
  result['stable_detected_total']=len(result['stable_detections'])
  result['base_transform_status']=self.add_base_coordinates(result) if H is not None else 'TRAY_NOT_REGISTERED'
  result['robot_motion_authorized']=False
  for d in result['stable_detections']:
   u,v=map(int,d['center_pixel']);cv2.circle(image,(u,v),14,(255,255,255),2)
   if d['part_type']=='gpu':
    # Draw the temporally median box, never the jittering single-frame box.
    size=np.asarray(d['bbox_size_px'],dtype=float)
    box=np.rint(cv2.boxPoints(((float(u),float(v)),tuple(size),float(d['angle_deg'])))).astype(np.int32)
    cv2.polylines(image,[box],True,COLORS['gpu'],3)
    cv2.drawMarker(image,(u,v),COLORS['gpu'],cv2.MARKER_CROSS,24,3)
    cv2.putText(image,f'GPU #{d["instance_index"]} stable',(u+12,v-12),
                cv2.FONT_HERSHEY_SIMPLEX,.52,COLORS['gpu'],2)
    if self.a.resolve_gpu_orientation and d.get('orientation_marker_pixel') is not None:
     marker=tuple(np.rint(d['orientation_marker_pixel']).astype(int))
     cv2.arrowedLine(image,(u,v),marker,(0,255,0),3,cv2.LINE_AA,tipLength=.3)
     cv2.circle(image,marker,7,(0,255,0),2,cv2.LINE_AA)
     cv2.putText(image,f'dir {d["directed_angle_deg"]:.1f}deg',(u+12,v+42),
                 cv2.FONT_HERSHEY_SIMPLEX,.48,(0,255,0),2,cv2.LINE_AA)
   cv2.putText(image,f'S{d["observation_frames"]}',(u+10,v+18),
               cv2.FONT_HERSHEY_SIMPLEX,.42,(255,255,255),2)
  self.a.output_json.parent.mkdir(parents=True,exist_ok=True)
  tmp=self.a.output_json.with_suffix('.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2));tmp.replace(self.a.output_json)
  ok,jpg=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,self.a.jpeg_quality])
  if ok:
   out=CompressedImage();out.header=m.header;out.format='jpeg';out.data=jpg.tobytes();self.pub.publish(out)
  if self.a.debug_image is not None and now-self.last_debug_write>=1.0:
   self.a.debug_image.parent.mkdir(parents=True,exist_ok=True)
   cv2.imwrite(str(self.a.debug_image),image,[cv2.IMWRITE_JPEG_QUALITY,95])
   raw_path=self.a.debug_image.with_name(
    f'{self.a.debug_image.stem}_raw{self.a.debug_image.suffix}')
   cv2.imwrite(str(raw_path),raw_debug,[cv2.IMWRITE_JPEG_QUALITY,95])
   self.last_debug_write=now

def main():
 root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser()
 p.add_argument('--layout',type=Path,default=root/'config/tray_layout.json')
 p.add_argument('--specs',type=Path,default=root/'config/part_specs_candidate.json')
 p.add_argument('--output-json',type=Path,default=root/'data/tray_detections_last.json')
 p.add_argument('--debug-image',type=Path,
                help='Optional one-frame-per-second detector overlay for diagnosis')
 p.add_argument('--handeye-file',type=Path,default=root.parents[0]/'calibration/data/handeye_result.json')
 p.add_argument('--color-topic',default='/camera/camera/color/image_raw/compressed')
 p.add_argument('--depth-topic',default='/camera/camera/aligned_depth_to_color/image_raw')
 p.add_argument('--info-topic',default='/camera/camera/color/camera_info')
 p.add_argument('--output-topic',default='/vision/tray/detections_image/compressed')
 p.add_argument('--feature-band-px',type=int,default=70);p.add_argument('--registration-scale',type=float,default=.4)
 p.add_argument('--registration-mode',choices=('sift','fixed_view'),default='sift',
                help='fixed_view requires returning to the saved tray-overview teaching pose')
 p.add_argument('--fixed-view-pose-file',type=Path,
                default=root/'config/tray_view_pose.json')
 p.add_argument('--only-part-type',choices=tuple(COLORS),
                help='detect and draw only one class; use gpu for the current GPU pick test')
 p.add_argument('--resolve-gpu-orientation',action='store_true',
                help='opt-in GPU 180-degree direction estimation; normal detection skips it')
 p.add_argument('--jpeg-quality',type=int,default=95,
                help='quality of the annotated compressed image (70-100)')
 p.add_argument('--ratio-test',type=float,default=.72);p.add_argument('--min-matches',type=int,default=14)
 p.add_argument('--min-inliers',type=int,default=10);p.add_argument('--ransac-px',type=float,default=4.)
 p.add_argument('--min-scale-area',type=float,default=.18);p.add_argument('--max-scale-area',type=float,default=3.)
 p.add_argument('--process-hz',type=float,default=2.);p.add_argument('--max-sync-ms',type=float,default=120.)
 p.add_argument('--registration-hz',type=float,default=1.0,
                help='SIFT tray-registration refresh rate; cached H is used between updates')
 p.add_argument('--registration-timeout-sec',type=float,default=1.5,
                help='discard cached tray registration after this many seconds without success')
 p.add_argument('--min-height-mm',type=float,default=.8);p.add_argument('--max-height-threshold-mm',type=float,default=3.5)
 p.add_argument('--gpu-dark-threshold',type=int,default=85,
                help='deprecated compatibility option; GPU now uses HSV/LAB thresholds')
 p.add_argument('--gpu-hsv-v-max',type=int,default=125,
                help='maximum HSV value for the black GPU body')
 p.add_argument('--gpu-lab-l-max',type=int,default=130,
                help='maximum LAB lightness for the black GPU body')
 p.add_argument('--gpu-min-raised-ratio',type=float,default=.35,
                help='minimum fraction physically raised above the tray')
 p.add_argument('--gpu-min-dark-ratio',type=float,default=.30,
                help='minimum black-body fraction inside a raised GPU candidate')
 p.add_argument('--gpu-min-geometry-area-ratio',type=float,default=.20,
                help='minimum raised-depth area relative to projected GPU area')
 p.add_argument('--gpu-min-area-ratio',type=float,default=.35)
 p.add_argument('--gpu-max-area-ratio',type=float,default=2.2)
 p.add_argument('--gpu-box-scale',type=float,default=1.07,
                help='empirical projection correction for the measured 57x27 mm GPU')
 p.add_argument('--min-area-ratio',type=float,default=.06);p.add_argument('--max-area-ratio',type=float,default=5.0)
 p.add_argument('--history-frames',type=int,default=40);p.add_argument('--min-stable-hits',type=int,default=4)
 p.add_argument('--track-radius-px',type=float,default=16.)
 p.add_argument('--robot-state-topic',default='/nonrt_state_data')
 p.add_argument('--robot-stable-samples',type=int,default=5)
 p.add_argument('--max-robot-state-age-sec',type=float,default=1.)
 p.add_argument('--robot-stream-gap-sec',type=float,default=.5)
 p.add_argument('--max-robot-sample-jump-mm',type=float,default=5.)
 p.add_argument('--max-robot-sample-jump-deg',type=float,default=1.)
 p.add_argument('--robot-motion-delta-mm',type=float,default=.05)
 p.add_argument('--robot-motion-delta-deg',type=float,default=.02)
 p.add_argument('--robot-settle-sec',type=float,default=1.5)
 p.add_argument('--max-robot-translation-span-mm',type=float,default=.25)
 p.add_argument('--max-robot-rotation-span-deg',type=float,default=.05)
 p.add_argument('--history-pose-match-mm',type=float,default=.5)
 p.add_argument('--history-pose-match-deg',type=float,default=.1)
 p.add_argument('--homography-smoothing-frames',type=int,default=7)
 a=p.parse_args()
 if not 70<=a.jpeg_quality<=100:p.error('--jpeg-quality must be between 70 and 100')
 if a.process_hz<=0 or a.registration_hz<=0 or a.registration_timeout_sec<=0:
  p.error('process/registration rates and timeout must be positive')
 rclpy.init();node=Detector(a);executor=MultiThreadedExecutor(num_threads=2)
 executor.add_node(node)
 try:executor.spin()
 except KeyboardInterrupt:pass
 finally:
  executor.shutdown()
  node.destroy_node()
  if rclpy.ok():rclpy.shutdown()
if __name__=='__main__':main()
