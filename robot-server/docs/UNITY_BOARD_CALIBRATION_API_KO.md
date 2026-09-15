# Unity 트레이·기판 캘리브레이션 API

로봇 PC의 기존 트레이 검출과 PlaceCamera 기판 추적 결과를 외부 Unity에 전달한다. 이 API는 로봇·컨베이어를 이동하지 않는다. 기존 `/vision/tray/detect_parts`, `/vision/pcb/calibrate_pose` Action 계약은 유지된다.

## 연결

- ROS TCP Endpoint: 로봇 PC `192.168.11.5:10000` (현장 네트워크 주소).
- Unity 요구 패키지: ROS-TCP-Connector, Newtonsoft JSON, `std_msgs/String` 메시지.
- 요청: `/vision/unity/request`, 응답: `/vision/unity/response` — 모두 `std_msgs/String` 안의 JSON.
- 기판 실시간 상태: `/vision/board/unity_state` — `std_msgs/String`.
- 기존 트레이 실시간 상태: `/vision/tray/unity_state` — 기존 `TrayVisionSynchronizer.cs` 사용.
- 서버 단독 시작: `./run_fr5_assembly_stack.sh calibration-start`. 전체 `start`에도 포함된다.

## 함수

Unity GameObject에 `VisionCalibrationClient`를 붙인다. 응답은 `Completed(JObject response)` / `Failed(string code, string message)`로 받는다. 함수 반환값은 요청 UUID다. 서버 대기 제한은 5초, 클라이언트 통신 제한은 15초이며 자동 재시도는 없다.

```csharp
client.GetTraySnapshot(jobId);
client.GetBoardSnapshot(jobId);
client.CalibrateBoard(jobId);
```

| 함수 | 성공 조건 | 반환 data |
|---|---|---|
| GetTraySnapshot | TrayHome 정지·도착 후 관측·트레이 검출 품질 통과 | 부품 ID/위치/방향과 섹션 기준 이미지 폴리곤 |
| GetBoardSnapshot | PlaceCamera 정지·기판 품질·안정 프레임 4개 | 기판 자세, 외곽, 25개 보정 슬롯 |
| CalibrateBoard | 위 조건 + 요청 이후 새 프레임 4개 + 컨베이어 정지 확인 | 확정 관측 스냅샷과 calibration_id |

관측은 원본 ROS 타임스탬프 기준 2.5초 이내여야 한다. 카메라 위치는 기존 티칭값 대비 위치 각 축 1mm, 각도 각 축 1도 이내, Tool1/User0, 정지 피드백을 요구한다. 도착 후 2초가 지난 프레임을 사용한다. 기판 안정성은 4개 서로 다른 원본 프레임의 자세 차이가 1mm/1도 이내인지 확인한다.

`calibrateBoard`는 실제 컨베이어 제어 주체가 `/orchestrator/conveyor_stopped` Bool을 주기적으로 발행해야 한다. 2026-09-08부터 구독은 reliable/volatile이며, 한 번 보낸 정지값이나 과거 latched true는 보정 허가로 사용하지 않는다. 단순 연결 테스트를 위해 정지 신호를 만들어 보내면 안 된다.

기본 heartbeat 유효시간은 `orchestration_api.pcb.conveyor_heartbeat_max_age_sec: 1.0`초다. 실제 제어 주체는 정지 상태를 5Hz 등 유효시간보다 충분히 짧은 간격으로 계속 발행하고, 상태가 바뀌면 false를 발행한다. 같은 DDS publisher GID에서 원본 시각이 증가하는 새 true를 최소2회 받아야 정지 확인이 유효하다. 원본/수신 시각 만료, false, 시각 역전·중복, publisher 재시작은 기존 확인을 무효화하며 진행 중 보정에도 적용된다. 발행 측과 수신 측의 시스템 시각이 맞아야 한다.

DDS publisher GID는 통신 발행 세션을 구별하는 값이다. 컨베이어의 물리 정지나 제어기 내부 세션을 독립적으로 증명하지 않는다. 실제 정지 확인 책임은 컨베이어 제어 주체에 있다.

```json
{
  "request_id": "unique-request-id",
  "job_id": "assembly-job-001",
  "action": "calibrateBoard",
  "product_code": "printed_semiconductor_package_board",
  "product_version": "assembly-r1"
}
```

응답에는 `schema: fr5.unity.calibration_response/v1`, 동일한 `request_id/job_id/action`, `success`, `error_code`, `message`, `data`가 들어간다. 같은 요청 ID와 같은 내용을 다시 보내면 최근 128건 내에서 원래 결과를 반환한다. 새로운 관측이 필요하면 새 ID를 사용한다. 동시에 최대 16건을 처리한다.

