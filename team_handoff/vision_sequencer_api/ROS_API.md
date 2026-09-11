# Vision 검사 ROS 2 계약 — 2026-09-11

촬영 요청, 상태/결과 조회, 전체 PNG와 대책서 PNG 조회는 ROS 2로 전환되었습니다.
HTTP 8766, Bearer 토큰, POST/GET은 새 실행 경로에서 사용하지 않습니다.
컨베이어 이동/정지 서비스는 기존 그대로이며 **팀원 ROS-TCP Endpoint의 실행과 설정은 변경하지 않습니다.**

## 빌드와 실행

서버와 ROS 클라이언트 PC 모두 갱신된 `vision_interfaces`가 필요합니다.
이 저장소의 `ros2_ws/src/vision_interfaces` 패키지를 각 ROS 작업공간에 넣고 빌드합니다.

```bash
source /opt/ros/jazzy/setup.bash
cd ~/KSMC/ros2_ws
colcon build --packages-select vision_interfaces
source install/setup.bash
export ROS_DOMAIN_ID=5
```

ROS 분산 통신은 기존 DDS/네트워크 설정을 따릅니다. ROS_DOMAIN_ID는 인증 수단이
아니며 기존 셀의 ROS 네트워크 접근 정책이 적용됩니다. HTTP 토큰 파일은 삭제하거나
재발급하지 않습니다. Unity에서 새 서비스를 사용하려면 팀원 클라이언트 측에서 새
`.srv` 타입에 대응해야 합니다. 이 변경에는 Endpoint 수정/재시작이 포함되지 않습니다.

검사 서버만 실행:

```bash
~/KSMC/vision_assembly/run_conveyor_inspection_trigger.sh --timeout 300
```

컨베이어+검사 서버 통합 실행은 [통합 실행 가이드](../../docs/CONVEYOR_VISION_SERVER.md)를
따릅니다. 통합 실행은 GoPro도 시작하거나 기존 스트림을 재사용합니다. S22/ROI는
기존 실행 상태가 필요합니다. 기존 컨베이어/검사 서버는 자동 인수하지 않습니다.
기존 `inspection_api.py`를 직접 실행해도 이제 ROS 서버가 시작되며 `--host/--port`는 거절합니다.

## 요청과 결과

| 서비스 | 타입 | 용도 |
|---|---|---|
| `/vision/inspection/submit` | `vision_interfaces/srv/SubmitInspection` | 명시적 촬영·검사 요청 |
| `/vision/inspection/get` | `vision_interfaces/srv/GetInspection` | ID별 영속 상태·결과 조회 |
| `/vision/inspection/get_image` | `vision_interfaces/srv/GetInspectionImage` | PNG 조각 조회 |
| `/vision/inspection/health` | `std_srvs/srv/Trigger` | 서버 가용성·촬영 준비 상태 조회 |

`submit` 요청: `inspection_id`, `job_id`(UUID 문자열), `unit_id`(양의 int64).
ID는 Sequencer가 발급합니다. 동일 ID·동일 내용은 기존 상태를 돌려주며 재촬영하지
않습니다. 동일 ID·다른 내용은 `inspection_conflict`, 다른 검사 실행 중에는
`inspection_busy`입니다. 응답을 못 받으면 **같은 ID로 get 또는 submit을 재시도**합니다.
새 ID는 새 촬영 요청입니다.

`submit/get` 응답: `success`, `error_code`, `record_json`.
`success=true`는 서비스 요청 성공이며 검사 완료 또는 PASS를 의미하지 않습니다.
`record_json`은 이전 HTTP `data` 객체와 같은 결과 필드들을 갖는 JSON 문자열입니다.

- 공통: inspection_id/job_id/unit_id, status, image, transport=`ros2`.
- 상태: ACCEPTED → RUNNING → COMPLETED 또는 FAILED. 짧은 중간 상태는 조회 사이에 지나갈 수 있습니다.
- 완료: result.decision(PASS/FAIL/UNKNOWN), findings, slots, defects, summary, diagnostics 등 기존 필드.
- `COMPLETED + UNKNOWN`은 생산 합격/불량 확정이 아닙니다. 후보는 ADVISORY_ONLY를 유지합니다.
- `image.ready=false` 또는 `result.details_ready=false`는 자료 준비 실패/미준비입니다.
- 이미지 메타데이터의 HTTP `path`를 제거하고 `service`, `slot_code`, `max_chunk_bytes`를 제공합니다.

