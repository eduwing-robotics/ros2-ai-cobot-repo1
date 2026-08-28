| 문서 | 기준 | 범위 |
| --- | --- | --- |
| ROS2 연동 API | `Assets/Scenes/SampleScene.unity` | 프로젝트 필요 기능과 현재 Mock·Real API 비교 |

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
| 비전 영상 | `/vision/*/compressed` | 동일 | 구현 | PARTS·TRAY·CONVEYOR·CELL |
| 부품·기판 Pose | `/vision/board/capture/target_pose` | 동일 예정 | 코드만 존재 | Scene·Scenario 미연결 |
| 선택 대상 ID | `/vision/board/selected_target` | 동일 예정 | 코드만 존재 | Scene 미연결 |
| 컨베이어 이동·정지 | Unity 내부 Mock | 없음 | Mock 부분 구현 | Real 설비 API 없음 |
| 작업 중지 | 없음 | 없음 | 미구현 | 계약 확정 필요 |
| 일시정지·재개 | 없음 | 없음 | 미구현 | 계약 확정 필요 |
| 진행도·기판 번호 | Feedback·Snapshot | Progress 예정 | 부분 구현 | 진행도만 표시, `job_id`·`unit_id` UI 미전달 |
| PASS/FAIL 검사 | MainServer Job·Unit 조회 | 동일 예정 | 부분 구현 | Mock DB 기록만 존재, INSPECT 미연결 |
| 작업·검사 이력 | MainServer Job·Unit API | 동일 | 부분 구현 | 단건 조회만 존재 |
| 재고·조립 가능 여부 | MainServer Product API | 동일 | Backend 구현 | UI 공개 범위 재검토 중 |
| 사람 감지 안전정지 | 없음 | 없음 | 미구현 | 로봇·컨베이어 동시 정지 필요 |
| E-STOP 연동 | 상태 표시 일부 | `/nonrt_state_data` | 부분 구현 | 표시만 존재, 작업 정지 연동 없음 |

| 공통 API 기능 | 발행·요청 주체 | 구독·처리 주체 | API | 구분 | 메시지 타입 | 비고 |
| --- | --- | --- | --- | --- | --- | --- |
| PARTS 영상 | ROS2 / 비전 노드 | Unity / `CamVisionReceiver` | `/vision/parts_obb/image/compressed` | Topic | `sensor_msgs/CompressedImage` | 활성 Scene 구독 |
| TRAY 영상 | ROS2 / 비전 노드 | Unity / `CamVisionReceiver` | `/vision/tray/detections_image/compressed` | Topic | `sensor_msgs/CompressedImage` | RUN 동적 구독 |
| CONVEYOR 영상 | ROS2 / 비전 노드 | Unity / `CamVisionReceiver` | `/vision/conveyor/stop_image/compressed` | Topic | `sensor_msgs/CompressedImage` | RUN 동적 구독 |
| CELL 영상 | ROS2 / 카메라 노드 | Unity / `CamVisionReceiver` | `/camera3/image_raw/compressed` | Topic | `sensor_msgs/CompressedImage` | RUN 동적 구독 |
| 검출 Pose | ROS2 / 비전 노드 | Unity / `VisionDetector` | `/vision/board/capture/target_pose` | Topic | `geometry_msgs/PoseStamped` | 코드만 존재·Scene 미연결 |
| 선택 대상 ID | ROS2 / 비전 노드 | Unity / `VisionDetector` | `/vision/board/selected_target` | Topic | `std_msgs/String` | 코드만 존재·Scene 미연결 |

