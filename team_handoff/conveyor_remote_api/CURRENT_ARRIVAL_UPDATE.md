# S22 현재 도착 확인 및 같은 목적지 재요청

2026-09-10 구현. ROI 노드와 remote server를 모두 업데이트해야 합니다.
Sequencer 소스는 이 저장소에 없으므로 아래 클라이언트 분기는 팀원 측 적용이 필요합니다.
기존 `stop_trigger`와 `arrival` 기록의 의미는 유지됩니다.

## 현재 위치 조회

- `/vision/conveyor/assembly/arrival_observation`: `std_msgs/msg/String` JSON
- `/vision/conveyor/inspection/arrival_observation`: 같은 구조
- `/conveyor/check_assembly_arrival`: `std_srvs/srv/Trigger`, 읽기 전용
- `/conveyor/check_inspection_arrival`: 같은 구조
- `/conveyor/state.live_arrival.{assembly,inspection}`: 서버에서 유효성을 재확인한 결과

조회 서비스의 `success=true`는 **현재 영상과 정지 명령 상태에 근거한 AT_STATION**입니다.
`message`는 `{station,status,at_station,observation}` JSON입니다.
이 조회는 이동·reset·상태 변경을 하지 않습니다. `success=false`/`UNKNOWN`은
확인 불가이므로 도착으로 처리하지 않습니다.

도착 조건은 최신 원본 프레임, 해당 위치의 기판 후보 1개, 연속 위치 안정성,
최신 컨베이어 정지 상태와 명령 속도 0입니다. 원본 영상의 시간과 컨베이어
상태 시간 모두 유효해야 합니다. ROI와 서버의 수신 watchdog도 유지됩니다.
현재 픽셀 기준은 960px 영상 폭에서 정지선 ±8px, 중심/외곽 폭·높이 변화 범위
2px 이하, 최소 5개 서로 다른 프레임과 0.4초입니다. 영상 폭에 비례해 환산합니다.
이는 초기 영상 판정 기준이며 로봇 조립 포즈의 실측 허용 오차나 엔코더 정지 인증이 아닙니다.

영상 누락·가림으로 미검출·후보 중복·stale/중복 프레임·움직임·수동 정지·FAULT가
있으면 연속 증거를 무효화합니다. 새 프레임이 전혀 없어도 타이머가 만료시킵니다.
표시용으로 유지하거나 평활화한 기판 추적값은 이 판정에 사용하지 않습니다.
완전/부분 가림을 모두 검출한다고 보장하지 않으며 실제 현장 검증이 필요합니다.

## ASSEMBLY_STOP에서 다시 move_to_assembly를 요청한 경우

다음 조건을 모두 만족하면 **새 이동 없이** `success=true`를 반환합니다.

1. 요청 목적지의 STOP 상태이며 진행 중인 target이 없음.
2. armed/영상 ready/다른 cmd_vel 발행자 없음 등 기존 허가 조건을 만족.
3. 기존 `arrival.station` 및 `arrival.motion_id`가 현재 목적지/이동 ID와 일치.
4. 최신 현재 도착 관측이 같은 server_instance_id, motion_id, STOP 상태와 일치.

응답 예시(식별자는 예시):

```json
{
  "accepted": true,
  "already_arrived": true,
  "completed": true,
  "state": "ASSEMBLY_STOP",
  "target": "assembly",
  "motion_id": "server-instance:4",
  "observation_id": "vision-observer:12"
}
```

`motion_id`·기존 도착 기록·상태·타임아웃은 변경하지 않으며 이동/정지 속도
명령도 추가 발행하지 않습니다. 검사 위치에도 같은 규칙을 적용합니다.
오래된 STOP 문자열이나 과거 trigger만 있는 경우에는 기존처럼 거절됩니다.
MOVING/FAULT/MANUAL_STOP 상태를 자동 해제하지 않습니다.

## Sequencer 적용 분기

1. 현재 Job/Unit에 기판이 연결되어 있고 해당 단계가 아직 미완료인지 확인합니다.
2. 위 조회로 현재 도착이 확인되면 그 증거의 서버/이동/관측 ID를 현재 단계에
   기록하고, 새 이동 없이 이동 단계를 한 번만 완료 처리합니다.
3. 이동 요청 응답에 `already_arrived=true`와 `completed=true`가 오면
   새 MOVING 전이나 새 motion_id를 기다리지 않습니다. 최신 도착 조회와
   작업 연결을 확인해 같은 완료 분기로 처리합니다.
4. 일반 이동 수락은 기존처럼 해당 motion_id의 도착을 기다립니다.
5. 확인 불가나 수동 정지는 자동 성공으로 바꾸지 않습니다. 로봇 Start는
   Job/Unit/단계 기준으로 한 번만 호출하고, 중복 재개로 두 번 호출하지 않습니다.

영상의 `observation_id`는 연속 기하 관측 구간 ID일 뿐 기판 시리얼/Unit ID가
아닙니다. Job 등록·DB RUNNING·Sequencer PAUSED를 이 서버가 수정하지 않습니다.

## 적용 및 검증 상태