촬영 접수는 `/conveyor/moving=false`와 검사 stop_trigger=true가 각각 1초 이내에
수신되었고 0.35초 이상 유지된 때만 허용합니다. 실행 직전에도 재확인합니다.
도착만으로 촬영하지 않으며, 컨베이어/로봇 명령을 보내지 않습니다. 촬영 잠금,
단일 작업 실행, 기존 검사/재촬영 엔진과 timeout(기본 300초)을 유지합니다.
서버 재시작 시 중단된 작업은 FAILED로 복구하고 자동 재실행하지 않습니다.
기존 저장 위치 `runtime/inspection/api`와 결과 기록을 재사용합니다.

오류는 `success=false`와 문자열 `error_code`로 전달합니다. 주요 코드는
`invalid_identity`, `inspection_conflict`, `inspection_busy`, `station_not_ready`,
`inspection_not_found`, `worker_unavailable`, `internal_error`입니다.
FAILED의 실행 오류는 record.error로 확인합니다.

## PNG 전송

`get_image` 요청: inspection_id, slot_code, offset, max_bytes.

- slot_code=`''`: 기본 `02_annotated_report.png`.
- slot_code=`ALL` 또는 반환된 countermeasure_views의 slot_code: 해당 대책서 PNG.
- offset은 0부터 시작하는 바이트 위치, max_bytes는 1..65536.
- 응답은 success/error_code, inspection_id/slot_code, filename, mime_type,
  sha256, total_bytes, offset, eof, `uint8[] data`입니다.
- 수신 길이만큼 offset을 증가시켜 eof까지 조회하고 크기·SHA256을 검증한 뒤 파일을 확정합니다.
  이미지 바이트를 대용량 토픽으로 반복 발행하지 않습니다.
- 서버는 요청마다 PNG 서명/크기/해시를 검증합니다. 손상은 `image_integrity_error`,
  미준비는 `image_not_ready`, 없는 대책서는 `countermeasure_image_unavailable`,
  범위 오류는 `invalid_image_range`입니다. 현재 파일 상한은 64 MiB입니다.
- 원본 ROI/전체 로컬 package/ZIP은 이 서비스의 전송 대상이 아닙니다.

## 상태 토픽과 클라이언트 예제

`/vision/inspection/state`: `std_msgs/msg/String`, JSON 상태 변경 알림.
RELIABLE + TRANSIENT_LOCAL, KEEP_LAST 32, 0.2초마다 변경 확인.
내용은 inspection_id/job_id/unit_id/status/decision/error입니다. 중간 전이는 합쳐질 수
있고 최근 알림만 보관하므로 **ID별 get이 최종 근거**입니다. 재연결 시 get으로 복구합니다.
health.success는 서버 가용성이며 촬영 허가가 아닙니다. message JSON의
station_ready/active_inspection_id/closing으로 현재 상태를 확인합니다.

조회만 수행하는 예시(기존 ID로 바꾸세요):

```bash
source ~/KSMC/scripts/ksmc_env.sh
python3 ~/KSMC/vision_assembly/integration/inspection_ros_client.py \
  --inspection-id 69f7a921-b98d-4fc8-91ac-e23dbe91ac71 --output /tmp/inspection-result
ros2 service call /vision/inspection/health std_srvs/srv/Trigger '{}'
```

**실제 촬영 요청 예시**: 준비된 검사 위치에서 Sequencer가 발급한 ID를 사용합니다.

```bash
python3 ~/KSMC/vision_assembly/integration/inspection_ros_client.py \
  --inspection-id 69f7a921-b98d-4fc8-91ac-e23dbe91ac71 \
  --job-id 12345678-1234-5678-1234-567812345678 --unit-id 42 \
  --wait 360 --output /tmp/inspection-result
```

`--slot ALL`을 추가하면 전체 대책서 PNG를 저장합니다. 새 예제 클라이언트는 직접
HTTP 연결이나 DB 쓰기를 하지 않습니다. MainServer/Sequencer의 실제 소비 코드는
팀원 쪽에 이 서비스를 연결해야 하며, 이 저장소 밖의 서버는 변경하지 않았습니다.

## 검증 범위와 운영 전환

모의 runner/합성 PNG와 격리된 localhost ROS domain 219에서 직렬화, 요청·조회,
중복 요청, UNKNOWN 보존, 상태 토픽, 조각 이미지 전송을 검증합니다. 이는 실제
S22 촬영, 장비 움직임, 다중 PC DDS 성능 또는 생산 판정 정확도 검증이 아닙니다.
실행 중인 HTTP/컨베이어 서버는 이번 코드 작업에서 종료하지 않았습니다.
컨베이어 정지 및 검사 작업 종료 후 기존 서버를 종료하고 새 실행기로 시작해야
운영 프로세스에도 변경이 적용됩니다. Endpoint는 팀원의 기존 실행을 유지합니다.
