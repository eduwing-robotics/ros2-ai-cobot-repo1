# API Catalog & Interface Status

| 문서 | 기준 | 범위 |
| --- | --- | --- |
| ROS2·HTTP API Catalog | `Assets/Scenes/SampleScene.unity`와 현재 Runtime source | 프로젝트 필요 기능과 현재 Mock·Real API 비교 |

`제안·협의 필요`는 송신자·수신자와 기능만 선언한 상태이며 인터페이스명과 메시지 Schema는 미확정이다. 송신자·수신자는 시스템 컴포넌트 기준으로 표기하며 구체 클래스·노드명은 상세 명세에서 확인한다.

Real 자동 조립의 상세 메시지 Schema와 구현자 준수사항은 [Assembly Sequencer API](../ASSEMBLY_SEQUENCER/API.md), 프로세스와 DB 정책은 [Assembly Sequencer README](../ASSEMBLY_SEQUENCER/README.md)를 따른다.

## 1. 기능별 구현 현황

| 프로젝트 필요 기능 | Mock API | Real API | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| 자동 조립 시작 | MainServer `POST /api/v1/assemblies` | 동일 | Mock 구현·Real consumer 미구현 | HTTP 수락은 DB 저장일 뿐 완료가 아님 |
| 조립 상태 조회·재접속 복구 | `/unity/assembly/start`의 `status` | `/real/assembly/status` | Mock 구현·Real 미구현 | QUEUED는 영속, RUNNING 재시작은 실패 마감 |
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
| 생산 DB 갱신 | PostgreSQL command claim + Async DB Worker | 향후 Real도 같은 Writer 사용 | Mock·공통 구현, Real 연결 미구현 | command는 영속, update event Outbox는 제외 |
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
| HTTP-PRD-004 | 부품 정보·재고 조회 | Unity → MainServer | `GET` | `/api/v1/parts/{part_id}` | 구현·Unity 미연결 | UR-11, SR-16 |
| HTTP-JOB-001 | 조립 작업 진행률 조회 | Unity → MainServer | `GET` | `/api/v1/jobs/{job_id}` | 구현·UI 부분 연결 | UR-06, SR-10 |
| HTTP-JOB-002 | Unit·검사·불량 조회 | Unity → MainServer | `GET` | `/api/v1/jobs/{job_id}/units` | 구현·UI 부분 연결 | UR-09~10, SR-09·11·13 |
| HTTP-JOB-003 | 작업 목록 조회 | Unity → MainServer | `GET` | `TBD` | 제안·협의 필요 | UR-10, SR-13 |
| HTTP-JOB-004 | 작업 오류·취소 이벤트 조회 | Unity → MainServer | `GET` | `TBD` | 제안·협의 필요 | UR-10, SR-13 |
| HTTP-QLT-001 | 슬롯별 불량률 조회 | Unity → MainServer | `GET` | `/api/v1/products/{product_id}/quality/slot-rates` | 구현·UI 부분 연결 | UR-09, SR-09·11 |
| HTTP-ASM-001 | 조립 시작 요청 저장 | Unity → MainServer | `POST` | `/api/v1/assemblies` | 구현·Unity 연결 | UR-01~02, UR-08 / SR-01~02, SR-12 |
| HTTP-ASM-002 | 현재·최근 조립 상태 조회 | Unity → MainServer | `GET` | `/api/v1/assemblies/current` | 구현 | UR-06, SR-10 |

## 3. Mock API

Mock 카메라와 컨베이어는 Unity 내부 기능이므로 외부 API Catalog에 포함하지 않는다.

### 3.1 조립·DB Bridge

| API ID | 기능명 | 호출자·송신자 → 제공자·수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-ASM-001 | 조립 상태 조회 | Unity 또는 MainServer → Assembly Sequencer (Mock) | Service | `/unity/assembly/start`의 `status` | `fairino_msgs/srv/RemoteCmdInterface` | 구현 | UR-06, SR-10 |
| ROS-ASM-002 | 조립 진행·완료·실패 전달 | Assembly Sequencer (Mock) → Unity | Topic | `/unity/assembly/feedback` | `std_msgs/String` | 구현 | UR-01~02, UR-06 / SR-01~02, SR-10 |
| ROS-ASM-006 | 내부 Mock 조립 실행 | Assembly Sequencer → Mock backend | Service | `/mock_db_mvp/internal/assembly/start` | `fairino_msgs/srv/RemoteCmdInterface` | 구현 | UR-01~02, UR-08 / SR-01~02, SR-12 |

### 3.2 Robot·MoveIt

