# 통합 체크리스트

## A. 코드·환경

- [ ] 구현이 포함된 branch를 pull했다.
- [ ] `vision_interfaces`, `vision_server` 빌드가 성공했다.
- [ ] 모든 ROS 컴퓨터가 같은 네트워크와 `ROS_DOMAIN_ID=5`를 사용한다.
- [ ] Unity ROS-TCP Endpoint `10000` 연결이 성공했다.
- [ ] `assembly_recipe_r1.yaml`이 YAML parser로 정상 로드된다.

## B. Monitor-only 시험

- [ ] `run_s22_conveyor_hq.sh`가 실행 중이다.
- [ ] `/vision/conveyor/stop_line_ready`가 fresh하게 발행된다.
- [ ] `run_conveyor_remote_server.sh --monitor-only`가 실행된다.
- [ ] `/conveyor/state`에서 `armed=false`를 확인했다.
- [ ] 이동 서비스가 `success=false`, disarmed 사유로 거절된다.
- [ ] `/conveyor/stop`은 성공하고 `MANUAL_STOP`이 된다.
- [ ] `/conveyor/reset` 후 `IDLE`이 된다.

## C. FR5 interlock 시험

- [ ] 실제 FR5 상태 기반 clear publisher가 최소 10 Hz로 동작한다.
- [ ] FR5 작업영역 안에서 clear=false다.
- [ ] FR5 작업영역 밖에서 clear=true다.
- [ ] clear=false에서는 이동 서비스가 거절된다.
- [ ] heartbeat를 끊으면 250 ms 안에 FAULT 조건이 된다.
- [ ] `/cmd_vel` publisher가 원격 서버 하나뿐이다.

## D. 저속 실물 시험

- [ ] 물리 비상정지와 작업자 감시를 준비했다.
- [ ] 빈 컨베이어에서 방향과 정지를 확인했다.
- [ ] 기판 한 장으로 assembly 이동·정지를 확인했다.
- [ ] `ASSEMBLY_STOP` 전에는 조립 sequence가 시작되지 않는다.
- [ ] FR5 후퇴 후 inspection 이동·정지를 확인했다.
- [ ] `INSPECTION_STOP` 전에는 검사가 시작되지 않는다.
- [ ] 이동 중 S22 heartbeat 단절 시 즉시 정지한다.
- [ ] 이동 중 FR5 clear=false 시 즉시 정지한다.
- [ ] 이동 중 원격 stop 버튼이 즉시 정지한다.
- [ ] 30초 timeout 시 FAULT 정지한다.

## E. DB·Unity

- [ ] Unity가 300 ms 상태 heartbeat timeout을 FAULT로 표시한다.
- [ ] Unity 버튼이 서비스 응답의 success/message를 표시한다.
- [ ] DB는 상태 변화만 저장하고 10 Hz 상태를 전부 중복 저장하지 않는다.
- [ ] DB는 `(cycle_id, station, event_type)` 중복을 차단한다.
- [ ] DB와 Unity 모두 서비스 수락과 물리 도착 상태를 구분한다.

## 남은 필수 통합 항목

- FR5/Main Server의 `/cell/fr5_clear_for_conveyor` 실제 publisher
- 생산 `cycle_id` 생성·복구·중복 요청 정책
- 모터 encoder가 있다면 command state와 분리된 실제 feedback
- `inspect_assembled_pcb`, `transfer_assembled_pcb` 실행기 연결
