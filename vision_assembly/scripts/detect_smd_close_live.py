#!/usr/bin/env python3
"""Publish live SMD-section corners and configured close-view OBBs; never moves the robot."""
import argparse,json,time
from pathlib import Path
import cv2,numpy as np,rclpy
from fairino_msgs.msg import RobotNonrtState
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String
from ultralytics import YOLO
from smd_set_selection import select_smd_set

class CloseSmdDetector(Node):
 def __init__(self,a):
  super().__init__('smd_close_live_detector');self.a=a;self.cfg=json.loads(a.config.read_text());self.ref=np.asarray(self.cfg['reference_tcp_base'],float);self.source_size=np.asarray(self.cfg['source_image_size'],float);self.size=tuple(map(int,self.cfg['canonical_size']));self.model=YOLO(str(a.model));self.robot=None;self.last=0.
  obb=self.cfg['obb_detection'];self.set_layout=self.cfg['set_layout'];self.layout_capacity=int(self.set_layout['required_count']);self.required_count=int(self.set_layout['parts_per_set']);self.set_index=int(a.set_index)
  if int(obb['required_count'])!=self.layout_capacity:raise RuntimeError('OBB count and SMD layout capacity disagree')
  self.pub=self.create_publisher(String,a.output_topic,10);self.create_subscription(RobotNonrtState,a.robot_topic,self.robot_cb,10);self.create_subscription(CompressedImage,a.color_topic,self.image_cb,qos_profile_sensor_data);self.get_logger().info('SMD close live detector ready')
 def robot_cb(self,m):self.robot=m
 def at_reference(self):
  if self.robot is None or int(self.robot.robot_motion_done)!=1:return False
  s=self.robot;pose=np.asarray([s.cart_x_cur_pos,s.cart_y_cur_pos,s.cart_z_cur_pos,s.cart_a_cur_pos,s.cart_b_cur_pos,s.cart_c_cur_pos],float)
  pos=np.max(np.abs(pose[:3]-self.ref[:3]));ang=np.max(np.abs((pose[3:]-self.ref[3:]+180.)%360.-180.))
  return pos<=self.a.position_tolerance_mm and ang<=self.a.angle_tolerance_deg
 def publish(self,q):m=String();m.data=json.dumps(q,separators=(',',':'));self.pub.publish(m)
 def image_cb(self,m):
  now=time.monotonic()
  if now-self.last<1./self.a.process_hz:return
  self.last=now
  if not self.at_reference():self.publish({'valid':False,'at_smd_view':False,'timestamp_unix':time.time()});return
  image=cv2.imdecode(np.frombuffer(m.data,np.uint8),cv2.IMREAD_COLOR)
  if image is None:return
  scale=np.asarray([image.shape[1],image.shape[0]],np.float32)/self.source_size.astype(np.float32);section=np.asarray(self.cfg['section_polygon_pixel'],np.float32)*scale;width,height=self.size;dst=np.float32([[0,0],[width-1,0],[width-1,height-1],[0,height-1]]);H=cv2.getPerspectiveTransform(section,dst);inv=np.linalg.inv(H);rect=cv2.warpPerspective(image,H,(width,height),flags=cv2.INTER_CUBIC)
  pred=self.model.predict(rect,imgsz=self.a.image_size,conf=self.a.confidence,device=self.a.device,verbose=False)[0];total_count=0 if pred.obb is None else len(pred.obb)
  items=[{'box':b,'center':b.mean(0),'confidence':float(c)} for b,c in zip(pred.obb.xyxyxyxy.cpu().numpy(),pred.obb.conf.cpu().numpy())]
  try:ordered=select_smd_set(items,self.set_layout,self.set_index)
  except RuntimeError as exc:
   self.publish({'valid':False,'at_smd_view':True,'count':0,'required_count':self.required_count,'total_count':total_count,'set_index':self.set_index,'reason':str(exc),'timestamp_unix':time.time()});return
  detections=[]
  for index,item in enumerate(ordered,1):
   box=cv2.perspectiveTransform(item['box'].astype(np.float32).reshape(-1,1,2),inv)[:,0];detections.append({'instance_index':index,'polygon_source_pixel':np.round(box,2).tolist(),'confidence':round(item['confidence'],4)})
  self.publish({'valid':True,'at_smd_view':True,'timestamp_unix':time.time(),'section_polygon_source_pixel':np.round(section,2).tolist(),'count':len(detections),'required_count':self.required_count,'total_count':total_count,'layout_capacity':self.layout_capacity,'set_index':self.set_index,'detections':detections})

def main():
 root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--config',type=Path,default=root/'config/smd_section_view.json');p.add_argument('--model',type=Path,default=root/'models/smd_obb/pilot_03/weights/best.pt');p.add_argument('--color-topic',default='/camera/camera/color/image_raw/compressed');p.add_argument('--robot-topic',default='/nonrt_state_data');p.add_argument('--output-topic',default='/vision/smd/close_overlay_state');p.add_argument('--process-hz',type=float,default=2.);p.add_argument('--confidence',type=float,default=.5);p.add_argument('--image-size',type=int,default=960);p.add_argument('--device',default='0');p.add_argument('--position-tolerance-mm',type=float,default=2.);p.add_argument('--angle-tolerance-deg',type=float,default=1.)
 p.add_argument('--set-index',type=int,choices=(1,2),default=1);a=p.parse_args();rclpy.init();node=CloseSmdDetector(a)
 try:rclpy.spin(node)
 except KeyboardInterrupt:pass
 finally:
  node.destroy_node()
  if rclpy.ok():rclpy.shutdown()
if __name__=='__main__':main()
