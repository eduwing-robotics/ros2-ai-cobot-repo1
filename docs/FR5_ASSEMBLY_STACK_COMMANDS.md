# FR5 조립 스택 통합 실행 명령

## 조립 사이클 실행 — 2026-09-07

스택 기동 후 `./run_fr5_cycle.sh --execute`로 촬영부터 일반20개·SMD5개 조립까지 이어간다. 일반 부품의 매 파지 후 TrayHome 확인을 포함한다. `./run_fr5_cycle.sh --check`는 이동 없이 준비 상태를 조회한다. [단일 런처 사용법](FR5_CYCLE_LAUNCHER_KO.md). 아래 9월 6일 인계에는 이후 전체25개 성공 전의 상태가 포함되므로 최신 물리 상태는 오늘 일지와 현재 조회로 확인한다.

## 최신 인계 — 2026-09-06

- 통합 실행기는 서비스·카메라·비전 기동용이다. 조립 실행은 별도 단계다.
- 최신 물리 인계는 `작업일지/2026-09-05.md` 말미의 최종 종합이다.
  GPU1/HBM8/PM4/VRM2는 명령상 배치 시퀀스 완료이나 PM03·04 중심 오차와
  VRM 반대 방향 배치 문제가 남았다. VRM03은 실제 보유 여부 미확인 상태에서
  사용자 정지했다. 마지막 기록은 abnormal_stop=1, 그리퍼24이며 현재 상태가 아니다.
- 9월 6일 수정 전 조회에서는 관리 대상 7개 STOPPED, TCP10000 미수신이었다.
  과거의 실행 중 보고를 재사용하지 말고 `check`로 현재 상태를 조회한다.
- 9월 6일 후속 작업에서 VRM C≈180° 분기 고정과 실행 전 반대 분기 거부를 수정했다.
  관련45개 시험 통과. 새 촬영·실기 IK·안착 검증 및 PM03·04 보정 검증은 미완료다.
- 기본 RGB/Depth는 1280×720·15fps, SMD set1, 기판 추적 기본 슬롯 GPU-01이다.
  start 성공이나 publisher 존재는 이미지 최신성·검출 품질·물리 안착 검증이 아니다.

## 가장 자주 쓰는 명령

프로젝트 폴더에서 실행한다.

```bash
cd /home/juchan-yoon/FR5_robot_control
```

설치 경로와 ROS 패키지만 사전 점검(서비스 기동 없음):

```bash
./run_fr5_assembly_stack.sh preflight
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

작업자 통합 화면과 USB 휴대폰 카메라 화면 함께 열기:

```bash
./run_fr5_assembly_stack.sh view
```

`view`는 D435 작업자 화면(RQT)과 기존 `~/.local/bin/fr5-phone-view` 휴대폰 화면을 함께 연다. 이미 실행 중인 휴대폰 화면은 그대로 사용한다. 휴대폰 연결이나 실행에 문제가 있어도 D435 화면은 열리며, 휴대폰 실행 로그는 `runtime/assembly_stack/logs/phone_view.log`에서 확인한다. 휴대폰 창은 `Q` 또는 `Esc`로 닫는다.

평소 시작 명령은 그대로 사용한다.

```bash
cd /home/juchan-yoon/FR5_robot_control
./run_fr5_assembly_stack.sh preflight
./run_fr5_assembly_stack.sh start
./run_fr5_assembly_stack.sh check
./run_fr5_assembly_stack.sh view
```

휴대폰 화면은 마지막 `view` 단계에서 켜진다. `start`는 기존 스택을 재시작하는 명령이므로 이미 정상 실행 중인 화면을 열 때는 `view`만 실행하면 된다.

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

기본 카메라 프로필은 `standard`이며, 전체 사이클 동안 단일 1280×720·15fps RGB-D 스트림을 유지한다. TrayHome 등록과 SMD 근접 OBB 모두 이 스트림에서 동작한다.

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

이미 별도로 D435를 실행한 경우(외부 카메라 프로세스를 보존):

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

FAIRINO 드라이버가 있는데 정지 상태 샘플을 확보하지 못하거나 `robot_motion_done != 1`이면 정리를 거부한다. 움직이는 중 FAIRINO 서버를 끊지 않기 위한 조건이다. 먼저 로봇을 안전하게 정지한 뒤 다시 실행한다.

기동 전 점검 또는 정지 확인 실패 시 기존 관리 프로세스를 실패 정리 경로로 종료하지 않는다.
`--camera none` 시작에서는 관리·외부 D435 프로세스를 모두 정리 대상에서 제외한다.

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

9월 5일 최종 기록의 VRM03 보유 후보와 현재 실물을 먼저 대조한다.
과거 target/snapshot 및 run record의 last_verified_tcp를 현재 위치로 재사용하지 않는다.
오류 해제·로봇 이동·그리퍼 명령은 이 실행기에서 수행하지 않는다.
Real Backend 하드웨어 실행은 비활성으로 유지한다.

## 명령이 실패할 때

|증상|확인 방법|
|---|---|
|`No such file or directory`|위 프로젝트 폴더로 이동하거나 실행기의 절대 경로 사용|
|`MISSING executable` / `MISSING ROS package`|`preflight`에 표시된 설치 경로·워크스페이스 빌드를 점검|
|`No valid /nonrt_state_data`|`logs unity_fairino`로 드라이버 상태·제어기 연결·ROS_DOMAIN_ID 확인|
|`Refusing cleanup`|현재 로봇 정지와 상태 토픽을 확인한 뒤 재시도|
|카메라 시작 timeout|`logs camera`로 USB 연결·장치 점유·스트림 오류 확인|
|RQT desktop session 오류|로봇 PC의 데스크톱 터미널에서 `view` 실행|
|`No assembly image publisher`|`start` 후 `logs image_mux`와 `status` 확인|

`view`는 해당 터미널을 점유한다. 다른 명령은 새 터미널에서 실행한다.
`check`는 유효한 로봇 상태 샘플이 없거나 관리 구성요소가 중단되면 종료코드1을 반환한다.
로봇 상태 숫자는 그대로 출력하며, 명령 성공을 동작 허가로 해석하지 않는다.

## 9월 6일 검증

- 쉘 문법 검사와 서비스 호출을 대체한 회귀시험 9개 통과.
- 현재 PC의 `preflight` 통과. 이후 사용자 start/check 로그에서 7개 RUNNING 및 TCP10000 정상 확인.
- `view`의 publisher 오판(ROS CLI와 grep 조기 파이프 종료)을 수정했다. 실제 영상 내용·최신성은 별도 확인 대상.


## Real Robot API 실행 모드 — 2026-09-08

이 PC는 사용자 요청에 따라 `config/ksmc.env`의 `KSMC_REAL_HARDWARE_EXECUTION=true`로 실제 실행을 활성화했다. 스택 재시작 시에도 유지된다. 다른 PC에서 미지정 시 false다. `api-start`는 기존 API의 모드를 바꾸지 않으며 설정 변경 후에는 API 재시작이 필요하다. 상태는 `/real/robot/status` (`std_srvs/srv/Trigger`)의 `hardware_execution_enabled`로 확인한다. 기동 자체는 이동 명령을 보내지 않는다.
