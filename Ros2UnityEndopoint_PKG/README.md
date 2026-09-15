# Ros2UnityEndopoint_PKG · Unity ↔ ROS 2 통신 다리

> Unity 애플리케이션과 ROS 2 로봇 소프트웨어가 서로 메시지를 주고받을 수 있게 중계하는 ROS 2 패키지입니다.

## 역할

Unity는 C#으로 동작하는 게임 엔진이고, 로봇 소프트웨어는 ROS 2라는 별도의 통신 체계를 씁니다. 둘은 서로의 말을 직접 알아듣지 못합니다. 이 패키지는 그 사이에서 **통역사** 역할을 합니다.

- Unity와 TCP 연결을 맺고 끊습니다.
- Unity가 보낸 메시지를 ROS 2 토픽·서비스로 전달하고, 반대 방향도 전달합니다.
- 연결 오류와 전송 실패를 알립니다.

통역사가 대화 내용을 바꾸지 않듯, Endpoint는 **메시지 내용을 해석하지 않습니다.** 요청 접수를 작업 완료로 바꾸거나, 연결이 복구됐다고 작업이 재개됐다고 판단하지 않습니다.

## 구조

```mermaid
flowchart LR
    U["UnityDT<br/>ROS-TCP Connector (C#)"] <-->|"TCP :10000"| E["ROS-TCP Endpoint<br/>(Python ROS 2 노드)"]
    E <-->|"ROS 2 토픽·서비스"| R["Assembly Sequencer<br/>로봇·카메라 노드"]
```

| 용어 | 설명 |
|---|---|
| **토픽 (topic)** | 한쪽이 계속 방송하고 여러 쪽이 듣는 방식. 예: 로봇 관절 상태 |
| **서비스 (service)** | 요청을 보내고 응답을 받는 방식. 예: 조립 시작 요청 |
| **ROS domain** | 같은 번호끼리만 통신하는 채널. 이 프로젝트는 Mock `42`, Real `5` |

## 기술 스택

ROS 2 Jazzy · Python · Unity [ROS-TCP-Endpoint](src/ROS-TCP-Endpoint) (Unity Technologies 오픈소스 기반) · colcon

## 폴더 구조

```text
Ros2UnityEndopoint_PKG/
├── src/ROS-TCP-Endpoint/   # Endpoint ROS 2 패키지
├── install.sh              # 이 패키지 단독 빌드
└── run.sh                  # 필요 시 자동 재빌드 후 실행
```

## 설치 및 실행

전체 시스템에서는 [최상단 실행 절차](../README.md#실행)의 `assembly_mock` / `assembly_real` 런치가 Endpoint를 함께 시작합니다. 단독으로 실행할 때만 아래를 사용합니다.

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

## 관련 문서

- [공개 API 목록](../README.md#공개-api)
- [UnityDT](../UnityDT/README.md)
