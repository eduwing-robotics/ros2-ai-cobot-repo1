#!/usr/bin/env python3
"""Depth-assisted four-hole board tracking. Publishes diagnostics; never moves robot."""
import argparse,itertools,json,time
from pathlib import Path
import cv2,numpy as np,rclpy
from fairino_msgs.msg import RobotNonrtState
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from scipy.spatial.transform import Rotation,Slerp
from sensor_msgs.msg import CameraInfo,CompressedImage,Image
from std_msgs.msg import String

def tf(r,t):
 o=np.eye(4);o[:3,:3]=r;o[:3,3]=t;return o

class Tracker(Node):
 def __init__(self,a):
  super().__init__('board_pose_3d');self.a=a;self.K=self.depth=self.robot=None;self.ds=None;self.filt=None;self.last=0
  p=json.loads(a.handeye.read_text());h=p.get('camera_to_flange') or p['best']['camera_to_flange'];self.Tfc=tf(np.array(h['rotation_matrix']),np.array(h['translation_m']))
  p=json.loads(a.holes.read_text());self.ref=np.array(p['hole_centers_pixel'],np.float32);self.rad=np.array(p['hole_radii_pixel']);self.obj=np.array(p['hole_centers_board_mm'])/1000
  self.slots={s['slot_code']:s for s in json.loads(a.slots.read_text())['slots']};self.selected=a.target
  residual=json.loads(a.residual.read_text());self.residual_base_m=np.asarray(residual['residual_base_mm'],float)/1000.0
  self.pub=self.create_publisher(String,a.status,10);self.ppub=self.create_publisher(PoseStamped,a.pose,10)
  self.create_subscription(CameraInfo,a.info,lambda m:setattr(self,'K',np.array(m.k).reshape(3,3)),qos_profile_sensor_data)
  self.create_subscription(Image,a.depth,self.depth_cb,qos_profile_sensor_data);self.create_subscription(CompressedImage,a.color,self.color_cb,qos_profile_sensor_data)
  self.create_subscription(RobotNonrtState,a.robot,lambda m:setattr(self,'robot',m),10);self.create_subscription(String,a.selection,self.select_cb,10)
  self.get_logger().info('DRY RUN ONLY: publishes 3D board/slot poses; sends no motion')
 def select_cb(self,m):
  c=m.data.strip().upper().replace('_','-')
  if c in self.slots:self.selected=c
 def depth_cb(self,m):
  if m.encoding not in ('16UC1','mono16'):return
  self.depth=np.ndarray((m.height,m.width),np.uint16,buffer=m.data,strides=(m.step,2)).copy();self.ds=m.header.stamp.sec+m.header.stamp.nanosec*1e-9
 def find_holes(self,img):
  g=cv2.GaussianBlur(cv2.cvtColor(img,cv2.COLOR_BGR2GRAY),(5,5),1.2);groups=[];half=80
  for ref,r0 in zip(self.ref,self.rad):
   x,y=np.rint(ref).astype(int);x0=max(0,x-half);y0=max(0,y-half);cs=cv2.HoughCircles(g[y0:y+half+1,x0:x+half+1],cv2.HOUGH_GRADIENT,1,10,param1=90,param2=12,minRadius=5,maxRadius=18)
   if cs is None:return
   q=[]
   for cx,cy,r in cs[0]:
    c=np.array([x0+cx,y0+cy]);d=np.linalg.norm(c-ref);re=abs(r-r0)
    if d<=70 and re<=8:q.append((c,d,re))
   if not q:return
   groups.append(q[:8])
  best=None
  for z in itertools.product(*groups):
   q=np.array([v[0] for v in z],np.float32);sh=q-self.ref;score=np.sum((sh-np.median(sh,0))**2)+.5*sum(v[2]**2 for v in z)
   if best is None or score<best[0]:best=(score,q)
  q=best[1];rat=np.linalg.norm(q-np.roll(q,-1,0),axis=1)/np.linalg.norm(self.ref-np.roll(self.ref,-1,0),axis=1)
  return q if np.ptp(rat)<.045 and .92<np.mean(rat)<1.08 else None
 def solve(self,h):
  H,W=self.depth.shape;uv=[];zs=[]
  for c,r in zip(h,self.rad):
   outer=max(16,r+9);inner=max(8,r+2);xs=np.arange(max(0,int(c[0]-outer)),min(W,int(c[0]+outer)+1));ys=np.arange(max(0,int(c[1]-outer)),min(H,int(c[1]+outer)+1));xx,yy=np.meshgrid(xs,ys);rr=np.hypot(xx-c[0],yy-c[1]);z=self.depth[yy,xx]*.001;ok=(rr>=inner)&(rr<=outer)&(z>.2)&(z<.5);uv.append(np.c_[xx[ok],yy[ok]]);zs.append(z[ok])
  uv=np.vstack(uv);z=np.hstack(zs)
  if len(z)<200:raise ValueError('insufficient_depth')
  cloud=np.c_[(uv[:,0]-self.K[0,2])*z/self.K[0,0],(uv[:,1]-self.K[1,2])*z/self.K[1,1],z];keep=np.ones(len(z),bool)
  for _ in range(4):
   cen=np.median(cloud[keep],0);_,_,v=np.linalg.svd(cloud[keep]-cen,full_matrices=False);n=v[-1];e=abs((cloud-cen)@n);keep=e<=max(.0025,3*1.4826*np.median(e[keep]))
  cen=np.mean(cloud[keep],0);_,_,v=np.linalg.svd(cloud[keep]-cen,full_matrices=False);n=v[-1];n=n if n[2]<0 else -n;inv=np.linalg.inv(self.K);obs=[]
  for u,v in h:
   ray=inv@[u,v,1];obs.append(ray*(n@cen)/(n@ray))
  obs=np.array(obs);src=np.c_[self.obj,np.zeros(4)];sc=src.mean(0);oc=obs.mean(0);u,_,v=np.linalg.svd((src-sc).T@(obs-oc));R=v.T@u.T
  if np.linalg.det(R)<0:v[-1]*=-1;R=v.T@u.T
  T=tf(R,oc-R@sc);err=np.linalg.norm((R@src.T).T+T[:3,3]-obs,axis=1);return T,err,cloud,keep,cen,n
 def invalid(self,why):self.pub.publish(String(data=json.dumps({'schema':'fr5.vision.board_pose_3d/v1','valid':False,'dry_run':True,'robot_motion_authorized':False,'reason':why})))
 def color_cb(self,m):
  if self.K is None or self.depth is None or self.robot is None:return
  stamp_ns=m.header.stamp.sec*1000000000+m.header.stamp.nanosec
  stamp=stamp_ns*1e-9
  if abs(stamp-self.ds)>.25:return
  img=cv2.imdecode(np.frombuffer(m.data,np.uint8),1)
  if img is None or img.shape[:2]!=self.depth.shape:return
  h=self.find_holes(img)
  if h is None:self.invalid('four_holes_not_found');return
  try:Tcb,err,cloud,keep,cen,n=self.solve(h)
  except Exception as e:self.invalid(str(e));return
  s=self.robot;Tbf=tf(Rotation.from_euler('xyz',[s.flange_a_cur_pos,s.flange_b_cur_pos,s.flange_c_cur_pos],degrees=True).as_matrix(),np.array([s.flange_x_cur_pos,s.flange_y_cur_pos,s.flange_z_cur_pos])/1000);cur=Tbf@self.Tfc@Tcb
  if self.filt is None:self.filt=cur
  else:self.filt=tf(Slerp([0,1],Rotation.from_matrix([self.filt[:3,:3],cur[:3,:3]]))([.25]).as_matrix()[0],.75*self.filt[:3,3]+.25*cur[:3,3])
  slots={c:{'surface_base_mm':((self.filt@[v['x_mm']/1000,v['y_mm']/1000,0,1])[:3]+self.residual_base_m).tolist()} for c,v in self.slots.items()};slots={c:{'surface_base_mm':(np.array(v['surface_base_mm'])*1000).tolist()} for c,v in slots.items()}
  out={'schema':'fr5.vision.board_pose_3d/v1','valid':True,'timestamp_ros_ns':stamp_ns,'coordinate_frame':'base_link','product_code':self.a.product_code,'product_version':self.a.product_version,'dry_run':True,'robot_motion_authorized':False,'selected_slot':self.selected,'hole_fit_error_mm':(err*1000).tolist(),'hole_fit_rms_mm':float(np.sqrt(np.mean(err**2))*1000),'plane_inliers':int(keep.sum()),'plane_samples':len(keep),'plane_residual_mad_mm':float(np.median(abs((cloud-cen)@n))*1000),'T_base_board':self.filt.tolist(),'slots':slots,'accuracy_status':'validation_required; do not execute robot motion'};self.pub.publish(String(data=json.dumps(out,separators=(',',':'))))
  if self.selected in slots:
   p=PoseStamped();p.header.stamp=m.header.stamp;p.header.frame_id='base_link';x=np.array(slots[self.selected]['surface_base_mm'])/1000;p.pose.position.x,p.pose.position.y,p.pose.position.z=x;q=Rotation.from_matrix(self.filt[:3,:3]).as_quat();p.pose.orientation.x,p.pose.orientation.y,p.pose.orientation.z,p.pose.orientation.w=q;self.ppub.publish(p)
  if time.monotonic()-self.last>.5:self.a.output.parent.mkdir(parents=True,exist_ok=True);self.a.output.write_text(json.dumps(out,indent=2));self.last=time.monotonic()