오프라인 테스트에서는 같은 위치 재요청의 무이동 완료, 증거 만료와 잘못된
서버/이동 ID 거부를 확인했습니다. 실시간 읽기 전용 점검에서는 S22 영상과
실제 MANUAL_STOP/속도0 상태를 수신했고, 자동 도착으로 승격하지 않았습니다.
사용자 승인 후 ROI와 컨베이어·검사 API 묶음을 재시작해 적용했습니다.
중단돼 있던 S22 송신기도 기존 설정으로 복구했습니다. 최종 상태는 IDLE/속도0,
vision_ready=true 및 fresh=true입니다. 두 조회는 현재 정지선 허용 구간 내
기판 후보가 없어 UNKNOWN을 반환합니다. 재시작으로 server_instance_id가 바뀌고
기존 motion_id/arrival은 초기화됐습니다. Sequencer/Job은 재개하지 않았으며
현재 Job/Unit과의 연결 및 위 클라이언트 분기는 팀원 측 적용이 필요합니다. 실물 이동 시험과
Sequencer 전체 재개/로봇 Start 검증은 아직 수행하지 않았습니다.


## 기판을 시작 위치로 되돌린 뒤 처음부터 실행하기 (2026-09-10 적용)

이전 도착 정지 상태가 남아 있더라도, S22가 조립·검사 위치의 벨트 영역이
비었다고 연속 2초/20프레임 이상 확인하면 서버가 자동 IDLE로 전환합니다.
영상·상태 지연이 있으면 연속 확인을 다시 시작하므로 실제 대기 시간은 더 길 수 있습니다.
이전 arrival/motion_id는 지우고 motion_sequence는 보존합니다. 자동 이동은 하지 않습니다.
Unity의 새 실행에서는 IDLE 및 기존 ready 조건을 확인한 뒤 기존
`/conveyor/move_to_assembly`를 요청하면 됩니다. 옛 motion_id/arrival을 재사용하지 않습니다.
이미 목적지에 있는 경우를 처리하는 앞의 no-op 분기와는 별개입니다.

`arrival_observation`에 `regions_empty`, `empty_frames`, `empty_since_ns`가 추가됩니다.
`UNKNOWN`이나 단순 미검출을 클라이언트에서 자체적으로 empty로 간주하지 마세요.
영상 중단·가림/밝기 불일치·구역 내 검출 기판이 있으면 초기화하지 않으며,
MANUAL_STOP/FAULT는 기존 명시적 복구가 필요합니다. 빈 벨트 판정은 현재 고정 S22
시야에 맞춘 기준으로 카메라 이동 시 재검증해야 합니다.

### 명시적 재시도 요청의 빠른 복구 (2026-09-11)

서버가 `ASSEMBLY_STOP` 또는 `INSPECTION_STOP`에 남아 있고 사용자가 기판을
출발 위치로 되돌린 뒤 새 이동 서비스를 요청하면, 두 station payload의
`restart_regions_empty=true`, `restart_empty_frames>=5`,
`restart_empty_since_ns`부터 현재 source frame까지 0.4초 이상인 경우에 한해
그 요청 안에서 이전 completion을 IDLE로 정리하고 새 motion을 접수합니다.
`regions_empty/empty_frames/empty_since_ns`는 기존처럼 2초/20프레임의 수동 없는
자동 IDLE 기준으로 유지됩니다. 따라서 클라이언트는 새 motion ID를 응답에서 받고
이전 ID나 arrival을 재사용하지 않아야 합니다. 한 station이라도 비어 있지 않거나
  증거가 오래됐으면 요청은 기존처럼 거절됩니다. `MANUAL_STOP`은 이 명시적
  빈 증거 요청으로만 IDLE 복구할 수 있고, `FAULT`는 계속 `/conveyor/reset`을
  먼저 호출해야 합니다. 수동 stop/fault를 타이머가 자동 해제하지는 않습니다.

로컬 서버/ROI 적용 및 빈 구역 실시간 관측은 확인했습니다. 실제
‘도착 → 공정 중단 → 기판 시작 위치 복귀 → Unity 새 실행’ 시험은 남아 있습니다.
Job/Unit/조립 이력 정리와 로봇 재실행 처리는 이 컨베이어 초기화가 수행하지 않습니다.

## S22 ready heartbeat 지연 조사 (2026-09-10)

이동 중 조립선에 도착하기 전에 `S22 ready heartbeat missing`으로 FAULT가
발생한 사례를 분석했습니다. 같은 시각 ROI가 185ms 된 프레임을 150ms 안전
기준으로 거절했으며, 기판은 조립선 앞에 있었습니다. Fast DDS가 모든 활성
인터페이스와 blocking UDP를 사용하던 설정을 노트북 프로필에서 정리하고,
GoPro 전용 WLAN을 제외하며 non-blocking UDP와 로컬 SHM을 사용하도록 배포했습니다.
수정 전 30초 측정의 ready false 24회/150ms 초과 간격38회가 수정 후 각각0회/0회로
감소했습니다. 순간적인 영상 구독자 gap은 남아 있어 150ms watchdog은 유지합니다.

노트북 유선 포트는 1Gbps 링크와 `10.77.5.1/30`으로 설정했지만, 로봇의
Ethernet IP가 아직 확인되지 않아 로봇 ROS 경로는 `192.168.11.101` Wi-Fi입니다.
로봇 Ethernet 주소와 ROS 인터페이스를 설정한 뒤에만 유선 경로가 실제로 사용됩니다.
로봇 SSH는 문서 계정 `musk`로 읽기 접속이 인증/시간 초과되어 원격 설정은 하지
않았습니다. 이동·정지·reset·Job 재개는 이 조사에서 호출하지 않았습니다.

노트북에서 DHCP 공유를 잠시 시험했으나 로봇의 lease/ARP 응답이 없어 원래의
`10.77.5.1/30` 수동 주소로 되돌렸습니다. 따라서 현재 로봇 통신은 기존
`192.168.11.101` 무선 경로이며, 유선 전환에는 로봇 측 주소 설정과 ROS 재시작이 필요합니다.
