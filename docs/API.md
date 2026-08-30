# API Catalog & Interface Status

| 문서 | 기준 | 범위 |
| --- | --- | --- |
| ROS2·HTTP API Catalog | `Assets/Scenes/SampleScene.unity`와 현재 Runtime source | 프로젝트 필요 기능과 현재 Mock·Real API 비교 |

`제안·협의 필요`는 송신자·수신자와 기능만 선언한 상태이며 인터페이스명과 메시지 Schema는 미확정이다.

## 1. 기능별 구현 현황

| 프로젝트 필요 기능 | Mock API | Real API | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| 자동 조립 시작 | `/unity/assembly/start` | `/real/assembly/start` | Mock 구현·Real 미구현 | 수락은 완료가 아님 |
| 조립 상태 조회·재접속 복구 | `/unity/assembly/start`의 `status` | `/real/assembly/status` | Mock 구현·Real 미구현 | Mock은 ROS 메모리 Snapshot 사용 |
| 조립 진행·완료·실패 | `/unity/assembly/feedback` | `/real/assembly/progress` | Mock 구현·Real 미구현 | `COMPLETED`에서만 성공 |
| 부품 Pick·Place | Mock 자동 조립 내부 실행 | Real 자동 조립 내부 실행 예정 | Mock 부분 구현 | Real 실행 노드 없음 |
| 관절 수동 제어 | `/unity/joint_target` | 없음 | Mock API만 구현 | MANUAL UI 미연결 |
| MoveJ | `/unity/movej_target` | `/fairino_remote_command_service` | 저수준 구현 | MANUAL UI 미연결 |
| TCP 직선 이동 | `/unity/tcp_target` | `/fairino_remote_command_service` | Mock 구현·Real 디버그 전용 | Real은 `IRobotControl` 미연결 |
| 그리퍼 제어 | `/unity/gripper_target` | `/fairino_remote_command_service` | 저수준 구현 | Real은 실제 완료 Task 없음 |
| 로봇 상태 | `/joint_states` | `/nonrt_state_data` | 구현 | 관절·TCP·안전·오류 상태 |
| 수동 명령 완료 확인 | `/twin_visual/status` | `/nonrt_state_data` | 부분 구현 | Real 그리퍼 완료 판정 없음 |
| 비전 영상 | Unity 내부 Camera | `/vision/*/compressed`, `/camera3/*` | Mock 내부 구현·Real 미구현 | Mock 외부 API 없음·Real ROS 발행 노드 없음 |
| 부품·기판 Pose | Unity Scene Transform | `/vision/board/capture/target_pose` | Mock 구현·Real 미구현 | Real 수신 코드만 존재 |
| 선택 대상 ID | Unity 내부 식별자 | `/vision/board/selected_target` | Mock 내부 처리·Real 미구현 | Real 수신 코드만 존재 |
| 컨베이어 이동·정지 | Unity 내부 Mock | 없음 | Mock 부분 구현 | 외부 API 없음 |
| 작업 중지 | 없음 | 없음 | 미구현 | 계약 확정 필요 |
| 일시정지·재개 | 없음 | 없음 | 미구현 | 계약 확정 필요 |
| 진행도·기판 번호 | Feedback·Snapshot | Progress 예정 | 부분 구현 | 진행도만 표시, `job_id`·`unit_id` UI 미전달 |
| PASS/FAIL 검사 | MainServer Job·Unit 조회 | 동일 예정 | 부분 구현 | Mock DB 기록만 존재, INSPECT 미연결 |
| 작업·검사 이력 | MainServer Job·Unit API | 동일 | 부분 구현 | 단건 조회만 존재 |
| 재고·조립 가능 여부 | MainServer Product API | 동일 | Backend 구현 | UI 공개 범위 재검토 중 |
| 사람 감지 안전정지 | 없음 | 없음 | 미구현 | 로봇·컨베이어 동시 정지 필요 |
| E-STOP 연동 | 상태 표시 일부 | `/nonrt_state_data` | 부분 구현 | 표시만 존재, 작업 정지 연동 없음 |

## 2. 공통 API

### 2.1 MainServer HTTP

상세 요청·응답과 오류 계약은 [MainServer API](../MAIN_SERVER/Main_serverAPI.md)를 따른다.

