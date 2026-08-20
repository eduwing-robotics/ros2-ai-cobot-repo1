# KSMC 팀 하드웨어·소프트웨어 아키텍처

- Document ID: 1E1vdtc80XqmClC_7l0EV4oabBd8hvPEEHcWAR3qWRhE
- Revision ID: AIroW35WJNL7V1zkb8ihmFs35li5I42xpbm3TQBjuo90vtSIKXiKRfsstoBJiZ0eqD302eqLw6dZnu8xxDC0CKVviFxNgPyO4K3qaGW6zg
- Selected tab: all
- Protected controls: 0
- Opaque controls: 0
- Authoritative dropdowns: 0

Protected-control annotations are preservation instructions. Do not insert their displayed placeholder text to recreate a native control.

## Tab 1 (t.0)

[P00001 | 1:24 | TITLE]
KSMC 팀 하드웨어·소프트웨어 아키텍처

[P00002 | 24:160 | NORMAL_TEXT]
FR5 기반 반도체 패키지형 전자모듈 정밀 조립·검사 스마트 제조 셀의 팀 전체 목표 아키텍처다. 기판 이송, 비전 좌표 계산, 부품 Pick/Place, 조립 검사, PASS/FAIL과 GUI 시각화를 하나의 ROS 2 시스템으로 연결한다.

[P00003 | 160:173 | HEADING_1]
1. 하드웨어 아키텍처

[P00004 | 173:175 | NORMAL_TEXT]
[INLINE_OBJECT kix.bo3lxjc18x8]

[P00005 | 175:224 | NORMAL_TEXT]
그림 1. FR5, 3대 카메라, TurtleBot 컨베이어와 통합 노트북의 물리 연결

[P00006 | 224:283 | NORMAL_TEXT | LIST id=kix.fp6g3rihxzt level=0]
FAIRINO FR5와 DH Robotics PGEA-100-40 및 제작 핑거가 실제 조립을 수행한다.

[P00007 | 283:352 | NORMAL_TEXT | LIST id=kix.fp6g3rihxzt level=0]
Intel RealSense D435는 그리퍼 측면 Eye-in-Hand 카메라로 RGB-D 근접 좌표와 높이를 제공한다.

[P00008 | 352:422 | NORMAL_TEXT | LIST id=kix.fp6g3rihxzt level=0]
Galaxy S22는 조립 위치 상부 Eye-to-Hand 카메라로 기판 도착, 위치·회전과 조립 완료 전수검사를 담당한다.

[P00009 | 422:458 | NORMAL_TEXT | LIST id=kix.fp6g3rihxzt level=0]
TurtleBot 구동륜이 자체 제작 컨베이어 롤러를 구동한다.

[P00010 | 458:500 | NORMAL_TEXT | LIST id=kix.fp6g3rihxzt level=0]
GoPro HERO11은 전체 공정 기록과 보조 위험영역 감시를 담당한다.

[P00011 | 500:557 | NORMAL_TEXT | LIST id=kix.fp6g3rihxzt level=0]
ROS 2 통합 노트북은 카메라, FR5, 컨베이어, 공정 로그와 Unity GUI/DT를 연결한다.

[P00012 | 557:571 | HEADING_1]
2. 소프트웨어 아키텍처

[P00013 | 571:573 | NORMAL_TEXT]
[INLINE_OBJECT kix.5nj4516l050g]

[P00014 | 573:605 | NORMAL_TEXT]
그림 2. ROS 2 장치·비전·좌표·공정제어·실행 계층

[P00015 | 605:673 | NORMAL_TEXT | LIST id=kix.110dd6z9ffp4 level=0]
장치 인터페이스 계층: D435, S22, GoPro, FR5 command server, TurtleBot driver

[P00016 | 673:726 | NORMAL_TEXT | LIST id=kix.110dd6z9ffp4 level=0]
비전·상태 인식 계층: 부품 RGB-D, 기판 도착·pose, 조립 검사, 로봇·컨베이어 상태

[P00017 | 726:814 | NORMAL_TEXT | LIST id=kix.110dd6z9ffp4 level=0]
좌표계·공정 모델 계층: TF, Hand-Eye, S22 Eye-to-Hand, CAD layout, part recipe, Pick/Place target

[P00018 | 814:873 | NORMAL_TEXT | LIST id=kix.110dd6z9ffp4 level=0]
공정 조정·안전 계층: Cell Orchestrator, Safety Interlock, Watchdog

