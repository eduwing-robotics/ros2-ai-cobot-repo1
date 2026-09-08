# Ros2UnityEndopoint_PKG

Unity와 ROS 2 사이의 메시지 전송을 담당하는 ROS-TCP Endpoint 패키지입니다.

## 역할과 책임

- Unity TCP 연결 수립과 해제
- Unity 메시지와 ROS pub/sub/service 사이의 전달
- 연결 오류와 전송 실패 보고
- Endpoint 빌드·실행 진입점 제공

좌표 변환, 생산 상태, 조립 흐름, FAIRINO 드라이버와 로봇 제어는 소유하지 않습니다.

## 설계 경계

Endpoint는 전송 내용을 업무 상태로 해석하지 않습니다. 요청 수락을 완료로 바꾸거나, 연결 복구를 작업 재개로 판단하거나, 실패를 숨긴 기본값으로 대체하지 않습니다.

전송 방식이나 배포 위치가 바뀌더라도 송신자와 수신자의 공개 계약 및 완료 의미는 유지되어야 합니다.

## 설치 및 실행

필요 환경: Ubuntu 24.04, ROS 2 Jazzy, `python3-colcon-common-extensions`

Endpoint는 Unity가 ROS 2 토픽·서비스를 사용하게 하는 브리지입니다. 실제 로봇 상태를 발행하고 제어하는 FAIRINO 드라이버와 `fr_command_server`를 대체하지 않습니다.

다른 PC에서 만든 `build`, `install`, `log`는 복사하거나 재사용하지 말고 로봇 PC에 소스만 옮깁니다. `run.sh`가 `~/.bashrc`를 불러오고, 설치가 없거나 복사됐거나 소스보다 오래됐으면 자동으로 다시 빌드한 뒤 실행합니다.

```bash
cd Ros2UnityEndopoint_PKG
chmod +x run.sh
./run.sh
```

`~/.bashrc`에 FAIRINO workspace의 `install/setup.bash`가 등록되어 있으면 자동으로 사용합니다. 자동 감지가 안 될 때만 FAIRINO setup을 지정합니다.

```bash
ROS_SETUP=~/fairino_ws/install/setup.bash ./run.sh
```

`fairino_msgs`가 없으면 Endpoint 단독 모드로 빌드하고 경고합니다.

기본 주소는 `0.0.0.0:10000`입니다. 변경할 때만 다음처럼 실행합니다.

```bash
ROS_IP=0.0.0.0 ROS_TCP_PORT=10000 ./run.sh
```

Unity의 **Robotics > ROS Settings**에서 ROS 2를 선택하고, ROS IP에는 이 PC의 실제 IP를, 포트에는 `10000`을 입력합니다.

## 문서

- [공개 API 목록](../docs/API.md)