| API ID | 기능명 | 송신자 → 수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-RBT-001 | 관절 목표 전달 | Unity → Robot (Mock) | Topic | `/unity/joint_target` | `sensor_msgs/JointState` | 구현·MANUAL UI 미연결 | — |
| ROS-RBT-002 | MoveJ 목표 전달 | Unity → Robot (Mock) | Topic | `/unity/movej_target` | `geometry_msgs/PoseStamped` | 구현·MANUAL UI 미연결 | — |
| ROS-RBT-003 | TCP 직선 이동 목표 전달 | Unity → Robot (Mock) | Topic | `/unity/tcp_target` | `geometry_msgs/PoseStamped` | 구현·MANUAL UI 미연결 | — |
| ROS-RBT-004 | 그리퍼 개도 전달 | Unity → Robot (Mock) | Topic | `/unity/gripper_target` | `std_msgs/Float32` | 구현·MANUAL UI 미연결 | — |
| ROS-RBT-005 | Mock 로봇 상태 전달 | Robot (Mock) → Unity | Topic | `/joint_states` | `sensor_msgs/JointState` | 구현 | UR-07, SR-08 |
| ROS-RBT-006 | Mock 명령 결과 전달 | Robot (Mock) → Unity | Topic | `/twin_visual/status` | `std_msgs/String` | 구현 | UR-07, SR-08 |

## 4. Real API

### 4.1 FR5 Robot

| API ID | 기능명 | 호출자·송신자 → 제공자·수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-RBT-007 | FR5 이동·그리퍼 명령 | Unity (Manual) 또는 Assembly Sequencer (Real) → Robot (FR5) | Service | `/fairino_remote_command_service` | `fairino_msgs/srv/RemoteCmdInterface` | 저수준 부분 구현 | — |
| ROS-RBT-008 | FR5 상태 전달 | Robot (FR5) → Assembly Sequencer (Real), Unity | Topic | `/nonrt_state_data` | `fairino_msgs/msg/RobotNonrtState` | 구현 | UR-07, SR-08 |

### 4.2 Vision

| API ID | 기능명 | 송신자 → 수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-VIS-001 | PARTS 영상 전달 | Vision → Unity | Topic | `/vision/parts_obb/image/compressed` | `sensor_msgs/CompressedImage` | Unity 구독 구현·ROS 발행 노드 없음 | SR-06 |
| ROS-VIS-002 | TRAY 영상 전달 | Vision → Unity | Topic | `/vision/tray/detections_image/compressed` | `sensor_msgs/CompressedImage` | Unity 구독 구현·ROS 발행 노드 없음 | SR-06 |
| ROS-VIS-003 | CONVEYOR 영상 전달 | Vision → Unity | Topic | `/vision/conveyor/stop_image/compressed` | `sensor_msgs/CompressedImage` | Unity 구독 구현·ROS 발행 노드 없음 | SR-06 |
| ROS-VIS-004 | CELL 영상 전달 | Vision → Unity | Topic | `/camera3/image_raw/compressed` | `sensor_msgs/CompressedImage` | Unity 구독 구현·ROS 발행 노드 없음 | SR-06 |
| ROS-VIS-005 | 기판 검출 Pose 전달 | Vision → Unity | Topic | `/vision/board/capture/target_pose` | `geometry_msgs/PoseStamped` | Unity 수신 코드만 존재·ROS 발행 노드 없음 | SR-06~07 |
| ROS-VIS-006 | 선택 대상 ID 전달 | Vision → Unity | Topic | `/vision/board/selected_target` | `std_msgs/String` | Unity 수신 코드만 존재·ROS 발행 노드 없음 | SR-06 |
| ROS-STA-003 | Vision 연결·검출 준비·오류 상태 전달 | Vision → Assembly Sequencer (Real), Unity | Topic | `TBD` | `TBD` | 제안·협의 필요 | UR-07, SR-08 |

### 4.3 자동 조립

Real AssemblySequencer는 MainServer와 분리된 ROS 2 프로세스로 배치한다.
MainServer는 조회와 command enqueue만 담당하고, Real AssemblySequencer가
command claim, 조립 순서·실제 완료 판정과 생산 DB 갱신 이벤트를 소유한다.

HTTP `accepted=true`는 command 저장 성공을 뜻한다. `COMPLETED`는 실제 조립·검사 완료를 뜻하며 DB 최종 반영 여부는 `db_sync_state`로 분리한다.

| API ID | 기능명 | 호출자·송신자 → 제공자·수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-ASM-003 | Real backend 조립 시작 | AssemblySequencer Real adapter → `real_assembly` | Service | `/real/assembly/start` | `real_assembly_interfaces/srv/StartAssembly` | 계약 확정·미구현 | UR-01~02, UR-08 / SR-01~02, SR-12 |
| ROS-ASM-004 | Real 조립 상태 조회 | Unity 또는 MainServer → AssemblySequencer Real adapter | Service | `/real/assembly/status` | `real_assembly_interfaces/srv/GetAssemblyStatus` | 계약 확정·미구현 | UR-06, SR-10 |
| ROS-ASM-005 | Real 조립 진행·완료·실패 전달 | `real_assembly` → AssemblySequencer Real adapter → Unity | Topic | `/real/assembly/progress` | `real_assembly_interfaces/msg/AssemblyProgress` | 계약 확정·미구현 | UR-01~02, UR-06 / SR-01~02, SR-10 |
| ROS-CTL-001 | 조립 중지·일시정지·재개 | Unity → MainServer → AssemblySequencer (Real) | `TBD` | `TBD` | `TBD` | 제안·협의 필요 | UR-08, SR-12 |

