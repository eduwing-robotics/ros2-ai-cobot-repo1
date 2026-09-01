# Ros2UnityEndopoint_PKG

UnityDT와 로봇 PC의 ROS 2 사이를 연결하는 ROS-TCP Endpoint 패키지입니다. Endpoint는 브리지이며 FAIRINO 드라이버나 `fr_command_server`를 대체하지 않습니다.

## 역할과 책임

- 역할: Unity TCP 메시지와 ROS 2 pub/sub/service 사이의 전송 경계
- 책임: 연결 수립, 메시지 전달, Endpoint 실행·빌드 스크립트 제공
- 책임 아님: 좌표 변환 규칙, 조립 흐름, FAIRINO 드라이버와 로봇 제어

## 실행

필요 환경은 Ubuntu 24.04, ROS2 Jazzy와 `python3-colcon-common-extensions`입니다.
로봇 PC로 옮길 때는 소스만 복사하고 `build`, `install`, `log`는 복사·재사용하지 않습니다.

```bash
cd Ros2UnityEndopoint_PKG
chmod +x run.sh
./run.sh
```

`run.sh`가 `~/.bashrc`를 불러오고, 로컬 설치가 없거나 다른 PC에서 복사됐거나 소스보다 오래됐으면 자동으로 빌드합니다. FAIRINO workspace setup도 `~/.bashrc`에서 자동으로 사용합니다. 자동 감지가 안 될 때만 다음처럼 setup 경로를 지정합니다.

```bash
ROS_SETUP=~/fairino_ws/install/setup.bash ./run.sh
```

FAIRINO workspace가 없으면 `/opt/ros/jazzy/setup.bash`로 Endpoint만 빌드하고 경고합니다.

기본 수신 주소는 `0.0.0.0:10000`입니다. Unity에는 Endpoint PC의 실제 LAN IP와 포트 `10000`을 설정합니다.

## 문서

- [상세 실행 방법](실행방법.md)
