#!/usr/bin/env python3
"""Detect an object standing above the ChArUco/table plane using aligned depth."""

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, CompressedImage, Image
from fairino_msgs.msg import RobotNonrtState
from scipy.spatial.transform import Rotation

from charuco_common import detect_charuco, detector_parameters, load_config


class Detector(Node):
    def __init__(self, args):
        super().__init__("detect_object_height_dry_run")
        self.args=args; self.bridge=CvBridge()
        self.config,self.dictionary,self.board=load_config(); self.parameters=detector_parameters()
        self.k=None; self.d=None; self.depth=None; self.depth_stamp=None; self.results=[]; self.robot=None
        result=json.loads(args.result_file.read_text(encoding="utf-8"))["best"]
        self.euler_convention=result["euler_convention"]
        handeye=result["camera_to_flange"]
        self.t_flange_camera=np.eye(4); self.t_flange_camera[:3,:3]=np.asarray(handeye["rotation_matrix"]); self.t_flange_camera[:3,3]=np.asarray(handeye["translation_m"])
        self.create_subscription(CameraInfo,self.config["camera_info_topic"],self.info_cb,qos_profile_sensor_data)
        self.create_subscription(Image,args.depth_topic,self.depth_cb,qos_profile_sensor_data)
        self.create_subscription(CompressedImage,self.config["image_topic"],self.color_cb,qos_profile_sensor_data)
        self.create_subscription(RobotNonrtState,self.config["robot_state_topic"],self.robot_cb,10)
        self.get_logger().info("DRY RUN: table-relative RGB-D object height; no robot motion")

    @staticmethod
    def stamp(m): return m.header.stamp.sec+m.header.stamp.nanosec*1e-9
    def info_cb(self,m): self.k=np.asarray(m.k,float).reshape(3,3); self.d=np.asarray(m.d,float)
    def robot_cb(self,m): self.robot=m
    def depth_cb(self,m):
        x=self.bridge.imgmsg_to_cv2(m,"passthrough").astype(np.float32)
        self.depth=x*0.001 if m.encoding in ("16UC1","mono16") else x
        self.depth_stamp=self.stamp(m)

    def color_cb(self,m):
        if self.k is None or self.depth is None or self.robot is None or abs(self.stamp(m)-self.depth_stamp)>.2:return
        im=self.bridge.compressed_imgmsg_to_cv2(m,"bgr8")
        if im.shape[:2]!=self.depth.shape:return
        gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
        mc,mi,cc,ci,_=detect_charuco(gray,self.dictionary,self.board,self.parameters,self.k,self.d)
        if ci is None or len(ci)<12:return
        pose_ok,rvec,tvec=cv2.aruco.estimatePoseCharucoBoard(cc,ci,self.board,self.k,self.d,None,None)
        if not pose_ok:return
        pts=cc.reshape(-1,2); x,y,w,h=cv2.boundingRect(np.rint(pts).astype(np.int32))
        pad=int(max(w,h)*.18); x0=max(0,x-pad); y0=max(0,y-pad); x1=min(im.shape[1],x+w+pad); y1=min(im.shape[0],y+h+pad)
        yy,xx=np.mgrid[y0:y1,x0:x1]; z=self.depth[y0:y1,x0:x1]
        valid=np.isfinite(z)&(z>.15)&(z<2.0)
        if valid.sum()<1000:return
        # Robust pixel-plane fit; lower-depth object pixels are removed iteratively.
        A=np.c_[xx[valid],yy[valid],np.ones(valid.sum())]; b=z[valid]
        keep=np.ones(len(b),bool)
        for _ in range(4):
            coef=np.linalg.lstsq(A[keep],b[keep],rcond=None)[0]
            residual=b-A@coef
            med=np.median(residual[keep]); mad=np.median(np.abs(residual[keep]-med))+1e-6
            keep=np.abs(residual-med)<max(.003,3.5*mad)
        plane=coef[0]*xx+coef[1]*yy+coef[2]
        height=plane-z
        mask=(valid&(height>=self.args.min_height_mm/1000)&(height<=self.args.max_height_mm/1000)).astype(np.uint8)*255
        mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
        mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((7,7),np.uint8))
        n,labels,stats,cents=cv2.connectedComponentsWithStats(mask)
        candidates=[i for i in range(1,n) if stats[i,cv2.CC_STAT_AREA]>=self.args.min_area_px]
        if not candidates:return
        i=max(candidates,key=lambda q:stats[q,cv2.CC_STAT_AREA]); sel=labels==i
        core=cv2.erode(sel.astype(np.uint8),np.ones((5,5),np.uint8)).astype(bool)
        if core.sum()<50:core=sel
        heights=height[core]; u=float(cents[i][0]+x0); v=float(cents[i][1]+y0)
        object_z=float(np.median(z[core])); table_z=float(np.median(plane[core]))
        xyz=np.array([(u-self.k[0,2])*object_z/self.k[0,0],(v-self.k[1,2])*object_z/self.k[1,1],object_z])
        s=self.robot; tbf=np.eye(4)
        tbf[:3,:3]=Rotation.from_euler(self.euler_convention,[s.flange_a_cur_pos,s.flange_b_cur_pos,s.flange_c_cur_pos],degrees=True).as_matrix()
        tbf[:3,3]=np.asarray([s.flange_x_cur_pos,s.flange_y_cur_pos,s.flange_z_cur_pos])/1000.0
        base=(tbf@self.t_flange_camera@np.r_[xyz,1.0])[:3]
        rcb,_=cv2.Rodrigues(rvec); tcb=np.eye(4); tcb[:3,:3]=rcb; tcb[:3,3]=np.asarray(tvec).reshape(3)
        tbb=tbf@self.t_flange_camera@tcb; normal=tbb[:3,2]; origin=tbb[:3,3]
        if abs(normal[2])<0.5:return
        table_base_z=origin[2]-(normal[0]*(base[0]-origin[0])+normal[1]*(base[1]-origin[1]))/normal[2]
        self.results.append((xyz,(table_z-object_z)*1000,float(np.percentile(heights,90)*1000),stats[i,cv2.CC_STAT_AREA],u,v,base,table_base_z))
        if len(self.results) in (1,5,10,20,self.args.frames):self.get_logger().info(f"Stable object frames: {len(self.results)}/{self.args.frames}")
        if len(self.results)>=self.args.frames:
            a=np.asarray([r[0] for r in self.results])*1000; heights=np.asarray([r[1] for r in self.results]); h90=np.asarray([r[2] for r in self.results]); uv=np.asarray([[r[4],r[5]] for r in self.results])
            print("\nRGB-D OBJECT HEIGHT DRY RUN - ROBOT DID NOT MOVE")
            print("Object center pixel median:",np.round(np.median(uv,0),1).tolist())
            print("Object Camera XYZ median [mm]:",np.round(np.median(a,0),3).tolist())
            print(f"Height above plane median/min/max [mm]: {np.median(heights):.3f}/{heights.min():.3f}/{heights.max():.3f}")
            print(f"Height 90th-percentile median [mm]: {np.median(h90):.3f}")
            print("Component area median [px]:",int(np.median([r[3] for r in self.results])))
            base=np.asarray([r[6] for r in self.results])*1000.0; base_med=np.median(base,axis=0)
            table_z_base=float(np.median([r[7] for r in self.results])*1000.0)
            object_top_registered_z=table_z_base+self.args.registered_height_mm
            approach=np.array([base_med[0],base_med[1],object_top_registered_z+self.args.approach_offset_mm])
            print("Object top Base XYZ median [mm]:",np.round(base_med,3).tolist())
            print(f"Registered part height [mm]: {self.args.registered_height_mm:.3f}")
            print(f"ChArUco table plane Base Z at object [mm]: {table_z_base:.3f}")
            print("Safe approach TCP/Base XYZ [mm]:",np.round(approach,3).tolist())
            rclpy.shutdown()


def main():
    default_result = Path(__file__).resolve().parents[1] / "data/handeye_result.json"
    p=argparse.ArgumentParser(); p.add_argument("--frames",type=int,default=30); p.add_argument("--min-height-mm",type=float,default=5); p.add_argument("--max-height-mm",type=float,default=25); p.add_argument("--min-area-px",type=int,default=80); p.add_argument("--depth-topic",default="/camera/camera/aligned_depth_to_color/image_raw"); p.add_argument("--registered-height-mm",type=float,default=10.0); p.add_argument("--approach-offset-mm",type=float,default=100.0); p.add_argument("--result-file",type=Path,default=default_result); a=p.parse_args()
    rclpy.init(); n=Detector(a)
    try:rclpy.spin(n)
    except KeyboardInterrupt:pass
    finally:
        n.destroy_node()
        if rclpy.ok():rclpy.shutdown()

if __name__=="__main__":main()
