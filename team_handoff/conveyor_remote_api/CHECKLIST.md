# 통합 체크리스트

## A. 코드·환경

- [ ] 구현이 포함된 branch를 pull했다.
- [ ] `vision_interfaces`, `vision_server` 빌드가 성공했다.
- [ ] 모든 ROS 컴퓨터가 같은 네트워크와 `ROS_DOMAIN_ID=5`를 사용한다.
- [ ] Unity ROS-TCP Endpoint `10000` 연결이 성공했다.
- [ ] `assembly_recipe_r1.yaml`이 YAML parser로 정상 로드된다.

## B. Monitor-only 시험

- [ ] 단일 컴퓨터 운용이면 `run_conveyor_remote_server.sh --with-s22 --monitor-only`가
      실행 중이다. 역할을 분리하면 S22 HQ와 서버를 각각 실행한다.
- [ ] `/vision/conveyor/stop_line_ready`가 `true`로 발행된다.
- [ ] 역할 분리 운용이면 `run_conveyor_remote_server.sh --monitor-only`가 실행된다.
- [ ] Unity ROS-TCP Endpoint(`port 10000`)는 팀원이 별도로 실행 중이다.
- [ ] `/conveyor/state`에서 `armed=false`를 확인했다.
- [ ] 이동 서비스가 `success=false`, disarmed 사유로 거절된다.
- [ ] `/conveyor/stop`은 성공하고 `MANUAL_STOP`이 된다.
- [ ] `/conveyor/reset` 후 `IDLE`이 된다.

## C. FR5 허가 제거 확인

- [ ] FR5 publisher 없이 이동 요청이 수락된다(다른 조건 충족 시).
- [ ] 상태 JSON의 FR5 호환 필드 세 개는 모두 false다.
- [ ] 명시적인 S22 `ready=false` 시 FAULT 정지가 유지된다.
- [ ] 로봇 `/cmd_vel` subscriber가 없을 때 이동 요청이 즉시 거절된다.
- [ ] `/cmd_vel` publisher가 원격 서버 하나뿐이다.

## D. 저속 실물 시험

- [ ] 물리 비상정지와 작업자 감시를 준비했다.
- [ ] 빈 컨베이어에서 방향과 정지를 확인했다.
- [ ] 기판 한 장으로 assembly 이동·정지를 확인했다.
- [ ] `ASSEMBLY_STOP` 전에는 조립 sequence가 시작되지 않는다.
- [ ] FR5 후퇴 후 inspection 이동·정지를 확인했다.
- [ ] `INSPECTION_STOP` 전에는 검사가 시작되지 않는다.
- [ ] 이동 중 S22 `ready=false` 시 즉시 정지한다.
- [ ] FR5 작업영역 이탈을 운용자/상위 시퀀서가 확인한다.
- [ ] 이동 중 원격 stop 버튼이 즉시 정지한다.
- [ ] 30초 timeout 시 FAULT 정지한다.

## E. DB·Unity

- [ ] 팀원이 관리하는 ROS-TCP Endpoint가 TCP `10000`에서 연결됐다.
- [ ] Unity는 `RosMessageTypes.Sensor.CompressedImageMsg`로
      `/vision/conveyor/stop_image/compressed`를 구독한다.
- [ ] Unity `RawImage`에는 `unity/S22ConveyorOverlayView.cs`를 적용하거나
      동일하게 `CompressedImageMsg.data`를 `Texture2D.LoadImage`로 갱신한다.
- [ ] S22 원본 화면은 `/camera2/image_stream/compressed`, GoPro 화면은
      `/camera3/image_raw/compressed`를 `CompressedImageMsg`로 구독한다.
- [ ] Unity 클라이언트가 두 대 이상 연결된 경우 각 화면에 최신 프레임이
      표시되고, 한 클라이언트의 재접속이 다른 클라이언트 화면을 끊지 않는다.
- [ ] Unity 연결 후 `ros2 topic info -v /vision/conveyor/stop_image/compressed`의
      subscription count가 1 이상이고 QoS 불일치 경고가 없다.
- [ ] Unity가 `/conveyor/state`의 `state`, `moving`, `reason`을 표시한다.
- [ ] Unity 버튼이 서비스 응답의 success/message를 표시한다.
- [ ] DB는 상태 변화만 저장하고 10 Hz 상태를 전부 중복 저장하지 않는다.
- [ ] DB는 `(cycle_id, station, event_type)` 중복을 차단한다.
- [ ] DB와 Unity 모두 서비스 수락과 물리 도착 상태를 구분한다.

## 남은 필수 통합 항목

- FR5 작업영역 이탈에 대한 운용자/상위 시퀀서 확인
- 생산 `cycle_id` 생성·복구·중복 요청 정책
- 모터 encoder가 있다면 command state와 분리된 실제 feedback
- `inspect_assembled_pcb`, `transfer_assembled_pcb` 실행기 연결
