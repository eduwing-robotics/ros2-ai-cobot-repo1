# HBM 조립체 디지털 트윈

FR5, Unity 디지털 트윈, ROS2/MoveIt, MainServer와 PostgreSQL을 연결해 HBM 조립체의 Mock 조립과 생산·검사 기록을 다루는 작업 공간입니다.

기능 목표와 현재 범위는 [프로젝트 개요](overview.md) 한 문서에서 관리하고, 미구현 작업은 [TODO](TODO.md)에서 관리합니다.

## 필요 환경

| 항목 | 버전·패키지 | 비고 |
| --- | --- | --- |
| OS | Ubuntu 24.04 | ROS2 실행 PC |
| Unity | 6000.3.21f1 | `UnityDT/` 프로젝트 |
| ROS2 / MoveIt | ROS2 Jazzy / MoveIt2 | `rosdep`으로 패키지 설치 |
| Python | 3.12 / `python3-psycopg` | MainServer와 DB bridge |
| 빌드 | `python3-colcon-common-extensions` | ROS2 workspace 빌드 |
| PostgreSQL | 버전 고정 없음 | Mock DB와 Real production DB |
| FAIRINO SDK | `libfairino` 2.3.7 | Real 전용, FR5 기본 IP `192.168.58.2` |

## 최초 1회 설정

### ROS2 workspace

```bash
sudo apt update
sudo apt install python3-colcon-common-extensions python3-rosdep python3-psycopg postgresql postgresql-client
sudo rosdep init  # 이미 초기화했으면 생략
rosdep update

cd /home/codlab/Main_Unity/Farino_AIO
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
```

### Unity ROS Endpoint

```bash
cd /home/codlab/Main_Unity/Ros2UnityEndopoint_PKG
ROS_SETUP=/home/codlab/Main_Unity/Farino_AIO/install/setup.bash ./install.sh
```

### Mock DB

```bash
cd /home/codlab/Main_Unity
sudo -u postgres createuser "$USER"
sudo -u postgres createdb --owner="$USER" main_unity_mock_test
psql -v ON_ERROR_STOP=1 -d main_unity_mock_test -f DATA_STATION/DB/production_schema.sql
psql -v ON_ERROR_STOP=1 -d main_unity_mock_test -f DATA_STATION/DB/004_mock_seed.sql
```

Unity Hub에서 `UnityDT/`를 Unity 6000.3.21f1로 한 번 열어 패키지를 복원합니다.

## 실행

Unity에서 `SampleScene`을 열고 Play 전에 `RobotMaster`의 Mock 또는 Real Backend를 선택합니다. **Robotics > ROS Settings**는 ROS2, Endpoint PC 실제 IP, 포트 `10000`으로 설정합니다.

### Mock

```bash
cd /home/codlab/Main_Unity
source /opt/ros/jazzy/setup.bash
source Farino_AIO/install/setup.bash
source Ros2UnityEndopoint_PKG/install/local_setup.bash

export ROS_DOMAIN_ID=5
export PRODUCTION_DB_DSN='dbname=main_unity_mock_test'
export MAIN_SERVER_DB_DSN='dbname=main_unity_mock_test'
export MAIN_SERVER_SCRIPT="$PWD/MAIN_SERVER/server.py"

ros2 launch mock_db_mvp launch_mock.launch.py \
  endpoint_ip:=0.0.0.0 endpoint_port:=10000
```

MoveIt, RViz, Mock 조립, DB bridge, Unity Endpoint와 MainServer가 함께 실행됩니다.

### Real

MoveIt:

```bash
cd /home/codlab/Main_Unity/Farino_AIO
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=5
ros2 launch fairino5_v6_moveit2_config real_robot.launch.py
```

Unity Endpoint:

```bash
cd /home/codlab/Main_Unity/Ros2UnityEndopoint_PKG
ROS_SETUP=/home/codlab/Main_Unity/Farino_AIO/install/setup.bash ./run.sh
```

FAIRINO 상태·수동 명령 서버:

```bash
cd /home/codlab/Main_Unity/Farino_AIO
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=5
ros2 run fairino_hardware_v3_9_7 ros2_cmd_server
```

MainServer:

```bash
cd /home/codlab/Main_Unity
source /opt/ros/jazzy/setup.bash
source Farino_AIO/install/setup.bash
export ROS_DOMAIN_ID=5
export MAIN_SERVER_MODE=real
export MAIN_SERVER_DB_DSN='host=DB_HOST dbname=DB_NAME user=READ_ONLY_USER password=PASSWORD'
python3 MAIN_SERVER/server.py
```

현재 Real MainServer는 DB 조회만 가능하며 Real 자동조립 node는 미구현입니다.

## 구성

- `UnityDT/` — Unity 작업 화면, 조립 Scenario와 Mock/Real backend 선택
- `MAIN_SERVER/` — 제품·재고·작업 조회와 조립 실행 HTTP API
- `Farino_AIO/` — FR5 MoveIt, Mock 조립 노드와 DB bridge
- `Ros2UnityEndopoint_PKG/` — Unity와 ROS2 연결 패키지
- `DATA_STATION/DB/` — PostgreSQL 스키마, 기준정보와 권한 SQL

## 기준 문서

- [프로젝트 기능 목표와 현재 상태](overview.md)
- [작업 계획](TODO.md)
- [현재 시스템 구조](UnityDT/Docs/Architecture.md)
- [ISA-95 기준 현재 구조](UnityDT/Docs/ISA95-Current.md)
- [Unity ↔ ROS2 API](docs/API.md)
- [MainServer HTTP API](MAIN_SERVER/Main_serverAPI.md)
- [production 핵심 DB 설계](UnityDT/Docs/DB.md)
- [조립 레시피 규격](UnityDT/Docs/Recipe.md)