Real Start 요청은 `request_id`, `product_code`, `product_version`, `recipe_version`, `requested_quantity`를 사용한다. 응답은 `accepted`, `request_id`, `job_id`, `unit_id`, `error_code`, `message`를 반환한다. Status와 Progress는 작업 식별자, 상태, 현재 단계, 진행도, `db_sync_state`, 오류와 갱신 시각을 제공한다.

### 4.4 Conveyor

| API ID | 기능명 | 호출자·송신자 → 제공자·수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-CNV-001 | 조립·검사 위치 이동 | Assembly Sequencer (Real) → Conveyor | Action | `TBD` | `TBD` | 제안·협의 필요 | UR-03~05, SR-03~05 |
| ROS-STA-002 | 컨베이어 위치·운전·오류 상태 전달 | Conveyor → Assembly Sequencer (Real), Unity | Topic | `TBD` | `TBD` | 제안·협의 필요 | UR-03~05·07, SR-03~05·08 |

### 4.5 Inspection

| API ID | 기능명 | 호출자 → 제공자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-INS-001 | 검사 실행·진행·PASS/FAIL 결과 반환 | Assembly Sequencer (Real) → Inspection | Action | `TBD` | `TBD` | 제안·협의 필요 | UR-09, SR-09·11 |

- Goal: `job_id`, `unit_id`, `product_id`
- Feedback: 검사 단계와 진행 상태
- Result: PASS/FAIL, `slot_code`, `defect_type`, 검사 이미지 경로, 검사 시각, 오류 코드

### 4.6 Safety

| API ID | 기능명 | 송신자 → 수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 | 관련 요구사항 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROS-SAF-001 | 사람 감지·E-STOP 상태 전달 | Safety → Assembly Sequencer (Real), Robot (FR5), Conveyor, Unity | Topic | `TBD` | `TBD` | 제안·협의 필요 | UR-13, SR-14~15 |

물리 E-STOP은 하드와이어드 안전회로가 정지시키며 ROS는 상태 전달과 새 명령 차단만 담당한다.

### 4.7 내부 DB 갱신 계약

이 계약은 외부 ROS API가 아니라 `real_assembly` 프로세스 내부 경계다. 로봇·검사 callback은 SQL을 실행하지 않고 DB Update Event를 bounded queue에 추가한다.

신규 작업은 MainServer가 PostgreSQL command queue에 저장한다. AssemblySequencer가
`writer.claim()`으로 command와 Job·첫 Unit을 한 transaction에서 연결한 뒤에만
로봇 실행을 요청한다. DB claim 실패나 재고 부족 시 실제 로봇은 움직이지 않는다.
조립·검사 완료 이후 갱신은 queue에서 비동기로 처리한다.

| ID | 기능명 | 송신자 → 수신자 | 구분 | 인터페이스 | 데이터 | 상태 |
| --- | --- | --- | --- | --- | --- | --- |
| INT-DB-000 | 조립 command 저장·claim | MainServer → PostgreSQL → AssemblySequencer | PostgreSQL Queue | `control.assembly_requests` | command JSON | Mock·공통 구현 |
| INT-DB-001 | 생산 DB 갱신 예약 | Assembly Sequencer → Assembly Sequencer DB Worker | In-process Queue | bounded DB Update Queue | `DbUpdateEvent` | Mock·공통 구현 |
| INT-DB-002 | 생산 DB transaction 적용 | Assembly Sequencer DB Worker → PostgreSQL | DB Transaction | `PRODUCTION_DB_DSN` | `production_writer` 권한 | Mock·공통 구현 |

`DbUpdateEvent`는 `event_id`, `event_type`, `job_id`, `unit_id`, `payload`, `created_at`, `attempt_count`, `next_retry_at`, `last_error`를 가진다.

- 검사 Result callback은 `INSPECTION_RECORDED`와 최종 작업 이벤트를 queue에 추가한다.
- queue 항목은 PostgreSQL commit 성공 후에만 제거한다.
- 실패 항목은 재시도하며 queue overflow와 최종 실패를 조용히 폐기하지 않는다.
- command queue는 PostgreSQL에 영속된다. production update event queue는 프로세스
  내부이며 재시작을 넘는 Outbox는 포함하지 않는다.
- 이 구조는 SECS/GEM Spooling 개념을 참고하지만 SECS/GEM 호환 계약은 아니다.
