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
  -> board_arrival_detector
       - board detection
       - pre-stop ROI
       - assembly target line/pose
  -> conveyor_controller
       - RUN_FAST
       - RUN_SLOW
       - ALIGN
       - HOLD_STOP
  -> TurtleBot /conveyor/cmd_vel (actual remap may be /cmd_vel)
  -> wheel/roller/belt
```

## 상태 머신

1. `IDLE`: 속도 0, 기판 대기
2. `RUN_FAST`: 기판이 멀리 있을 때 정상 이송
3. `PRESTOP`: S22 pre-stop ROI 진입 시 감속
4. `ALIGN`: 목표선/목표 pose 오차에 따라 저속 또는 짧은 pulse 이동
5. `HOLD_STOP`: 0 속도를 연속 발행하고 정지 안정성 확인
6. `ASSEMBLY_READY`: 기판 pose snapshot과 품질 조건을 통과하면 FR5 조립 허가
7. `ASSEMBLING`: 컨베이어 정지 interlock 유지
8. `INSPECTING`: FR5 후퇴 후 S22 전수검사
9. `RELEASE`: PASS/FAIL 기록 후 다음 공정으로 이송
10. `FAULT`: 영상 끊김, 기판 이동, 통신 오류, 사람 감지 시 속도 0 유지

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
/conveyor/cmd_vel                   geometry_msgs/Twist 또는 TwistStamped
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
/vision/conveyor/stop_line_normalized     std_msgs/Float32
/vision/conveyor/stop_line_ready          std_msgs/Bool
```

초기 시험의 `conveyor_roi` 실행 파일은 기판 후단 통과용 정지선과 정규화 위치를
발행하며 `/cmd_vel`을 발행하지 않는다. 현재 가정은 영상 왼쪽→오른쪽 이송이고,
기판 왼쪽 후단이 세로 정지선을 통과하면 정지 trigger를 만드는 방식이다.
감속 기능은 정지 검증 후 필요할 때 추가한다.

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
5. pre-stop/stop ROI 기반 자동 감속·정지
6. 정지 후 기판 pose 및 흔들림 검증
7. `assembly/ready`와 FR5 interlock 연결
