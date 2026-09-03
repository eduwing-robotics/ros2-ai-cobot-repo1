# FR5 조립 스택 통합 실행 명령

## 가장 자주 쓰는 명령

프로젝트 폴더에서 실행한다.

```bash
cd /home/juchan-yoon/FR5_robot_control
```

전체 스택 시작:

```bash
./run_fr5_assembly_stack.sh start
```

기존 노드나 토픽 발행 프로세스가 꼬였을 때 전체 정리 후 재시작:

```bash
./run_fr5_assembly_stack.sh restart
```

현재 상태와 로봇 상태 1회 확인:

```bash
./run_fr5_assembly_stack.sh check
```

작업자 통합 화면 열기:

```bash
./run_fr5_assembly_stack.sh view
```

전체 종료:

```bash
./run_fr5_assembly_stack.sh stop
```

통합 실행기 밖에서 따로 실행해 남은 중복 프로세스까지 정리:

```bash
./run_fr5_assembly_stack.sh clean
```

## 통합 시작 대상

`start`는 다음 구성요소를 순서대로 실행한다.

1. FAIRINO 명령/상태 서버와 Unity ROS-TCP Endpoint
2. D435 RGB-D
3. 트레이 등록·부품 검출·CAP 근접뷰·트레이 렌더러
4. 기판 슬롯 화면
5. 최신 기판 3D 좌표 추적
6. 트레이/기판 작업자 화면 mux
7. Unity 관제용 Vision Action API

기본 카메라 프로필은 `standard`이며, 전체 사이클 동안 단일 1280×720 RGB-D 스트림을 유지한다. TrayHome 등록과 SMD 근접 OBB 모두 이 스트림에서 동작한다.

```bash
./run_fr5_assembly_stack.sh start --camera standard --smd-set 1
```

두 번째 SMD 세트(물리 인덱스 6~10)를 선택할 때:

```bash
./run_fr5_assembly_stack.sh start --smd-set 2
```

`--smd-set`은 트레이의 물리 용량 10개를 바꾸지 않고, 이번 조립 사이클에서 사용할 한 줄 5개만 선택한다. 다른 줄이 비어 있거나 채워져 있어도 선택한 세트만 계산한다.

1920×1080 컬러 프로필은 진단용으로만 남긴다. 기존 TrayHome homography는 1280 실시간 화면 기준이므로 정상 조립 사이클 중에는 사용하지 않는다.

```bash
./run_fr5_assembly_stack.sh start --camera smd
```

이미 별도로 D435를 실행한 경우:

```bash
./run_fr5_assembly_stack.sh start --camera none
```

## 중복 노드 정리 정책

`start`, `restart`, `clean`은 이 프로젝트의 알려진 프로세스만 이름으로 찾아 정리한다. 주요 대상은 다음과 같다.

- `ros2_cmd_server`, `default_server_endpoint`
- `realsense2_camera_node`, `rs_launch.py`
- `view_tray_sections.py`, `render_tray_live.py`
- `detect_tray_parts.py`, `detect_smd_close_live.py`
- `view_board_center.py`, `track_board_pose_3d.py`
- `assembly_image_mux.py`, `orchestration_action_server`

상태 토픽을 받을 수 있는데 `robot_motion_done != 1`이면 정리를 거부한다. 움직이는 중 FAIRINO 서버를 끊지 않기 위한 조건이다. 먼저 로봇을 안전하게 정지한 뒤 다시 실행한다.

통합 실행기는 `SIGKILL`을 자동으로 쓰지 않는다. INT와 TERM 후에도 남는 프로세스는 PID를 출력하고 작업자 확인을 요구한다.

## 상태와 로그

관리 중인 PID, 관련 ROS 노드/토픽, Unity TCP 10000 포트 확인:

```bash
./run_fr5_assembly_stack.sh status
```

전체 최근 로그:

```bash
./run_fr5_assembly_stack.sh logs
```

특정 구성요소 로그:

```bash
./run_fr5_assembly_stack.sh logs camera
./run_fr5_assembly_stack.sh logs tray_vision
./run_fr5_assembly_stack.sh logs unity_fairino
```

실시간 로그 추적:

```bash
./run_fr5_assembly_stack.sh follow
./run_fr5_assembly_stack.sh follow board_pose_3d
```

로그와 PID는 Git에서 제외된 `runtime/assembly_stack/`에 저장된다.

## 안전 범위

이 실행기는 서버, 카메라, 비전 노드만 시작한다. 로봇 이동이나 그리퍼 명령은 보내지 않는다.

실제 이동 전에는 반드시 다음을 별도로 확인한다.

- `robot_mode=0`
- `robot_motion_done=1`
- Tool1/User0
- 비상정지·충돌·주/부 오류 없음
- 실제 로봇 주변 간섭 없음
- 현재 파지 부품과 TCP 위치를 작업자가 직접 확인

2026-09-02 종료 상태는 CAP-01 파지 및 비정상 정지 기록이므로, 새 로그인에서 실제 상태를 확인하기 전 자동 이동을 재개하지 않는다.