| API ID | 기능명 | 호출자 → 제공자 | Method | Endpoint | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- |
| HTTP-SYS-001 | 서버 상태 조회 | 운영자 → MainServer | `GET` | `/api/v1/health` | 구현 | — |
| HTTP-PRD-001 | 제품 목록·조립 가능 수량 조회 | Unity → MainServer | `GET` | `/api/v1/products` | 구현 | UR-11, SR-16 |
| HTTP-PRD-002 | 제품 슬롯·부품 구성 조회 | Unity → MainServer | `GET` | `/api/v1/products/{product_id}` | 구현 | UR-11, SR-16 |
| HTTP-PRD-003 | 필요·보유·부족 수량 조회 | Unity → MainServer | `GET` | `/api/v1/products/{product_id}/requirements?quantity={quantity}` | 구현 | UR-11, SR-16 |
| HTTP-PRD-004 | 부품 정보·재고 조회 | HTTP Client → MainServer | `GET` | `/api/v1/parts/{part_id}` | 구현·Unity 미연결 | UR-11, SR-16 |
| HTTP-JOB-001 | 조립 작업 진행률 조회 | Unity → MainServer | `GET` | `/api/v1/jobs/{job_id}` | 구현·UI 부분 연결 | UR-06, SR-10 |
| HTTP-JOB-002 | Unit·검사·불량 조회 | Unity → MainServer | `GET` | `/api/v1/jobs/{job_id}/units` | 구현·UI 부분 연결 | UR-09~10, SR-09·11·13 |
| HTTP-JOB-003 | 작업 목록 조회 | Unity 작업 화면 → MainServer | `GET` | `TBD` | 제안·협의 필요 | UR-10, SR-13 |
| HTTP-JOB-004 | 작업 오류·취소 이벤트 조회 | Unity 작업·검사 화면 → MainServer | `GET` | `TBD` | 제안·협의 필요 | UR-10, SR-13 |
| HTTP-QLT-001 | 슬롯별 불량률 조회 | Unity → MainServer | `GET` | `/api/v1/products/{product_id}/quality/slot-rates` | 구현·UI 부분 연결 | UR-09, SR-09·11 |
| HTTP-ASM-001 | 조립 시작 요청 전달 | HTTP Client → MainServer | `POST` | `/api/v1/assemblies` | 구현·Unity 미연결 | UR-01~02, UR-08 / SR-01~02, SR-12 |
| HTTP-ASM-002 | 현재·최근 조립 상태 조회 | Unity → MainServer | `GET` | `/api/v1/assemblies/current` | 구현 | UR-06, SR-10 |

## 3. Mock API

Mock 카메라와 컨베이어는 Unity 내부 기능이므로 외부 API Catalog에 포함하지 않는다.

### 3.1 조립·DB Bridge

| API ID | 기능명 | 호출자·송신자 → 제공자·수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-ASM-001 | 자동 조립 시작·상태 조회 | Unity `MockAssemblyScenarioControl` 또는 MainServer `AssemblyGateway` → `mock_movej` 또는 `mock_db_bridge` | Service | `/unity/assembly/start` | `fairino_msgs/srv/RemoteCmdInterface` | 구현 | UR-01~02, UR-08 / SR-01~02, SR-12 |
| ROS-ASM-002 | 조립 진행·완료·실패 전달 | `mock_movej` 또는 `mock_db_bridge` → Unity `MockAssemblyScenarioControl` | Topic | `/unity/assembly/feedback` | `std_msgs/String` | 구현 | UR-01~02, UR-06 / SR-01~02, SR-10 |

### 3.2 Robot·MoveIt

| API ID | 기능명 | 송신자 → 수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-RBT-001 | 관절 목표 전달 | Unity `MockRobotControl` → `mock_movej` | Topic | `/unity/joint_target` | `sensor_msgs/JointState` | 구현·MANUAL UI 미연결 | — |
| ROS-RBT-002 | MoveJ 목표 전달 | Unity `MockRobotControl` → `mock_movej` | Topic | `/unity/movej_target` | `geometry_msgs/PoseStamped` | 구현·MANUAL UI 미연결 | — |
| ROS-RBT-003 | TCP 직선 이동 목표 전달 | Unity `MockRobotControl` → `mock_movej` | Topic | `/unity/tcp_target` | `geometry_msgs/PoseStamped` | 구현·MANUAL UI 미연결 | — |
| ROS-RBT-004 | 그리퍼 개도 전달 | Unity `MockRobotControl` → `mock_movej` | Topic | `/unity/gripper_target` | `std_msgs/Float32` | 구현·MANUAL UI 미연결 | — |
| ROS-RBT-005 | Mock 로봇 상태 전달 | `joint_state_broadcaster` → Unity `MockRobotStateSource` | Topic | `/joint_states` | `sensor_msgs/JointState` | 구현 | UR-07, SR-08 |
| ROS-RBT-006 | Mock 명령 결과 전달 | `mock_movej` → Unity `MockRobotControl` | Topic | `/twin_visual/status` | `std_msgs/String` | 구현 | UR-07, SR-08 |

## 4. Real API

### 4.1 FR5 Robot

| API ID | 기능명 | 호출자·송신자 → 제공자·수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-RBT-007 | FR5 이동·그리퍼 명령 | Unity `RealRobotControl`·`RealGripperRequest` → `fr_command_server` | Service | `/fairino_remote_command_service` | `fairino_msgs/srv/RemoteCmdInterface` | 저수준 부분 구현 | — |
| ROS-RBT-008 | FR5 상태 전달 | `fr_command_server` → Unity `RealStatusSubscriber` | Topic | `/nonrt_state_data` | `fairino_msgs/msg/RobotNonrtState` | 구현 | UR-07, SR-08 |

