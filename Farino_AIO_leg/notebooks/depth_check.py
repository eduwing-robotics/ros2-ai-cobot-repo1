#!/usr/bin/env python3
# 카메라 노드(ros2 launch realsense2_camera rs_launch.py)가 떠 있는 상태에서 실행할 것.

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import numpy as np

rclpy.init()
node = Node('depth_quick_check')
result = {}


def cb(msg):
    # depth 토픽은 16UC1(픽셀당 2바이트, mm 단위 정수) 인코딩이라
    # uint16 배열로 그대로 해석하면 각 픽셀 = 그 지점까지의 거리(mm)
    result['arr'] = np.frombuffer(msg.data, dtype=np.uint16).reshape(msg.height, msg.width)


sub = node.create_subscription(Image, '/camera/camera/depth/image_rect_raw', cb, 1)
while 'arr' not in result:
    rclpy.spin_once(node, timeout_sec=0.2)

arr = result['arr']
nonzero = arr[arr > 0]

# min/max는 반사면 등에서 튀는 노이즈 값 하나에도 크게 흔들리므로,
# 중앙값(median)과 5~95 퍼센타일(상하위 5%를 잘라낸 범위)을 같이 확인한다.
p5, p95 = np.percentile(nonzero, [5, 95])
print(f"무효(0) 비율: {100 * (arr == 0).sum() / arr.size:.1f}%")
print(f"min={nonzero.min()}mm max={nonzero.max()}mm (노이즈에 민감, 참고용)")
print(f"median={np.median(nonzero):.0f}mm  5~95 퍼센타일 범위={p5:.0f}~{p95:.0f}mm (신뢰 가능한 대표값)")

node.destroy_node()
rclpy.shutdown()

