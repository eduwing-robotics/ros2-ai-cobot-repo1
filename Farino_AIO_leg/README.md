# FAIRINO Chapter 11-14 Integrated Workspace

중복 패키지 없이 Chapter 11~14를 하나로 합친 워크스페이스입니다.

```bash
colcon build
source install/setup.bash
```

- Chapter 12 mock MoveIt/RViz: `ros2 launch fairino5_v6_moveit2_config demo.launch.py`
- Chapter 13 실물 Digital Twin: `ros2 launch fairino5_v6_moveit2_config real_robot.launch.py`
- Chapter 11 Python API 서버: `ros2 launch fairino5_v6_moveit2_config ch11_python_control.launch.py`
- Chapter 14 카메라만: `ros2 launch fairino5_v6_moveit2_config ch14_vision.launch.py`
- Chapter 14 카메라 + 실물 API 서버: `ros2 launch fairino5_v6_moveit2_config ch14_vision.launch.py start_robot_api:=true`

`real_robot.launch.py`와 `start_robot_api:=true`는 실물 FR5에 연결합니다. mock 테스트에는 `demo.launch.py`를 사용하세요.

---

# FAIRINO Cobot Manipulation

FAIRINO FR5 협동로봇으로 배우는 로봇 제어 커리큘럼입니다. WebApp/Lua 기초 조작부터 ROS2, MoveIt2, Digital Twin, Vision 기반 Pick & Place까지 다룹니다.

에듀윙 로보틱스의 교육 과정 자료입니다.

전체 커리큘럼은 [에듀윙 로보틱스 홈페이지](https://eduwingrobotics.com)에서 확인하실 수 있습니다.

## 폴더 구조

- `src/` — ROS2(Jazzy) 패키지 소스 (fairino_hardware_v3_9_7, fairino_description, fairino5_v6_moveit2_config, fairino_msgs)
- `notebooks/` — Chapter 11(Python Control), Chapter 14(Vision) 관련 Python 스크립트

## 사전 준비

- ROS2 Jazzy
- FAIRINO FR5 협동로봇 실물 (또는 시뮬레이션 환경)
- Intel RealSense D435 (Chapter 14 Vision 파트)

## 빌드

```bash
colcon build
source install/setup.bash
```