[P00019 | 873:924 | NORMAL_TEXT | LIST id=kix.110dd6z9ffp4 level=0]
실행·결과 계층: FR5·그리퍼 실행, 컨베이어 제어, 검사 로그, Unity GUI/DT

[P00020 | 924:940 | HEADING_1]
3. 전체 공정 데이터 흐름

[P00021 | 940:989 | NORMAL_TEXT | LIST id=kix.arj6dzdsy910 level=0]
S22가 컨베이어에서 기판 도착을 검출하고 pre-stop과 stop 오차를 계산한다.

[P00022 | 989:1058 | NORMAL_TEXT | LIST id=kix.arj6dzdsy910 level=0]
Conveyor Controller가 TurtleBot 속도를 조절하고 완전 정지 후 assembly ready를 만든다.

[P00023 | 1058:1118 | NORMAL_TEXT | LIST id=kix.arj6dzdsy910 level=0]
S22가 기판 frame과 Base 기준 XY·yaw를 확정하고 CAD의 25개 slot 좌표를 변환한다.

[P00024 | 1118:1176 | NORMAL_TEXT | LIST id=kix.arj6dzdsy910 level=0]
D435가 고대비 부품 트레이에서 6개 recipe 중 대상 부품의 중심·yaw·depth를 계산한다.

[P00025 | 1176:1226 | NORMAL_TEXT | LIST id=kix.arj6dzdsy910 level=0]
Coordinate/TF Manager가 카메라 좌표를 FR5 Base 좌표로 변환한다.

[P00026 | 1226:1292 | NORMAL_TEXT | LIST id=kix.arj6dzdsy910 level=0]
Quality Gate가 reprojection, depth, 좌표 jump와 두 카메라 결과 일치 여부를 검사한다.

[P00027 | 1292:1354 | NORMAL_TEXT | LIST id=kix.arj6dzdsy910 level=0]
Cell Orchestrator가 FR5 Pick, 안전 접근, Place와 그리퍼 동작을 순서대로 실행한다.

[P00028 | 1354:1412 | NORMAL_TEXT | LIST id=kix.arj6dzdsy910 level=0]
FR5가 검사 시야에서 후퇴하면 S22가 전체 slot을 검사하고 불확실한 곳은 D435가 재검사한다.

[P00029 | 1412:1468 | NORMAL_TEXT | LIST id=kix.arj6dzdsy910 level=0]
PASS/FAIL, slot별 위치·방향·높이 오차와 이미지 경로를 저장하고 다음 기판을 이송한다.

[P00030 | 1468:1479 | HEADING_1]
4. 핵심 좌표변환

[P00031 | 1479:1508 | NORMAL_TEXT]
D435 Eye-in-Hand Pick/근접 좌표:

[P00032 | 1508:1580 | NORMAL_TEXT]
T_base_part = T_base_flange × T_flange_camera_d435 × T_camera_d435_part

[P00033 | 1580:1612 | NORMAL_TEXT]
S22 Eye-to-Hand Board/Place 좌표:

[P00034 | 1612:1680 | NORMAL_TEXT]
T_base_slot = T_base_camera_s22 × T_camera_s22_board × T_board_slot

[P00035 | 1680:1817 | NORMAL_TEXT]
TCP/toolcoord1과 T_flange_camera_d435는 서로 다른 변환이다. TCP 값을 Hand-Eye에 다시 더하지 않는다. 안전 접근 높이는 목표를 Base frame으로 완전히 변환한 뒤 Robot Base +Z에 적용한다.

[P00036 | 1817:1833 | HEADING_1]
5. 주요 ROS 인터페이스

[P00037 | 1833:1886 | NORMAL_TEXT | LIST id=kix.7ozhf3b9154s level=0]
/camera/camera/color/image_raw/compressed — D435 RGB

[P00038 | 1886:1955 | NORMAL_TEXT | LIST id=kix.7ozhf3b9154s level=0]
/camera/camera/aligned_depth_to_color/image_raw — D435 aligned depth

[P00039 | 1955:2009 | NORMAL_TEXT | LIST id=kix.7ozhf3b9154s level=0]
/nonrt_state_data — FR5 Base/Flange/TCP, 오류와 동작 완료 상태

[P00040 | 2009:2048 | NORMAL_TEXT | LIST id=kix.7ozhf3b9154s level=0]
/camera2/image_raw/compressed — S22 영상