### 4.2 Vision

| API ID | 기능명 | 송신자 → 수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-VIS-001 | PARTS 영상 전달 | Vision node → Unity `CamVisionReceiver` | Topic | `/vision/parts_obb/image/compressed` | `sensor_msgs/CompressedImage` | Unity 구독 구현·ROS 발행 노드 없음 | SR-06 |
| ROS-VIS-002 | TRAY 영상 전달 | Vision node → Unity `CamVisionReceiver` | Topic | `/vision/tray/detections_image/compressed` | `sensor_msgs/CompressedImage` | Unity 구독 구현·ROS 발행 노드 없음 | SR-06 |
| ROS-VIS-003 | CONVEYOR 영상 전달 | Vision node → Unity `CamVisionReceiver` | Topic | `/vision/conveyor/stop_image/compressed` | `sensor_msgs/CompressedImage` | Unity 구독 구현·ROS 발행 노드 없음 | SR-06 |
| ROS-VIS-004 | CELL 영상 전달 | Camera node → Unity `CamVisionReceiver` | Topic | `/camera3/image_raw/compressed` | `sensor_msgs/CompressedImage` | Unity 구독 구현·ROS 발행 노드 없음 | SR-06 |
| ROS-VIS-005 | 기판 검출 Pose 전달 | Vision node → Unity `VisionDetector` | Topic | `/vision/board/capture/target_pose` | `geometry_msgs/PoseStamped` | Unity 수신 코드만 존재·ROS 발행 노드 없음 | SR-06~07 |
| ROS-VIS-006 | 선택 대상 ID 전달 | Vision node → Unity `VisionDetector` | Topic | `/vision/board/selected_target` | `std_msgs/String` | Unity 수신 코드만 존재·ROS 발행 노드 없음 | SR-06 |
| ROS-STA-003 | Vision 연결·검출 준비·오류 상태 전달 | `vision_node` → `real_assembly`, Unity | Topic | `TBD` | `TBD` | 제안·협의 필요 | UR-07, SR-08 |

### 4.3 자동 조립

| API ID | 기능명 | 호출자·송신자 → 제공자·수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-ASM-003 | Real 자동 조립 시작 | Unity `RealAssemblyScenarioControl` → `real_assembly` node | Service | `/real/assembly/start` | `real_assembly_interfaces/srv/StartAssembly` | 설계됨·미구현 | UR-01~02, UR-08 / SR-01~02, SR-12 |
| ROS-ASM-004 | Real 조립 상태 조회 | Unity `RealAssemblyScenarioControl` → `real_assembly` node | Service | `/real/assembly/status` | `real_assembly_interfaces/srv/GetAssemblyStatus` | 설계됨·미구현 | UR-06, SR-10 |
| ROS-ASM-005 | Real 조립 진행·완료·실패 전달 | `real_assembly` node → Unity `RealAssemblyScenarioControl` | Topic | `/real/assembly/progress` | `real_assembly_interfaces/msg/AssemblyProgress` | 설계됨·미구현 | UR-01~02, UR-06 / SR-01~02, SR-10 |
| ROS-CTL-001 | 조립 중지·일시정지·재개 | Unity `RealAssemblyScenarioControl`, MainServer `AssemblyGateway` → `real_assembly` | Service | `TBD` | `TBD` | 제안·협의 필요 | UR-08, SR-12 |

### 4.4 Conveyor

| API ID | 기능명 | 호출자·송신자 → 제공자·수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-CNV-001 | 조립·검사 위치 이동 | `real_assembly` → `conveyor_controller` | Action | `TBD` | `TBD` | 제안·협의 필요 | UR-03~05, SR-03~05 |
| ROS-STA-002 | 컨베이어 위치·운전·오류 상태 전달 | `conveyor_controller` → `real_assembly`, Unity | Topic | `TBD` | `TBD` | 제안·협의 필요 | UR-03~05·07, SR-03~05·08 |

### 4.5 Inspection

| API ID | 기능명 | 호출자 → 제공자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-INS-001 | 검사 실행·진행·PASS/FAIL 결과 반환 | `real_assembly` → `inspection_node` | Action | `TBD` | `TBD` | 제안·협의 필요 | UR-09, SR-09·11 |

- Goal: `job_id`, `unit_id`, `product_id`
- Feedback: 검사 단계와 진행 상태
- Result: PASS/FAIL, `slot_code`, `defect_type`, 검사 이미지 경로, 검사 시각, 오류 코드

### 4.6 Safety

| API ID | 기능명 | 송신자 → 수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-SAF-001 | 사람 감지·E-STOP 상태 전달 | Safety PLC·센서 bridge → `real_assembly`, Robot·Conveyor 명령 경계, Unity | Topic | `TBD` | `TBD` | 제안·협의 필요 | UR-13, SR-14~15 |

물리 E-STOP은 하드와이어드 안전회로가 정지시키며 ROS는 상태 전달과 새 명령 차단만 담당한다.
