# Ros2UnityEndopoint_PKG

UnityDT와 ROS2/MoveIt workspace 사이의 ROS-TCP Endpoint 패키지입니다.

## 실행

필요 환경은 Ubuntu 24.04, ROS2 Jazzy와 `python3-colcon-common-extensions`입니다.

```bash
cd Ros2UnityEndopoint_PKG
chmod +x install.sh run.sh
./install.sh
./run.sh
```

기본 수신 주소는 `0.0.0.0:10000`입니다. Unity에는 Endpoint PC의 실제 LAN IP와 포트 `10000`을 설정합니다.

## 문서

- [상세 실행 방법](실행방법.md)
- [프로젝트 기능 목표](../overview.md)
- [Unity ↔ ROS2 API](../UnityDT/Docs/API.md)
- [작업 계획](../TODO.md)