def main():
 root=Path(__file__).resolve().parents[2];p=argparse.ArgumentParser();p.add_argument('--color',default='/camera/camera/color/image_raw/compressed');p.add_argument('--depth',default='/camera/camera/aligned_depth_to_color/image_raw');p.add_argument('--info',default='/camera/camera/color/camera_info');p.add_argument('--robot',default='/nonrt_state_data');p.add_argument('--selection',default='/vision/board/selected_target');p.add_argument('--status',default='/vision/board/pose_3d/status');p.add_argument('--pose',default='/vision/board/target_surface_pose_3d');p.add_argument('--target',default='HBM-01');p.add_argument('--product-code',default='printed_semiconductor_package_board');p.add_argument('--product-version',default='assembly-r1');p.add_argument('--handeye',type=Path,default=root/'calibration/data/handeye_result.json');p.add_argument('--holes',type=Path,default=root/'vision_assembly/config/assembly_board_holes.json');p.add_argument('--slots',type=Path,default=root/'vision_assembly/config/assembly_slots_r1.json');p.add_argument('--residual',type=Path,default=root/'vision_assembly/config/assembly_placecamera_residual.json');p.add_argument('--output',type=Path,default=root/'vision_assembly/data/board_pose_3d_live.json');a=p.parse_args();rclpy.init();n=Tracker(a)
 try:rclpy.spin(n)
 except KeyboardInterrupt:pass
 finally:n.destroy_node();rclpy.shutdown() if rclpy.ok() else None
if __name__=='__main__':main()
