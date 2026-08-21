# KSMC ROS 2 Workspace

현재 워크스페이스에는 AI/Vision 서버 기반이 들어 있다.

- `vision_interfaces`: 검출·검사·상태용 ROS 2 메시지
- `vision_server`: 카메라 입력 정리, YOLO 검출, 조립 검사, Mock 검증

패키지 이름에는 팀명 접두사를 반복하지 않고, 노드와 토픽은 기능을 바로 알 수
있는 설명적인 이름을 사용한다. 상세 내용은
`src/vision_server/README.md`를 참고한다.

## 빌드

```bash
cd <repository>/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

## 실행

```bash
./run_vision.sh
```

장비 없는 검사:

```bash
./run_vision_mock.sh pass
./run_vision_mock.sh missing_hbm
```