[P00041 | 2048:2097 | NORMAL_TEXT | LIST id=kix.7ozhf3b9154s level=0]
/conveyor/cmd_vel, /conveyor/state — 컨베이어 명령과 상태

[P00042 | 2097:2153 | NORMAL_TEXT | LIST id=kix.7ozhf3b9154s level=0]
/board/pose_base, /assembly/ready — 기판 Base pose와 조립 허가

[P00043 | 2153:2197 | NORMAL_TEXT | LIST id=kix.7ozhf3b9154s level=0]
/inspection/result — slot별 검사와 최종 PASS/FAIL

[P00044 | 2197:2243 | NORMAL_TEXT | LIST id=kix.7ozhf3b9154s level=0]
/camera3/image_raw/compressed — GoPro 전체 셀 영상

[P00045 | 2243:2255 | HEADING_1]
6. 안전 설계 원칙

[P00046 | 2255:2287 | NORMAL_TEXT | LIST id=kix.bn7250l7be9f level=0]
FR5가 조립 구역에 있을 때 컨베이어 이동을 차단한다.

[P00047 | 2287:2324 | NORMAL_TEXT | LIST id=kix.bn7250l7be9f level=0]
컨베이어 이동 중에는 FR5가 조립 구역에 진입하지 못하게 한다.

[P00048 | 2324:2378 | NORMAL_TEXT | LIST id=kix.bn7250l7be9f level=0]
영상·DDS·노드 timeout 시 Watchdog이 공정 허가를 취소하고 컨베이어를 정지한다.

[P00049 | 2378:2448 | NORMAL_TEXT | LIST id=kix.bn7250l7be9f level=0]
NaN/Inf, depth invalid, 큰 좌표 jump와 calibration 미적용 상태에서는 로봇 이동을 금지한다.

[P00050 | 2448:2488 | NORMAL_TEXT | LIST id=kix.bn7250l7be9f level=0]
초기에는 dry-run과 안전 높이 접근 후에만 실제 동작을 허가한다.

[P00051 | 2488:2532 | NORMAL_TEXT | LIST id=kix.bn7250l7be9f level=0]
GoPro 사람 감지는 보조 계층이며 FR5 물리 비상정지를 대체하지 않는다.

[P00052 | 2532:2541 | HEADING_1]
7. 구현 상태

[P00053 | 2541:2551 | HEADING_2]
구현·검증된 기반

[P00054 | 2551:2581 | NORMAL_TEXT | LIST id=kix.jo58vejdgz8t level=0]
FR5 ROS 상태 수신과 command server

[P00055 | 2581:2633 | NORMAL_TEXT | LIST id=kix.jo58vejdgz8t level=0]
D435 1920×1080 RGB, aligned depth와 Eye-in-Hand 좌표변환

[P00056 | 2633:2669 | NORMAL_TEXT | LIST id=kix.jo58vejdgz8t level=0]
dry-run, 안전 접근과 RGB-D 테스트 물체 첫 Pick

[P00057 | 2669:2695 | NORMAL_TEXT | LIST id=kix.jo58vejdgz8t level=0]
GoPro HERO11 ROS 영상 발행 코드

[P00058 | 2695:2724 | NORMAL_TEXT | LIST id=kix.jo58vejdgz8t level=0]
Unity/OBJ board layout 후보 추출

[P00059 | 2724:2742 | HEADING_2]
통합을 위해 이어서 구현할 기능

[P00060 | 2742:2787 | NORMAL_TEXT | LIST id=kix.4q53youphtmn level=0]
S22 ROS 영상 bridge, intrinsic과 Eye-to-Hand 보정

[P00061 | 2787:2828 | NORMAL_TEXT | LIST id=kix.4q53youphtmn level=0]
기판 구멍/Fiducial 기반 board pose와 컨베이어 도착 검출

[P00062 | 2828:2873 | NORMAL_TEXT | LIST id=kix.4q53youphtmn level=0]
TurtleBot Conveyor Controller와 FR5 interlock

[P00063 | 2873:2898 | NORMAL_TEXT | LIST id=kix.4q53youphtmn level=0]
6개 recipe·25개 slot 순차 조립

[P00064 | 2898:2948 | NORMAL_TEXT | LIST id=kix.4q53youphtmn level=0]
S22 전수검사, D435 근접 재검사, 공정 Orchestrator와 통합 launch

[P00065 | 2948:2949 | NORMAL_TEXT]
⟦EMPTY PARAGRAPH⟧
