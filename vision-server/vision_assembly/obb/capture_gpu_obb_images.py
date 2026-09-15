#!/usr/bin/env python3
"""Capture sharp, spaced D435 frames for the GPU OBB dataset; no robot motion."""
import argparse
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage


class Capture(Node):
    def __init__(self, args):
        super().__init__('capture_gpu_obb_images')
        self.args=args;self.saved=0;self.last=0.0
        args.output.mkdir(parents=True,exist_ok=True)
        self.create_subscription(CompressedImage,args.topic,self.callback,qos_profile_sensor_data)
        self.get_logger().info(
            f'NO MOTION: saving up to {args.count} sharp frames from {args.topic}')

    def callback(self,message):
        now=time.monotonic()
        if now-self.last<self.args.interval_sec:return
        image=cv2.imdecode(np.frombuffer(message.data,np.uint8),cv2.IMREAD_COLOR)
        if image is None:return
        sharpness=float(cv2.Laplacian(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),cv2.CV_64F).var())
        if sharpness<self.args.min_sharpness:return
        stamp=time.strftime('%Y%m%d_%H%M%S')+f'_{message.header.stamp.nanosec:09d}'
        path=self.args.output/f'gpu_{stamp}.jpg'
        cv2.imwrite(str(path),image,[cv2.IMWRITE_JPEG_QUALITY,98])
        self.saved+=1;self.last=now
        self.get_logger().info(f'Saved {self.saved}/{self.args.count}: {path.name}, sharpness={sharpness:.1f}')
        if self.saved>=self.args.count:rclpy.shutdown()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--topic',default='/camera/camera/color/image_raw/compressed')
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'dataset/images/unlabeled')
    parser.add_argument('--count',type=int,default=20)
    parser.add_argument('--interval-sec',type=float,default=.7)
    parser.add_argument('--min-sharpness',type=float,default=20.0)
    args=parser.parse_args()
    if args.count<1 or args.interval_sec<=0:parser.error('invalid count/interval')
    rclpy.init();node=Capture(args)
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()


if __name__=='__main__':main()
