# Farino_AIO

FR5 MoveIt 구성과 Mock 로봇 backend를 포함하는 ROS2 workspace입니다.
조립 요청과 PostgreSQL 쓰기는 최상단 `ASSEMBLY_SEQUENCER`가 소유합니다.

## 현재 기능

- MoveIt 기반 Mock 수동 이동과 고정 레시피 Pick·Place
- `/unity/assembly/start` 서비스와 `/unity/assembly/feedback` 토픽
- 실행 중 중복 조립·수동 명령 차단
- AssemblySequencer DB Writer를 통한 Job·Unit·재고·검사 기록
- Mock 검사 PASS/FAIL 확률과 seed 설정

## Mock 올인원 실행

`launch_mock.launch.py` 하나가 MoveIt, RViz, FakeSystem controller, Mock 조립
노드, AssemblySequencer, Unity ROS TCP endpoint와 MainServer를 같은 Mock DB로
실행합니다. 먼저 AssemblySequencer를 빌드하고 그 install을 source해 호환
`mock_db_mvp` 패키지를 빌드합니다.

```bash
cd /home/codlab/Main_Unity
source /opt/ros/jazzy/setup.bash
source Farino_AIO/install/setup.bash
cd ASSEMBLY_SEQUENCER
colcon build --symlink-install
source install/setup.bash

cd ../Farino_AIO
colcon build --symlink-install --packages-select mock_db_mvp
source install/setup.bash

cd ..
source ASSEMBLY_SEQUENCER/install/setup.bash
source Ros2UnityEndopoint_PKG/install/local_setup.bash
export PRODUCTION_DB_DSN='dbname=main_unity_mock_test'
export MAIN_SERVER_DB_DSN='dbname=main_unity_mock_test'
export MAIN_SERVER_SCRIPT="$PWD/MAIN_SERVER/server.py"
ros2 launch mock_db_mvp launch_mock.launch.py \
  endpoint_ip:=0.0.0.0 endpoint_port:=10000
```

Unity의 **Robotics > ROS Settings**에서 ROS2를 선택하고 ROS IP에는 이 PC의
실제 IP, ROS Port에는 `10000`을 입력합니다. `endpoint_ip:=0.0.0.0`은 수신
주소이며 Unity 접속 주소가 아닙니다. 실제 IP는 `ip -br -4 address`로
확인합니다.

```bash
curl http://127.0.0.1:8000/api/v1/health
ros2 service call /unity/assembly/start fairino_msgs/srv/RemoteCmdInterface \
  "{cmd_str: '{\"command\":\"status\"}'}"
ros2 topic echo --once /joint_states
```

정상 초기 상태는 MainServer health의 `runtime_mode: mock`, 조립 서비스의
`state: IDLE`, `/joint_states` 수신입니다. 전체 종료는 launch를 실행한
터미널에서 `Ctrl+C` 한 번으로 처리합니다.

## 문서

- [프로젝트 기능 목표](../overview.md)
- [작업 계획](../TODO.md)
- [Unity ↔ ROS2 API](../docs/API.md)
- [현재 시스템 구조](../UnityDT/Docs/Architecture.md)
- [DB 핵심 설계](../UnityDT/Docs/DB.md)
