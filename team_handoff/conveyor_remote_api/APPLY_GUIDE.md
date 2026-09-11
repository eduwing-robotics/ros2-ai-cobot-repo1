# 적용 방법

## 1. 코드 받기와 빌드

원격 컨베이어 서버 구현이 포함된 Git branch를 받은 뒤 빌드한다.

```bash
cd ~/KSMC
git pull origin vision-robot-conveyor-control

source /opt/ros/jazzy/setup.bash
cd ~/KSMC/ros2_ws
colcon build --symlink-install --packages-select vision_interfaces vision_server
source install/setup.bash
export ROS_DOMAIN_ID=5
```

다음 실행 파일이 보여야 한다.

```bash
ros2 pkg executables vision_server | grep conveyor_remote_server
```

## 2. 장치별 실행 역할

### S22/비전 컴퓨터

```bash
~/KSMC/run_s22_conveyor_hq.sh
```

확인:

```bash
ros2 topic hz /vision/conveyor/stop_line_ready
ros2 topic echo /vision/conveyor/board_count
```

### FR5/Main Server

FR5 허가 토픽은 더 이상 필요하지 않다. 작업영역 이탈은 운용자/상위 시퀀서가 확인한다.

### 컨베이어 원격 서버 컴퓨터

먼저 monitor-only로 실행한다.

```bash
~/KSMC/run_conveyor_remote_server.sh --monitor-only
```

서비스가 보이는지 확인한다.

```bash
ros2 service list | grep '^/conveyor/'
ros2 topic echo /conveyor/state
```

실제 운전 준비와 현장 확인이 끝났을 때 monitor-only 서버를 종료하고 다음으로
실행한다.

```bash
~/KSMC/run_conveyor_remote_server.sh --execute --confirm-motion
```

서버를 ARMED로 실행해도 자동으로 움직이지 않는다. 이동 서비스 요청과 모든
interlock 통과가 필요하다.

### 서버와 S22를 한 번에 실행

컨베이어 서버와 S22 정지선/ROI를 같은 컴퓨터에서 함께 관리할 때는 다음
원커맨드 런처를 사용한다.

```bash
~/KSMC/run_conveyor_remote_server.sh --with-s22 --monitor-only
```

현장 운전 전환은 다음과 같다.

```bash
~/KSMC/run_conveyor_remote_server.sh --with-s22 --execute --confirm-motion
```

이 런처는 기존 S22 HQ 프로세스가 있으면 재사용하고, 자신이 시작한 프로세스만
종료한다. 기존 컨베이어 서버가 이미 실행 중이면 `/cmd_vel` 소유권 충돌로
종료하므로 기존 서버를 먼저 정상 종료해야 한다. Unity ROS-TCP Endpoint
(`port 10000`)와 GoPro 런처는 이 명령에 포함되지 않으며 팀원이 계속 별도로
관리한다.

## 3. assembly-r1 operation 연결

Main/Unity executor에서 레시피 문자열을 다음 서비스로 매핑한다.

| 레시피 operation | 호출 서비스 | operation 완료 조건 |
|---|---|---|
| `move_conveyor_to_assembly` | `/conveyor/move_to_assembly` | state=`ASSEMBLY_STOP` |
| `move_conveyor_to_inspection` | `/conveyor/move_to_inspection` | state=`INSPECTION_STOP` |
| 긴급/사용자 정지 | `/conveyor/stop` | state=`MANUAL_STOP` |
| fault 복구 | `/conveyor/reset` | state=`IDLE` |

처리 순서 예시:

```text
1. FR5 home/clear 확인
2. S22 `stop_line_ready=true`와 선택 정지선 trigger 상태 확인
3. move_to_assembly 서비스 호출
4. response.success 확인
5. /conveyor/state가 ASSEMBLY_STOP이 될 때까지 대기
6. 조립 25단계 수행
7. FR5 home/clear 확인
8. move_to_inspection 서비스 호출
9. /conveyor/state가 INSPECTION_STOP이 될 때까지 대기
10. 비전 검사와 DB 결과 저장
```

## 4. 서비스 수동 확인

```bash
ros2 service call /conveyor/move_to_assembly std_srvs/srv/Trigger '{}'
ros2 service call /conveyor/move_to_inspection std_srvs/srv/Trigger '{}'
ros2 service call /conveyor/stop std_srvs/srv/Trigger '{}'
ros2 service call /conveyor/reset std_srvs/srv/Trigger '{}'
```

거절되면 response의 `message`를 확인한다. 대표 원인은 다음과 같다.

- monitor-only/disarmed
- S22 stop-line status가 `false`
- 목적지 stop trigger가 이미 true
- 잘못된 공정 순서
- 다른 `/cmd_vel` publisher 실행 중
- 호환되는 로봇 `/cmd_vel` subscriber가 없음
- 이전 FAULT/MANUAL_STOP 이후 reset하지 않음

## 5. Unity 적용

1. Unity 프로젝트에 ROS-TCP Connector를 설치한다.
2. ROS 컴퓨터에서 Endpoint를 실행한다.

```bash
cd ~/KSMC/Ros2UnityEndopoint_PKG_0.2/Ros2UnityEndopoint_PKG
./run.sh
```

3. Unity의 ROS Connection에 Endpoint 컴퓨터 IP와 port `10000`을 입력한다.
4. `unity/ConveyorRosClient.cs`를 Unity `Assets/Scripts/`에 복사한다.
5. 빈 GameObject에 컴포넌트로 추가한다.
6. UI 버튼의 OnClick을 `MoveToAssembly`, `MoveToInspection`, `Stop`, `Reset`
   메서드에 연결한다.
7. `LastState`, `IsMoving`, `ConnectionStale`을 기존 UI/DT 상태에 반영한다.
   `ConnectionStale`은 유효한 상태를 한 번도 받지 못한 초기 표시용 호환
   플래그이며, 상태 수신 간격만으로 `FAULT`를 만들지 않는다.

Unity 버튼은 실제 장비 권한이 있는 Main Server 정책을 우회하면 안 된다. 운영
구성에서는 Main Server가 서비스 호출 권한을 갖고 Unity는 요청 UI 또는 상태 표시
역할만 갖는 것을 권장한다.

## 6. DB 적용

1. DB 서버가 ROS 2를 직접 사용한다면 ROS Jazzy와 domain 5를 설정한다.
2. `db/conveyor_event_subscriber.py`의 `persist_event()`를 실제 DB insert 함수로
   교체한다.
3. `(production_cycle_id, station, event_type)` unique key로 중복 저장을 막는다.
4. 상태 JSON의 `timestamp_ns`와 DB 수신 시간을 함께 저장한다.
5. `STATION_REACHED`는 trigger의 반복 true가 아닌 상승 에지만 저장한다.

DB 서버에 ROS 2를 설치할 수 없다면 Main Server에서 ROS를 구독하고 HTTP 또는
WebSocket으로 DB 애플리케이션에 전달하는 별도 adapter가 필요하다.

## 7. 종료

원격 서버는 실행 터미널에서 `Ctrl+C`로 종료한다. 종료 시 0속도를 반복 발행한다.
실제 장비 이상 시 소프트웨어보다 물리 비상정지를 우선한다.
