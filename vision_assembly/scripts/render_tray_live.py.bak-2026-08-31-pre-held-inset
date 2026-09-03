#!/usr/bin/env python3
import argparse,json,time
from pathlib import Path
import cv2,numpy as np,rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from rclpy.qos import HistoryPolicy,QoSProfile,ReliabilityPolicy
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String
COLORS={'black_block':(0,0,255),'long_orange':(0,165,255),'marked_white':(0,255,255),'right_white_brown':(0,200,0),'gpu':(255,80,0),'hbm':(220,0,220)}
class Renderer(Node):
 def __init__(self,a):
  super().__init__('tray_live_renderer');self.a=a;self.layout=json.loads(a.layout.read_text());self.bins=self.layout['bins']
  image=cv2.imread(self.layout['reference_image']);self.rh,self.rw=image.shape[:2]
  self.H=None;self.edge_corners=None;self.tracks={};self.counts={};self.last=0.
  qos=QoSProfile(history=HistoryPolicy.KEEP_LAST,depth=1,reliability=ReliabilityPolicy.BEST_EFFORT)
  self.pub=self.create_publisher(CompressedImage,a.output_topic,qos)
  self.create_subscription(CompressedImage,a.color_topic,self.image_cb,qos)
  self.create_subscription(String,a.registration_topic,self.registration_cb,10)
  self.create_subscription(String,a.overlay_topic,self.overlay_cb,10)
  self.get_logger().info('Independent live renderer ready')
 def ref_points(self,item):return np.array([[round(x*self.rw),round(y*self.rh)] for x,y in item['section_polygon_normalized']],np.float32)
 def registration_cb(self,m):
  try:
   q=json.loads(m.data)
   if q.get('state')!='TRACKING':self.H=None;self.edge_corners=None;self.tracks={};self.counts={};return
   H=np.asarray(q['homography_reference_to_image'],float)
   self.H=H if H.shape==(3,3) and np.all(np.isfinite(H)) else None
   corners=np.asarray(q.get('tray_edge_corners_image',[]),np.float32)
   self.edge_corners=corners if corners.shape==(4,2) else None
  except Exception:self.H=None;self.edge_corners=None;self.tracks={};self.counts={}
 def overlay_cb(self,m):
  try:
   q=json.loads(m.data)
   if not q.get('valid'):self.tracks={};self.counts={};return
   self.tracks={str(k):[np.asarray(c,np.float32).reshape(-1,1,2) for c in v] for k,v in q.get('tracks',{}).items()}
   self.counts={str(k):int(v) for k,v in q.get('counts',{}).items()}
  except Exception:self.tracks={};self.counts={}
 @staticmethod
 def marker(image,center):
  cv2.drawMarker(image,center,(0,0,0),cv2.MARKER_CROSS,7,3,cv2.LINE_AA);cv2.drawMarker(image,center,(255,255,255),cv2.MARKER_CROSS,7,1,cv2.LINE_AA)
 def image_cb(self,m):
  now=time.monotonic()
  if now-self.last<1./self.a.display_hz:return
  self.last=now;image=cv2.imdecode(np.frombuffer(m.data,np.uint8),cv2.IMREAD_COLOR)
  if image is None:return
  H=None if self.H is None else self.H.copy()
  if H is None:cv2.putText(image,'CAMERA MOVING / TRAY NOT REGISTERED',(25,50),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,0,255),2,cv2.LINE_AA)
  else:
   cv2.putText(image,'LIVE VIEW - DETECTION ENABLED',(25,42),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,220,0),2,cv2.LINE_AA)
   for part,contours in self.tracks.items():
    color=COLORS.get(part,(255,255,255));th=1 if part in ('right_white_brown','marked_white') else 2
    for ref in contours:
     contour=np.rint(cv2.perspectiveTransform(ref,H)).astype(np.int32);cv2.drawContours(image,[contour],-1,color,th,cv2.LINE_AA);mom=cv2.moments(contour)
     if abs(mom['m00'])>1e-6:self.marker(image,(round(mom['m10']/mom['m00']),round(mom['m01']/mom['m00'])))
   for item in self.bins:
    part=item['part_spec_id'];color=COLORS[part];poly=np.rint(cv2.perspectiveTransform(self.ref_points(item).reshape(-1,1,2),H)[:,0]).astype(np.int32)
    cv2.polylines(image,[poly],True,color,2,cv2.LINE_AA);label=f"{item['display_name'].split(' (')[0]} {self.counts.get(part,0)}/{item['expected_count']}"
    cv2.putText(image,label,(int(poly[:,0].min())+10,int(poly[:,1].max())-14),cv2.FONT_HERSHEY_SIMPLEX,.43,color,1,cv2.LINE_AA)
   if self.edge_corners is not None:
    for index,point in enumerate(np.rint(self.edge_corners).astype(int)):
     cv2.circle(image,tuple(point),6,(0,255,0),-1,cv2.LINE_AA)
     cv2.putText(image,str(index+1),tuple(point+np.array([8,-8])),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,255,0),1,cv2.LINE_AA)
  if self.a.display_scale!=1.:image=cv2.resize(image,None,fx=self.a.display_scale,fy=self.a.display_scale,interpolation=cv2.INTER_AREA)
  ok,jpg=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,self.a.jpeg_quality])
  if ok:
   out=CompressedImage();out.header=m.header;out.format='jpeg';out.data=jpg.tobytes();self.pub.publish(out)
def main():
 root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--layout',type=Path,default=root/'config/tray_layout_candidate.json');p.add_argument('--color-topic',default='/camera/camera/color/image_raw/compressed');p.add_argument('--registration-topic',default='/vision/tray/registration');p.add_argument('--overlay-topic',default='/vision/tray/detection_overlay_state');p.add_argument('--output-topic',default='/vision/tray/detections_image/compressed');p.add_argument('--display-hz',type=float,default=10.);p.add_argument('--display-scale',type=float,default=.75);p.add_argument('--jpeg-quality',type=int,default=75)
 a=p.parse_args();rclpy.init();node=Renderer(a)
 try:rclpy.spin(node)
 except (KeyboardInterrupt,ExternalShutdownException):pass
 finally:
  node.destroy_node()
  if rclpy.ok():rclpy.shutdown()
if __name__=='__main__':main()
