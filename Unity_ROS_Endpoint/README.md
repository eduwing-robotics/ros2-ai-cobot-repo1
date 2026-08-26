# Unity ↔ ROS2 Endpoint 패키지

다른 PC의 Unity와 FR5 MoveIt PC를 TCP로 연결하기 위한 전송용 패키지입니다.

```text
Unity PC ── TCP :10000 ──> ROS-TCP Endpoint ── ROS2 DDS ──> MoveIt / 로봇 드라이버
```

## 포함 내용

- `src/ROS-TCP-Endpoint`: Unity Technologies 공식 ROS2 Endpoint 소스
- `src/fr5_unity_endpoint`: FR5 MoveIt과 Endpoint를 함께 실행하는 launch 패키지
- `build.sh`: 의존성 설치 및 colcon 빌드
- `run_endpoint.sh`: Endpoint만 실행
- `run_fr5_with_endpoint.sh`: FR5 MoveIt과 Endpoint를 함께 실행

공식 소스 기준:

- 저장소: <https://github.com/Unity-Technologies/ROS-TCP-Endpoint>
- 브랜치: `main-ros2`
- 태그: `ROS2v0.7.0`
- 커밋: `54c1a64b6d5ef6ffa0a0431570bb74329b79b15b`

공식 소스의 저작권과 라이선스는 `src/ROS-TCP-Endpoint/LICENSE`를 따릅니다.

## 준비 사항

Endpoint PC:

- Ubuntu 24.04
- ROS2 Jazzy
- `rosdep`, `colcon`
- 통합 실행 시 빌드된 `fr5_moveit_mvp`와 그 MoveIt 의존 패키지

Unity PC:

- Unity ROS-TCP-Connector 패키지
- Endpoint PC와 통신 가능한 동일 네트워크

## 다른 PC로 복사

압축 파일을 Endpoint/MoveIt PC로 복사한 뒤 실행합니다.

```bash
tar -xzf Unity_ROS_Endpoint.tar.gz
cd Unity_ROS_Endpoint
```

## 최초 1회 빌드

ROS2 Jazzy와 rosdep이 설치되어 있어야 합니다. rosdep을 처음 사용하는 PC라면 먼저 초기화합니다.

```bash
sudo rosdep init
rosdep update
```

이미 초기화되어 있다면 `sudo rosdep init`은 생략합니다.

MoveIt 워크스페이스가 별도로 있다면 `ROS_SETUP`에 해당 setup 파일을 지정합니다.

```bash
ROS_SETUP=/path/to/FR5_MOVEIT/install/setup.bash ./build.sh
```

Endpoint만 사용할 경우 MoveIt workspace source 없이 빌드할 수 있습니다. `fr5_unity_endpoint` 의존성 경고가 발생하면 다음처럼 Endpoint만 선택해 빌드합니다.

```bash
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src/ROS-TCP-Endpoint --ignore-src -r -y
colcon build --symlink-install --packages-select ros_tcp_endpoint
```

## 실행 방법

### Endpoint만 실행

```bash
./run_endpoint.sh
```

기본 수신 주소는 `0.0.0.0`, 포트는 `10000`입니다.

### FR5 MoveIt과 Endpoint 통합 실행

빌드할 때 MoveIt workspace를 `ROS_SETUP`으로 지정했다면 생성된 setup 파일에 underlay가 기록됩니다.

```bash
./run_fr5_with_endpoint.sh
```

주소와 포트를 바꾸려면 launch argument를 전달합니다.

```bash
./run_fr5_with_endpoint.sh endpoint_ip:=192.168.0.25 endpoint_port:=10000
```

종료는 `Ctrl+C`입니다. 통합 launch로 시작된 MoveIt과 Endpoint가 함께 종료됩니다.

## Unity 설정

Unity의 `ROSConnection` 또는 `Robotics > ROS Settings`에서 다음을 설정합니다.

```text
Protocol: ROS2
ROS IP Address: Endpoint PC의 실제 LAN IP
ROS Port: 10000
Connect On Start: 활성화
```

예를 들어 Endpoint PC가 `192.168.0.25`라면 Unity에는 `192.168.0.25`를 입력합니다. `0.0.0.0`은 서버가 모든 로컬 인터페이스에서 수신한다는 뜻이며 Unity의 접속 주소로 사용하지 않습니다.

## 연결 확인

Endpoint PC에서:

```bash
ros2 node list
ss -ltn 'sport = :10000'
ros2 topic echo /joint_states --once
```

정상 상태에서는 `/UnityEndpoint` 노드가 보이고 TCP `10000` 포트가 LISTEN 상태여야 합니다. `/joint_states`는 Endpoint가 생성하지 않으므로 로봇 드라이버나 `joint_state_broadcaster`가 발행해야 합니다.

## 방화벽

Unity PC가 다른 장비라면 Endpoint PC의 TCP `10000` 포트를 Unity PC 또는 내부망에만 허용합니다.

```bash
sudo ufw allow from 192.168.0.0/24 to any port 10000 proto tcp
```

실제 네트워크 대역에 맞게 주소를 변경하십시오.

## 문제 해결

- Unity 연결 거부: Endpoint 실행 여부, IP, TCP `10000` 방화벽 확인
- `/UnityEndpoint`가 없음: workspace `install/setup.bash`를 source했는지 확인
- MoveIt 패키지를 찾지 못함: FR5 MoveIt workspace를 먼저 source한 뒤 빌드/실행
- Unity는 연결됐지만 로봇이 움직이지 않음: `/joint_states` 이름과 `j1`~`j6` 순서 확인
- 다른 ROS2 PC의 토픽이 안 보임: 양쪽 `ROS_DOMAIN_ID`와 DDS 네트워크 확인

## 공식 문서

- ROS-TCP-Endpoint: <https://github.com/Unity-Technologies/ROS-TCP-Endpoint>
- Unity ROS–Unity Integration: <https://github.com/Unity-Technologies/Unity-Robotics-Hub/blob/main/tutorials/ros_unity_integration/setup.md>
- ROS2 Jazzy Launch: <https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Launch/Launch-system.html>