주요 실패 코드: `CAMERA_POSE_NOT_READY`, `CAMERA_NOT_READY`, `DETECTION_TIMEOUT`, `UNSTABLE_POSE`, `CONVEYOR_NOT_STOPPED`, `WRONG_PCB`, `CALIBRATION_NOT_READY`, `FRAME_TRANSFORM_FAILED`, `INVALID_REQUEST`.

## Unity 기판 적용

1. `BoardVisionSynchronizer.cs`, `VisionCalibrationClient.cs`를 Unity 프로젝트로 복사한다.
2. `BoardVisionSynchronizer`의 `baseFrameOrigin`에 기존 트레이와 같은 FR5 Base 원점을 넣는다. 기준 Transform 계층의 스케일은 1이며 Unity 1단위는 1m다.
3. 별도의 빈 `boardFrame`을 할당하고 기판 시각 모델을 그 자식으로 둔다. 이 스크립트는 boardFrame 위치/회전과 25개 `VisionSlot_슬롯코드` 빈 앵커를 갱신한다. 슬롯 시각화 모델은 `Slots` 사전으로 연결한다.
4. `rosXyzToUnityXzy`와 `axisSigns`는 기존 트레이 좌표축 설정에 맞춘다. 기판 모델 고유 축 보정은 시각 모델 자식에 적용한다.
5. 클라이언트의 `boardSynchronizer`에 해당 컴포넌트를 할당한다. 성공한 기판 응답이 자동 적용된다. 실시간 토픽도 자동 구독한다.
6. `IsLive`, `LastError`, `CalibrationId`, `BoardUpdated`로 화면 상태를 표시한다. 카메라가 떠나거나 검출이 실패하면 마지막 위치는 남지만 `IsLive=false`가 된다. 통신 단절도 3초 후 같은 상태가 된다.

기판 메시지 스키마는 `fr5.board.unity_state/v1`이다. `board_pose`, `T_base_board`, `board_size_m`, `outline_board_m`, `slots`, `quality`, `timestamp_ros_ns`, `calibration_id`, `geometry_sha256`, `valid`, `stable`을 제공한다. 실시간 메시지는 `publisher_id/sequence/published_ros_ns`도 포함한다. 원본 관측 시각과 전송 시각은 구별된다.

- 위치 단위는 **m**, 회전은 quaternion **[x,y,z,w]**, 기준은 `base_link`다. 기존 트레이 `base_xyz_mm`과 달리 다시 0.001을 곱하지 않는다.
- 기판 루트는 추적기의 `T_base_board` 그대로다. 물리 기판 크기는 139×110mm다. 모델 크기는 자동 보정하지 않는다.
- 각 슬롯의 `board_position_m`은 PlaceCamera 잔차 보정이 이미 반영된 기판 로컬 좌표다. `base_position_m`은 같은 지점의 FR5 Base 좌표다. `nominal_board_position_m`은 보정 전 설계 좌표다. 잔차를 다시 더하지 않는다.
- `board_orientation_xyzw/base_orientation_xyzw`는 슬롯 긴 축의 기하학적 방향이다. 로봇 그리퍼의 TCP 자세가 아니다.
- 슬롯은 조립 표면 중심이며 approach/retract/TCP 목표가 아니다. 실제 `pickItem/placeItem`과 단계별 IK/Ghost 명령은 기존 로봇 API를 사용한다.
- 트레이의 `section_reference`는 기준 이미지 크기와 정규화 폴리곤이다. 현재 카메라 영상 또는 로봇 좌표로 변환된 섹션이 아니며 `reference_only=true`다. 부품은 `position_m/orientation_xyzw`와 원래 ID를 함께 제공한다.

설정 원본은 `physical_board.json`, `assembly_slots_r1.json`, `assembly_placecamera_residual.json`, `tray_layout_candidate.json`이다. 서버 시작 시 로드하므로 변경 후 해당 API를 재시작한다. 추적기 슬롯과 설정 계산 결과가 다르면 성공을 반환하지 않는다.

## 검증 범위

Python 테스트는 25개 슬롯 변환·잔차 1회 적용·오래된 관측·불안정 관측·요청 상관관계·컨베이어 조건·카메라 위치 조건을 검증한다. Unity Editor 컴파일 및 실제 모델 배치는 외부 Unity 프로젝트에서 확인해야 한다.
