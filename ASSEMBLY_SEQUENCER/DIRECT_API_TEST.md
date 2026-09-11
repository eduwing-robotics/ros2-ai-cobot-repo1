# 컨베이어·Vision API 직접 송신 점검

기준 계약은 `src/assembly_sequencer/assembly_sequencer/api_contracts.py`이다.
컨베이어는 `std_srvs/srv/Trigger`, Vision 검사는 `vision_interfaces/srv`를 사용한다.
`OUT/Vsion/API_CONTRACT.md`의 HTTP multipart 계약은 이 Sequencer가 소비하는 ROS API가 아니다.

## 1. 환경 준비

```bash
cd /home/codlab/Main_Unity/ASSEMBLY_SEQUENCER
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=5
chmod +x tools/direct_api_test.sh
```

`vision_interfaces`를 아직 빌드하지 않았다면 이 workspace 루트에서 먼저 실행한다.

```bash
colcon build --packages-select vision_interfaces assembly_sequencer
source install/setup.bash
```

## 2. 무동작 사전 점검

```bash
./tools/direct_api_test.sh endpoints
./tools/direct_api_test.sh conveyor-state
./tools/direct_api_test.sh vision-health
```

컨베이어 출발 전 `/conveyor/state`에서 다음을 확인한다.

- `schema_version=1`, `moving=false`
- 상태가 `IDLE`, `ASSEMBLY_STOP`, `INSPECTION_STOP` 중 하나
- `armed=true`, `vision_ready=true`, `vision_ready_fresh=true`
- `server_instance_id`가 비어 있지 않음
- `fr5_interlock_required=true`일 때만 `fr5_clear=true`, `fr5_clear_fresh=true` 필요

Vision health는 `success=true`만 보지 말고 `message` JSON의 촬영 준비 상태를 확인한다.

## 3. 컨베이어 직접 송신

아래 명령은 실제 벨트를 움직일 수 있으므로 비상 정지 접근, 작업 반경, 정지선 Vision을 먼저 확인한다.

```bash
./tools/direct_api_test.sh conveyor-assembly
./tools/direct_api_test.sh conveyor-inspection
./tools/direct_api_test.sh conveyor-stop
./tools/direct_api_test.sh conveyor-reset
```

이동 응답의 `success=true`는 수락일 뿐 도착이 아니다. 응답 JSON의 `motion_id`를 보관하고,
`/conveyor/state`의 같은 `motion_id` 및 `arrival.motion_id`, 목적지 `arrival.station`,
해당 STOP 상태, `moving=false`를 모두 확인한다. 응답이 유실되면 이동 요청을 자동 재전송하지 않는다.

## 4. Vision 직접 송신

검사·Job UUID는 실제 실행에서 발급한 값을 재사용하고 Unit ID도 DB의 실제 Unit과 맞춰야 한다.

```bash
./tools/direct_api_test.sh vision-submit INSPECTION_UUID JOB_UUID UNIT_ID
./tools/direct_api_test.sh vision-get INSPECTION_UUID
./tools/direct_api_test.sh vision-image INSPECTION_UUID
./tools/direct_api_test.sh vision-image INSPECTION_UUID PM-01 0
```

submit의 `success=true`는 접수 또는 기존 요청 확인이며 검사 완료/PASS가 아니다.
get의 `record_json`이 `COMPLETED`가 될 때까지 동일 `inspection_id`로 조회한다.
이미지는 응답의 `eof`, `offset`, `total_bytes`, `sha256`를 이용해 전체 조각을 재조립해야 한다.
테스트 도구의 `vision-image`는 한 조각을 관찰하기 위한 명령이다.

## 5. 중단 기준

- `/conveyor/state`가 1초 이상 수신되지 않거나 `FAULT`/`MANUAL_STOP`
- `vision_ready` 또는 `vision_ready_fresh`가 true가 아님
- 다른 `/cmd_vel` publisher, 수신 로봇 부재, 서버 instance 변경
- 서비스 timeout 또는 응답 유실로 실제 수락 여부를 확정할 수 없음

이 경우 성공으로 기록하거나 같은 이동을 재요청하지 말고 컨베이어 정지와 현장 상태를 먼저 확인한다.