| Mock API 기능 | 발행·요청 주체 | 구독·처리 주체 | API | 구분 | 메시지 타입 | 비고 |
| --- | --- | --- | --- | --- | --- | --- |
| 자동 조립 시작·상태 조회 | Unity / `MockAssemblyScenarioControl` 또는 MainServer / `AssemblyGateway` | ROS2 / `mock_movej` 또는 `mock_db_bridge` 노드 | `/unity/assembly/start` | Service | `fairino_msgs/srv/RemoteCmdInterface` | `start`·`status` JSON 사용 |
| 조립 진행·완료·실패 | ROS2 / `mock_movej` 또는 `mock_db_bridge` 노드 | Unity / `MockAssemblyScenarioControl` | `/unity/assembly/feedback` | Topic | `std_msgs/String` | `STARTED`·`PICKED`·`PLACED`·`COMPLETED`·`FAILED` |
| 관절 목표 | Unity / `MockRobotControl` | ROS2 / `mock_movej` 노드 | `/unity/joint_target` | Topic | `sensor_msgs/JointState` | MANUAL UI 미연결 |
| MoveJ 목표 | Unity / `MockRobotControl` | ROS2 / `mock_movej` 노드 | `/unity/movej_target` | Topic | `geometry_msgs/PoseStamped` | MANUAL UI 미연결 |
| TCP 직선 이동 | Unity / `MockRobotControl` | ROS2 / `mock_movej` 노드 | `/unity/tcp_target` | Topic | `geometry_msgs/PoseStamped` | MANUAL UI 미연결 |
| 그리퍼 개도 | Unity / `MockRobotControl` | ROS2 / `mock_movej` 노드 | `/unity/gripper_target` | Topic | `std_msgs/Float32` | 0~100%, MANUAL UI 미연결 |
| 로봇 상태 | ROS2 / `joint_state_broadcaster` | Unity / `MockRobotStateSource` | `/joint_states` | Topic | `sensor_msgs/JointState` | J1~J6·그리퍼 상태 |
| 명령 결과 | ROS2 / `mock_movej` 노드 | Unity / `MockRobotControl` | `/twin_visual/status` | Topic | `std_msgs/String` | 완료·오류·timeout |

| Real API 기능 | 발행·요청 주체 | 구독·처리 주체 | API | 구분 | 메시지 타입 | 비고 |
| --- | --- | --- | --- | --- | --- | --- |
| MoveJ | Unity / `RealRobotControl` | ROS2 / `fr_command_server` 노드 | `/fairino_remote_command_service` | Service | `fairino_msgs/srv/RemoteCmdInterface` | `/nonrt_state_data` 실제 완료까지 대기 |
| TCP MoveCart | Unity / `RealRobotControl` | ROS2 / `fr_command_server` 노드 | `/fairino_remote_command_service` | Service | `fairino_msgs/srv/RemoteCmdInterface` | Context Menu 디버그 전용 |
| 그리퍼 | Unity / `RealGripperRequest` | ROS2 / `fr_command_server` 노드 | `/fairino_remote_command_service` | Service | `fairino_msgs/srv/RemoteCmdInterface` | 서비스 응답만 확인 |
| 로봇 상태 | ROS2 / `fr_command_server` 노드 | Unity / `RealStatusSubscriber` | `/nonrt_state_data` | Topic | `fairino_msgs/msg/RobotNonrtState` | 관절·TCP·안전·오류·완료 상태 |
| 자동 조립 시작 | Unity / `RealAssemblyScenarioControl` | ROS2 / `real_assembly` 노드 | `/real/assembly/start` | Service | `real_assembly_interfaces/srv/StartAssembly` | 설계됨·미구현 |
| 자동 조립 상태 조회 | Unity / `RealAssemblyScenarioControl` | ROS2 / `real_assembly` 노드 | `/real/assembly/status` | Service | `real_assembly_interfaces/srv/GetAssemblyStatus` | 설계됨·미구현 |
| 조립 진행·완료·실패 | ROS2 / `real_assembly` 노드 | Unity / `RealAssemblyScenarioControl` | `/real/assembly/progress` | Topic | `real_assembly_interfaces/msg/AssemblyProgress` | 설계됨·미구현 |

| MainServer API 기능 | Method | Path | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| 조립 시작 | `POST` | `/api/v1/assemblies` | 구현 | ROS2 `/unity/assembly/start`로 전달 |
| 현재·마지막 조립 조회 | `GET` | `/api/v1/assemblies/current` | 구현 | ROS Snapshot 반환 |
| 제품·조립 가능 수량 | `GET` | `/api/v1/products` | 구현 | 상세 UI 범위 재검토 중 |
| 제품 슬롯·부품 구성 | `GET` | `/api/v1/products/{product_id}` | 구현 | 제품 상세 |
| 필요·보유·부족 수량 | `GET` | `/api/v1/products/{product_id}/requirements` | 구현 | `quantity` Query 사용 |
| Job 진행률 | `GET` | `/api/v1/jobs/{job_id}` | 구현 | Unity의 `job_id` 발견 경로 미완성 |
| Unit·검사·불량 | `GET` | `/api/v1/jobs/{job_id}/units` | 구현 | INSPECT UI 미연결 |
| 슬롯별 불량률 | `GET` | `/api/v1/products/{product_id}/quality/slot-rates` | 구현 | QUALITY UI 미연결 |
