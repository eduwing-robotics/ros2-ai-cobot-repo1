# Unity 관제용 Vision Action 계약

이 문서는 Real Orchestrator와 Unity가 사용하는 Vision API의 실제 구현 계약이다.
Vision 서버는 로봇이나 컨베이어를 움직이지 않는다. Home과
AssemblyReadyPoint의 관절각은 Action 데이터가 아니며 Real Orchestrator가
이동 완료를 확인한 뒤 해당 Action을 호출한다.

## 실행 순서

1. Real Orchestrator: MoveJ(Home) 완료 확인
2. Real Orchestrator: /vision/tray/detect_parts 호출
3. Unity: 성공 결과의 같은 index에 있는 part_ids[i]와 part_poses[i]로 부품 생성
4. Real Orchestrator: 컨베이어 실제 정지 확인 후
   /orchestrator/conveyor_stopped에 true 발행
5. Real Orchestrator: MoveJ(AssemblyReadyPoint) 완료 확인
6. Real Orchestrator: /vision/pcb/calibrate_pose 호출
7. Unity: 성공 결과의 pcb_pose로 PCB 루트 Transform 교체

Action 서버 시작:

~~~bash
source /home/juchan-yoon/FR5_robot_control/scripts/ksmc_env.sh
/home/juchan-yoon/FR5_robot_control/vision_assembly/run_orchestration_api.sh
~~~

## 1. 트레이 부품 인식

- Endpoint: /vision/tray/detect_parts
- Type: vision_interfaces/action/DetectTrayParts
- 성공 결과의 header.frame_id: 항상 base_link
- 위치 단위: m
- 회전: 정규화된 quaternion x,y,z,w
- 총수량: part_ids.length
- 부품별 수량: part_ids의 동일 값 개수
- part_ids.length == part_poses.length
- count 필드는 반환하지 않는다.

Recipe part_id 매핑:

| 검출기 타입 | Action part_id |
|---|---|
| gpu | GPU |
| hbm | HBM |
| long_orange | PM |
| black_block | VRM |
| marked_white | IND |
| right_white_brown | CAP |

호출 예:

~~~bash
ros2 action send_goal --feedback \
  /vision/tray/detect_parts \
  vision_interfaces/action/DetectTrayParts \
  "{job_id: 'assembly-001-tray'}"
~~~

Vision 서버는 등록 상태, Base 변환, 촬영시각 신선도, 다중 프레임 안정성,
알 수 없는 부품, 좌표 유한성, quaternion 정규화를 검증한다. 배열 수량이
Recipe의 필요 수량보다 부족한지는 Real Orchestrator가 조립 시작 전에 Recipe와
비교하여 거부한다.

### 트레이 모델 Pose 규칙

현재 트레이 검출 원점은 depth로 측정한 부품 상면 중심이다. 로컬 +X는 검출된
부품 장축, 로컬 +Z는 base_link +Z이며 roll/pitch는 0인 평면 가정이다.
장축은 180도 대칭 측정이다. 따라서 Unity prefab 루트와 축도 이 규칙으로
맞추거나, 아래 설정의 yaw_offset_deg와 origin_offset_local_m를 모델별로
보정해야 한다.

ros2_ws/src/vision_server/config/orchestration_api.yaml

모델이 180도 비대칭 외형을 정확히 표시해야 한다면 현재 장축 검출만으로는 앞뒤를
구분할 수 없으므로 비대칭 특징 검출을 추가해야 한다. 이 제한은 로봇의 대칭축
grasp 계산에는 영향을 주지 않지만 Unity 외형 방향에는 영향을 줄 수 있다.

## 2. PCB 위치·회전 보정

- Endpoint: /vision/pcb/calibrate_pose
- Type: vision_interfaces/action/CalibratePcbPose
- 성공 결과의 pcb_pose.header.frame_id: 항상 base_link
- 위치 단위: m
- 회전: 정규화된 quaternion x,y,z,w
- 반환 Pose: T_base_board의 절대 PCB 루트 Pose
- delta position/rotation과 슬롯별 API는 제공하지 않는다.

현재 제품 식별자:

- product_code: printed_semiconductor_package_board
- product_version: assembly-r1

컨베이어 실제 정지 상태는 Real Orchestrator가 transient-local/reliable
std_msgs/msg/Bool로 다음 토픽에 발행해야 한다.

/orchestrator/conveyor_stopped

호출 예:

~~~bash
ros2 topic pub --once --qos-durability transient_local \
  /orchestrator/conveyor_stopped std_msgs/msg/Bool "{data: true}"

ros2 action send_goal --feedback \
  /vision/pcb/calibrate_pose \
  vision_interfaces/action/CalibratePcbPose \
  "{job_id: 'assembly-001-pcb', product_code: 'printed_semiconductor_package_board', product_version: 'assembly-r1'}"
~~~

Vision 서버는 4개 홀 정합 RMS, 보드 평면 MAD/inlier, 촬영시각 신선도,
T_base_board 직교성·우수 회전행렬 여부, 제품 설정 일치를 검증한다.
PCB 원점은 실물 보드의 기하 중심이며 축은
vision_assembly/config/physical_board.json의 canonical 축이다. Unity PCB
루트와 Recipe PCB 좌표계도 같은 원점·축이어야 한다.

현재 WRONG_PCB 판정은 요청 제품 코드/버전과 구성된 홀 패턴·보드 형상
일치 여부를 기반으로 한다. 서로 형상이 같은 다른 제품까지 시각적으로 구별하려면
제품 마커/OCR/고유 특징 판정이 추가로 필요하다.

## 오류 코드

트레이:

- CAMERA_NOT_READY
- CALIBRATION_NOT_READY
- NO_PARTS_DETECTED
- UNSTABLE_DETECTION
- UNKNOWN_PART
- FRAME_TRANSFORM_FAILED
- DETECTION_TIMEOUT
- CANCELLED
- INVALID_REQUEST

PCB:

- CAMERA_NOT_READY
- CONVEYOR_NOT_STOPPED
- CALIBRATION_NOT_READY
- PCB_NOT_FOUND
- WRONG_PCB
- UNSTABLE_POSE
- FRAME_TRANSFORM_FAILED
- DETECTION_TIMEOUT
- CANCELLED
- INVALID_REQUEST

## 소유권 경계

| 기능 | 담당 |
|---|---|
| Home/AssemblyReadyPoint 이동 및 도달 확인 | Real Orchestrator |
| 컨베이어 구동·정지 및 실제 정지 확인 | Real Orchestrator |
| 안정 검출·Base 변환·Pose 품질 판정 | Vision Action 서버 |
| 부품 수량을 Recipe와 비교해 시작 허용/거부 | Real Orchestrator |
| 부품 오브젝트 생성·PCB 루트 Transform 갱신 | Unity |
