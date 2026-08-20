# S22 Vision + TurtleBot Conveyor ROS Architecture

## 확인한 하드웨어 구조

- 실물 영상: `/home/hc/Downloads/터틀봇 컨베이어.MOV`
- 모델 이미지: `/home/hc/Downloads/컨베이어 모델링.png`
- TurtleBot 구동륜이 컨베이어 롤러를 직접 회전시키는 구조다.
- TurtleBot의 ROS 속도 명령을 컨베이어 모터 명령으로 재사용할 수 있다.

## 권장 제어 구조

```text
Galaxy S22 image
  -> camera2 ROS image topic
  -> conveyor_roi
       - multiple-board contour detection
       - assembly trailing-edge line
       - downstream inspection trailing-edge line
       - two-board spacing validation
  -> conveyor_controller
       - one explicitly selected station per run
       - heartbeat/trigger watchdog
       - HOLD_STOP
  -> TurtleBot /cmd_vel (TwistStamped on the tested Burger)
  -> wheel/roller/belt
```

## 상태 머신

1. `IDLE`: 속도 0, 기판 대기
2. `RUN_FAST`: 기판이 멀리 있을 때 정상 이송
3. `ASSEMBLY_STOP`: 첫 정지선 trigger에서 0 속도를 연속 발행
4. `ASSEMBLY_READY`: 정지 후 기판 pose 품질 조건을 통과하면 FR5 조립 허가
5. `ASSEMBLING`: 컨베이어 정지 interlock 유지
6. `MOVE_TO_INSPECTION`: FR5 후퇴 확인 후 두 번째 정지선까지 명시적으로 이동
7. `INSPECTION_STOP`: 검사 정지선 trigger에서 0 속도를 연속 발행
8. `INSPECTING`: S22 전체 검사와 필요 시 D435 근접 검사
9. `RELEASE`: PASS/FAIL 기록 후 다음 공정으로 이송
10. `FAULT`: 영상 끊김, 간격 부족, 통신 오류, 사람 감지 시 속도 0 유지

현재 구현은 `ASSEMBLY_STOP`과 `INSPECTION_STOP`까지다. FR5 작업영역 interlock,
정지 후 board pose 품질 판정, 검사 결과에 따른 RELEASE는 Main Server 상태 머신에
연결할 예정이며 구현 완료로 간주하지 않는다.

## S22 정지 제어

- 영상의 컨베이어 진행축을 1차원 좌표 `s`로 정의한다.
- `e = s_target - s_board`를 계산한다.
- 멀리 있을 때 빠른 속도, pre-stop 구간에서 낮은 속도, 목표 근처에서 짧은
  pulse 또는 매우 낮은 속도를 사용한다.
- `|e|`가 허용 범위 안이고 여러 프레임 동안 기판 속도가 0에 가까울 때만
  `ASSEMBLY_READY`를 발행한다.
- 오버슈트 후 역회전은 벨트 장력과 백래시를 확인한 뒤 허용한다. 초기 MVP는
  역회전보다 충분히 이른 감속을 우선한다.

광전센서나 stopper가 없어도 공정은 가능하다. 기판이 정확히 같은 점에 멈추지
않아도 S22가 정지 후 실제 `T_base_board`를 다시 계산하므로, 기판이 FR5 작업
영역과 S22 시야 안에서 완전히 정지하기만 하면 CAD slot 좌표를 보정할 수 있다.

## 권장 ROS 인터페이스

실제 TurtleBot topic은 실행 중 `ros2 topic list`와 `ros2 topic info -v`로 확인해
아래 namespace에 remap한다.

```text
/camera2/image_raw/compressed       sensor_msgs/CompressedImage
/cmd_vel                            geometry_msgs/TwistStamped
/conveyor/state                     std_msgs/String 또는 custom state message
/conveyor/speed_feedback            std_msgs/Float32 (가능한 경우)
/board/detected                     std_msgs/Bool
/board/pose_base                    geometry_msgs/PoseStamped
/board/aligned                      std_msgs/Bool
/assembly/ready                     std_msgs/Bool
/inspection/result                 custom result message
```

현재 구현된 정지선 설정 인터페이스:

```text
/vision/conveyor/stop_image/compressed    sensor_msgs/CompressedImage
/vision/conveyor/assembly/stop_trigger    std_msgs/Bool
/vision/conveyor/inspection/stop_trigger  std_msgs/Bool
/vision/conveyor/{station}/stop_line_normalized  std_msgs/Float32
/vision/conveyor/board_count               std_msgs/Int32
/vision/conveyor/station_spacing_valid     std_msgs/Bool
/vision/conveyor/station_spacing_board_lengths  std_msgs/Float32
/vision/conveyor/stop_line_ready          std_msgs/Bool
```

`conveyor_roi`는 `/cmd_vel`을 발행하지 않는다. 영상 왼쪽→오른쪽 이송에서 기판
왼쪽 후단이 각 세로선을 통과하면 station별 trigger를 만든다. 두 선 사이가 현재
검출 기판 한 장 길이와 여유보다 좁으면 ready를 false로 만들어 제어 노드가
fail-safe 정지한다. 이전 단일 정지선 토픽은 assembly 별칭으로만 유지한다.

실제 이송은 아래처럼 두 번 분리한다.

```bash
~/KSMC/run_conveyor_to_assembly.sh
# 조립 완료 및 FR5 후퇴 확인
~/KSMC/run_conveyor_to_inspection.sh
```

두 번째 명령을 자동 실행하지 않는 이유는 현재 Main Server의 FR5-컨베이어 상호
배제 interlock이 아직 구현되지 않았기 때문이다.

TurtleBot이 별도 컴퓨터를 사용하면 노트북과 같은 네트워크, 호환되는 ROS 2
message type/QoS, 같은 `ROS_DOMAIN_ID`를 사용한다. 여러 `/cmd_vel` publisher가
충돌하지 않도록 conveyor controller 한 노드만 최종 속도 권한을 갖게 한다.

## 안전 interlock

- S22 영상 timeout 시 즉시 0 속도 및 `FAULT`
- FR5가 조립 구역에 있을 때 컨베이어 속도 0 강제
- 컨베이어 이동 중 FR5의 조립 구역 진입 금지
- board pose가 안정 프레임 수와 reprojection/검출 기준을 통과해야 조립 허가
- DDS/노드 오류 시 마지막 속도를 유지하지 않고 watchdog으로 정지
- GoPro 사람 감지는 보조 정지이며 물리 비상정지를 대체하지 않음

## 구현 순서

1. TurtleBot에서 실제 속도 topic과 message type 확인
2. 낮은 속도로 정방향/정지 명령만 시험
3. S22 ROS 영상 topic 안정화
4. 임시 판 또는 기판 외곽 검출과 영상 진행축 정의
5. 조립/검사 2개 정지선 기반 자동 정지
6. 최종 설치에서 두 정지선과 기판 2장 간격 재등록
7. 정지 후 기판 pose 및 흔들림 검증
8. `assembly/ready`와 FR5-컨베이어 상호 배제 interlock 연결
