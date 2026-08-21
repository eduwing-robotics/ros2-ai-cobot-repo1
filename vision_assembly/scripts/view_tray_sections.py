#!/usr/bin/env python3
"""Track a fixed planar tray and draw registered section polygons."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from collections import deque
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage

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
  if self.ref_desc is None or len(self.ref_kp)<args.min_matches:
   raise RuntimeError('Not enough reference tray features')
  self.pub=self.create_publisher(CompressedImage,args.output_topic,qos_profile_sensor_data)
  self.create_subscription(CompressedImage,args.input_topic,self.on_image,qos_profile_sensor_data)
  self.get_logger().info(f'Tray registration reference: {ref_path}')
  self.get_logger().info(f'Reference features: {len(self.ref_kp)}; no robot commands are sent')

 def reference_points(self,item,inset=True):
  p=np.array([[round(x*self.ref_w),round(y*self.ref_h)]
              for x,y in item['section_polygon_normalized']],np.int32)
  if inset:
   c=p.astype(float).mean(axis=0);gap=max(4,round(min(self.ref_w,self.ref_h)*.0045))
   p[:,0]+=np.where(p[:,0]<c[0],gap,-gap);p[:,1]+=np.where(p[:,1]<c[1],gap,-gap)
  return p

 def register(self,gray):
  small=cv2.resize(gray,None,fx=self.scale,fy=self.scale,interpolation=cv2.INTER_AREA)
  kp,desc=self.sift.detectAndCompute(small,None)
  if desc is None:return None,0,0
  pairs=self.matcher.knnMatch(self.ref_desc,desc,k=2)
  good=[a for a,b in pairs if a.distance<self.args.ratio_test*b.distance]
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
  area=abs(cv2.contourArea(moved));ratio=area/(self.ref_w*self.ref_h)
  if not self.args.min_scale_area<=ratio<=self.args.max_scale_area:
   return None,len(good),count
  self.homography_corners.append(moved)
  smooth=np.median(np.asarray(self.homography_corners),axis=0).astype(np.float32)
  full=cv2.getPerspectiveTransform(corners[0].astype(np.float32),smooth)
  return full,len(good),count

 def on_image(self,msg):
  image=cv2.imdecode(np.frombuffer(msg.data,np.uint8),cv2.IMREAD_COLOR)
  if image is None:return
  H,matches,inliers=self.register(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY))
  state='TRACKING' if H is not None else 'NOT_REGISTERED'
  if state!=self.last_state:
   self.get_logger().info(f'Tray state={state}, matches={matches}, inliers={inliers}')
   self.last_state=state
  if H is None:
   cv2.putText(image,f'TRAY NOT REGISTERED  matches={matches} inliers={inliers}',
               (35,55),cv2.FONT_HERSHEY_SIMPLEX,.9,(0,0,255),3,cv2.LINE_AA)
  else:
   cv2.putText(image,f'TRAY TRACKING  inliers={inliers}',(35,55),
               cv2.FONT_HERSHEY_SIMPLEX,.8,(0,220,0),3,cv2.LINE_AA)
   for item in self.config['bins']:
    ref=self.reference_points(item).astype(np.float32).reshape(-1,1,2)
    points=np.rint(cv2.perspectiveTransform(ref,H)[:,0,:]).astype(np.int32)
    color=COLORS.get(item['bin_id'],(255,255,255))
    cv2.polylines(image,[points],True,color,4,cv2.LINE_AA)
    label=f"{item['display_name'].split(' (')[0]} x{item['expected_count']}"
    x=int(points[:,0].min())+12;y=int(points[:,1].max())-18
    (tw,th),base=cv2.getTextSize(label,cv2.FONT_HERSHEY_SIMPLEX,.65,2)
    cv2.rectangle(image,(x-7,y-th-7),(x+tw+7,y+base+7),(20,20,20),-1)
    cv2.putText(image,label,(x,y),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),2,cv2.LINE_AA)
  ok,jpg=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,88])
  if ok:
   out=CompressedImage();out.header=msg.header;out.format='jpeg';out.data=jpg.tobytes();self.pub.publish(out)

def main():
 root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser()
 p.add_argument('--config',type=Path,default=root/'config/tray_layout_candidate.json')
 p.add_argument('--input-topic',default='/camera/camera/color/image_raw/compressed')
 p.add_argument('--output-topic',default='/vision/tray/sections_image/compressed')
 p.add_argument('--feature-band-px',type=int,default=70)
 p.add_argument('--registration-scale',type=float,default=.4)
 p.add_argument('--smoothing-frames',type=int,default=5)
 p.add_argument('--ratio-test',type=float,default=.72);p.add_argument('--min-matches',type=int,default=14)
 p.add_argument('--min-inliers',type=int,default=10);p.add_argument('--ransac-px',type=float,default=4.)
 p.add_argument('--min-scale-area',type=float,default=.18);p.add_argument('--max-scale-area',type=float,default=3.0)
 a=p.parse_args();rclpy.init();node=Viewer(a)
 try:rclpy.spin(node)
 except KeyboardInterrupt:pass
 finally:
  node.destroy_node()
  if rclpy.ok():rclpy.shutdown()
if __name__=='__main__':main()
