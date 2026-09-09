# Conveyor Work Log

## 2026-09-09 Correlated persistent arrival callbacks

- Added compatible motion_id/arrival fields and teammate callback examples; safety gates and legacy states unchanged. Current direct ROS discovery found trigger publishers but no remote-server state/services; no server was launched or motion commanded. Offline tests cover both stations, repetition, reset/fault and late consumers. Detailed shared validation and limitations: [vision record](vision.md#2026-09-09-arrival-callbacks-and-countermeasure-evidence-cards).

## 2026-09-08 inspection child UNKNOWN retry

- Inspection child now retries UNKNOWN once (max2captures), preserves attempt paths, and recommends HOLD if stillUNKNOWN. PASS/FAIL and offline skip-capture do not retry. No conveyor/robot command; actual Sequencer HOLD handling unverified. Existing API server/request IDs/routes unchanged; next child invocation uses new code and can take longer. Combined tests302passed without hardware. Detailed grouped record: [vision log](vision.md#2026-09-08-bounded-unknown-recapture-pipeline).

## 2026-09-08 freshness and duplicate-request hardening

- Invalid/stale image and heartbeat evidence now inhibits readiness; ready-loss and invalid motion clocks latch stop, while same-active-request retries preserve the original deadline without a stop/restart pulse. Existing geometry/speed/interlocks/topic contracts unchanged.123offline ROS-package tests passed; no publishers, equipment commands or live-server restart. See [grouped behavior and verification](vision.md#2026-09-08-parallel-subsystem-hardening-and-offline-regression-runner); physical stopping and cross-PC timestamp consistency still require operational verification.

## 2026-09-08 additive conveyor and inspection server supervision

- Added an opt-in shared launcher with duplicate/takeover refusal and owned-process-only cleanup; existing conveyor services, safety interlocks, station geometry and request-owned capture behavior are unchanged. Actual-host read-only preflight passed; no conveyor server was started or motor command sent. Mock lifecycle/API tests and existing interlock regression tests passed. See [grouped implementation and verification record](vision.md#2026-09-08-non-disruptive-server-bundle-and-recorded-result-viewer) for details and the still-required idle switchover/teammate live test.

## 2026-09-07 request-owned inspection trigger

- Default run_conveyor_inspection_trigger.sh now serves Sequencer request/pull API rather than firing on arrival. Existing arrival behavior is explicitly --legacy-arrival-trigger only; both use the same process lock. Combined S22 launcher help/token preflight updated. Fresh stopped and arrived messages are prerequisites; arriving without POST does not capture. Automatic direct MainServer delivery removed, evidence pulled by Sequencer. Stop geometry, motor/interlock code unchanged.20 API/export/pipeline tests and shell syntax passed; no physical motion/capture or end-to-end ROS test. See grouped vision log for deployment limitations.

## 2026-09-07 automatic inspection result file delivery

- Arrival-trigger child pipeline now uses existing hybrid25-slot inspector rather than legacy full-board default. Optional file export/HTTP receipt is off by default; completion and delivery states remain separate. No stop geometry, motor command, interlock, rearm policy or conveyor remote server change. Local mocked pipeline tests and HTTP loopback tests passed; physical arrival/capture/inspection/upload sequence not executed. See vision.md grouped MainServer file-only receipt record for details and limitations.

컨베이어 모터·정지 제어 변경만 기록한다. S22 영상 알고리즘은 `vision.md`, FR5
작업은 `robot.md`에서 관리한다.

## 2026-08-20 — 조립 정지와 비전검사 정지를 2단계로 분리

- 한 실행에서 사용할 station을 `assembly` 또는 `inspection`으로 명시하도록
  `conveyor_controller`에 `--station` 옵션을 추가했다.
- 실행 명령을 `run_conveyor_to_assembly.sh`와
  `run_conveyor_to_inspection.sh`로 분리했다. 첫 정지 후 FR5 조립 완료·후퇴를
  확인하지 않은 상태에서 검사선으로 자동 재출발하지 않는다.
- 실제 벨트 전진은 기존 검증값인 TurtleBot `linear.x=-0.10 m/s`를 유지한다.
- 기존 ready heartbeat뿐 아니라 선택한 station trigger 토픽도 1초 watchdog으로
  감시한다. 시작 후 3초 안에 둘 중 하나라도 수신되지 않거나 실행 중 끊기면 속도
  0을 10회 발행하고 종료한다.
- 소프트웨어 검증까지만 수행했으며 이번 변경으로 실제 바퀴·벨트를 구동하지
  않았다. 최종 컨베이어와 S22 고정 후 조립선, 검사선 순서로 각각 저속 실물 정지
  시험을 해야 한다.

### 발표·포트폴리오용 증빙 항목

- S22 화면에 두 정지선과 기판 2장이 동시에 표시된 캡처
- 조립선 trigger와 검사선 trigger가 서로 독립적으로 발생하는 터미널 로그
- 기판 길이보다 정지선 간격이 좁을 때 `station_spacing_valid=false`로 정지하는 로그
- 조립 완료 확인 후에만 두 번째 이동 명령을 실행하는 공정 순서 영상

## 2026-08-20 — 최종 S22 시점의 2개 정지선 재측정

- 현재 고정된 비스듬한 S22 화면에서 빈 기판 지그와 완성 기판 지그를 동시에
  측정했다.
- 지그 손잡이가 기판 중심을 위쪽으로 치우치게 하던 문제를 해결하기 위해 넓은
  본체 단면만 추출하는 검출 로직을 추가했다.
- 1920px 영상 기준 본체 후단은 조립 위치 약 `565.94px`, 검사 위치
  `1344.00px`였고 정규화 정지선은 `0.29491513`, `0.70036477`로 설정했다.
- 두 정지선을 각각 실측하여 S22 원근 왜곡을 반영했다. 실제 벨트 상판 완성 후
  같은 절차로 최종 미세조정한다.
- Vision 테스트 `21 passed`, ROS 패키지 빌드 성공을 확인했으며 실제 컨베이어는
  움직이지 않았다.
- S22 고정 화면에서 TurtleBot 몸체·삼각대·테이블 물체가 간헐적으로 기판으로
  검출되는 문제를 막기 위해 검출 범위를 컨베이어 벨트 띠 `Y=0.42~0.76`으로
  제한했다. 기판 형상 조건도 aspect ratio `1.25~1.90`, rectangularity
  `>=0.78`로 강화했다.
- 최신 S22 실물 프레임에서는 빈 기판과 완성 기판 2개만 유지됐고, 벨트 밖의
  TurtleBot형 어두운 사각 물체를 제외하는 회귀 테스트를 추가했다. Vision 전체
  테스트는 `22 passed`이며 실제 모터는 구동하지 않았다.

## 2026-08-21 - 회전 PCB의 지그 손잡이 제외 보정

- 실제 S22 오버레이에서 PCB가 약간 회전하면 기존 박스가 지그 손잡이까지
  포함하는 문제를 재확인했다. `body_span_ratio`만 조정하는 방식은 손잡이가
  본체 외곽을 넓히는 경우에 충분하지 않았다.
- `fit_dominant_body_box()`를 양축 scan-line profile 방식으로 수정했다. 본체
  폭의 중앙값을 기준으로 두 축을 모두 검사하고, 중앙값보다 큰 돌출 폭이
  전체 profile의 소수 구간에 반복될 때만 해당 축의 경계를 본체 경계로
  보정한다.
- 따라서 PCB가 90° 회전해 손잡이가 다른 축으로 돌출되어도 본체 중심과
  본체 사각형을 기준으로 표시한다. 방향 자체는 계속 `HORIZONTAL`,
  `VERTICAL`, `ROTATED`로 표시하며 검출을 중단하지 않는다.
- 현재 S22 프레임 오프라인 결과: 왼쪽 본체 중심 약 `(582.6, 484.3)px`,
  본체 박스 장축 길이 약 `235.5px`; 손잡이를 포함한 중심 약 `596px`에서
  본체 쪽으로 보정됐다.
- 90° 회전 손잡이 회귀 테스트를 추가해 Vision 테스트 `23 passed`를 확인하고
  `vision_interfaces`, `vision_server`를 다시 빌드했다. 실행 중인 S22/ROI
  노드는 재시작해야 새 검출 로직이 적용된다.
## 2026-08-20 - S22 Wi-Fi 정지 응답 개선

- S22 Wi-Fi 영상은 USB 경로보다 정지선 반응이 양호함을 확인했다.
- 정지 판정은 `stable_crossing_frames: 1`로 유지한다.
- `/vision/conveyor/{station}/stop_trigger=True` 수신 즉시 `/cmd_vel`에 0을 발행하도록 컨베이어 제어기를 수정했다.
- 기존 50 ms 제어 타이머는 반복 정지 명령과 heartbeat 안전 감시용으로 유지한다.
- `vision_server`를 다시 빌드했고 단위 테스트 22개가 모두 통과했다.
## 2026-08-21 - 수평 S22 재설치 후 ROI·정지선 재보정

- S22를 수평 방향으로 재설치한 현재 1920×1080 프레임을 확인했다.
- 기존 `search_y_start=0.42`가 기판 상단을 잘라 검출을 막고 있었고,
  `min_area_fraction=0.03`도 현재 기판 면적보다 높았다.
- 새 설정: 검색 Y `0.25~0.68`, 최소 면적 비율 `0.018`.
- 현재 프레임 오프라인 검증 결과 기판 2개를 정상 검출했다.
- 조립 정지선: `x=442 px`, normalized `0.23020833`.
- 검사 정지선: `x=1104 px`, normalized `0.57500000`.
- 두 정지선은 현재 화면에서 각각 왼쪽 빈 기판과 오른쪽 조립 기판의
  trailing edge에 맞췄다.
- 새 설정 반영을 위해 `vision_server`를 재빌드했다. 실행 중인 S22/ROI 노드는
  종료 후 다시 시작해야 한다.
- 기판 장축 각도를 계산해 `HORIZONTAL`, `VERTICAL`, `ROTATED`로 오버레이에
  표시하며, 방향이 달라도 검출을 폐기하지 않도록 했다.
- 0°, 30°, 90° 합성 기판 검출 검증을 통과했다.
- 90도 회전 시 지그 손잡이가 박스에 포함될 가능성을 줄이기 위해 본체
  cross-section 기준을 `body_span_ratio=0.85`로 강화했다.

## 2026-08-21 - 조립 기판 손잡이 돌출 기준 추가 조정

- 저장된 실제 조립 기판 프레임의 프로파일을 다시 측정했다. 조립 기판의
  손잡이 돌출 구간은 전체 프로파일의 약 `16.6%`였고, 기존 기준 `0.20`은
  이 구간을 손잡이로 확정하지 못했다.
- `body_extension_fraction` 기본값과 설정값을 `0.15`로 낮췄다. 본체 폭의
  중앙값보다 `8%` 이상 큰 구간이 이 기준 이상 반복될 때만 해당 축을
  본체 경계로 보정한다.
- 현재 저장 프레임 기준 조립 기판 박스 중심은 약 `(1230.4, 494.4)px`,
  장축 각도는 `+11.9°`이며, 손잡이로 추정되는 상단 돌출을 제외한 박스로
  계산된다. 빈 기판 결과도 기존 본체 중심 `(582.6, 484.3)px`를 유지한다.
- 테스트 `23 passed`, ROS 패키지 재빌드 성공. 실제 화면에 반영하려면
  S22/ROI 노드를 재시작해야 한다.

## 2026-08-21 - 조립 기판 회전 박스의 원근 보정

- 손잡이 제거 후에도 회전된 조립 기판에서 enclosing `minAreaRect`가 남아
  본체 모서리와 조금 어긋날 수 있는 문제가 확인됐다.
- 본체 외곽선에서 최소 epsilon으로 convex 4점 polygon을 추출하고, 이 4점을
  오버레이 박스와 중심 계산에 직접 사용하도록 수정했다. 따라서 S22가 비스듬히
  설치된 상태의 사다리꼴 원근도 그대로 표시한다.
- 저장된 실제 프레임 기준 결과: 빈 기판은 중심 약 `(581.8, 484.2)px`,
  조립 기판은 중심 약 `(1229.8, 494.8)px`, 장축 각도 `+11.5°`로 계산되며
  조립 기판의 4점은 `[(1118,383), (1056,547), (1341,608), (1404,441)]`이다.
- 방향 표시 각도도 전체 외곽선이 아니라 본체 4점에서 계산하도록 변경했다.
  테스트 `23 passed`를 다시 확인했다.

## 2026-08-27 - S22 정지선 화면 누락과 프레임 저하 점검

- 당시 구 실행기로 카메라를 실행한 뒤 `/camera2/image_raw/compressed`를 보면 정지선이
  보이지 않는다는 문제를 점검했다. 카메라와 `/conveyor_roi` 노드는 모두 정상
  실행 중이었으며, 정지선은 설계대로 별도 토픽
  `/vision/conveyor/stop_image/compressed`에만 그려지는 것을 확인했다.
- 실행기에 원본 카메라 토픽은 정지선 없는 영상이고, 정지선 확인 토픽은
  `/vision/conveyor/stop_image/compressed`라는 안내를 추가했다.
- ROI 검출은 full-HD 원본에서 유지하되 주석 출력만 1280 px/JPEG 78로 경량화했다.
- Python/YAML 검사, `vision_server` 테스트 23개 통과 및 ROS 패키지 재빌드 완료.
- Wi-Fi 실행기에도 동일한 경량 ROI 출력을 적용하고, 실행 로그에서 정지선 확인
  토픽과 원본 토픽의 차이를 바로 안내하도록 했다. 실제 시험에서
  `/conveyor_roi`가 두 정지선 설정과 함께 정상 시작되는 것을 확인했다.

## 2026-08-31 - S22 컨베이어 실행기 scrcpy 단일화

- 사용하지 않는 스마트폰 앱 기반 USB·Wi-Fi 카메라 실행기를 제거하고 컨베이어
  감시 실행을 `~/KSMC/run_s22_conveyor_hq.sh`로 단일화했다.
- 조립·검사 정지선 ROI 노드, 영상 토픽과 자동 검사 trigger 계약은 변경하지
  않았다. 정리 중 실제 컨베이어 구동 명령은 전송하지 않았다.
- 새 HQ 실행기를 18초간 영상 전용으로 실행해 `/conveyor_roi`가 조립선
  `0.22032`, 검사선 `0.48071`, trigger lead `10 px`, `/cmd_vel` publisher 없음으로
  시작되는 것을 확인했고 종료 후 잔여 프로세스도 없었다.

## 2026-08-27 - 컨베이어 검출 파이프라인 추가 최적화

- S22 원본 토픽은 `1920×1080/JPEG 85`로 보존하고, 정지선 검출과 오버레이만
  내부에서 최대 폭 `1280 px`로 처리하도록 분리했다. 정지선·검색 영역은 모두
  정규화 좌표이므로 영상 축소 후에도 화면상의 상대 위치와 정지 판정은 유지된다.
- 정지선 오버레이는 `1280 px/JPEG 85`로 발행한다. 기존 JPEG 78보다 표시 화질을
  높이면서 Full-HD 재인코딩 부하와 DDS/rqt 전송량은 줄였다.
- 카메라와 ROI 입출력 모두 최신 1프레임 QoS를 사용해 오래된 프레임 누적이
  정지 반응을 늦추지 않게 했다. Vision 회귀 테스트 `23 passed`, Python/YAML 및
  USB/Wi-Fi 실행기 구문 검사, `vision_server` 재빌드를 완료했다.

## 2026-08-31 — 비전검사 정지 후 자동 촬영·검사

- `/vision/conveyor/inspection/stop_trigger`가 참이 되면 모터 정지와 별개로 0.35초
  안정화 후 S22 망원 촬영, 기판 ROI 추출, 전수검사를 실행하도록 연결했다.
- trigger가 계속 참이어도 한 기판당 한 번만 실행한다. 기판이 정지선에서 20 px
  이상 벗어난 상태가 0.5초 유지된 뒤에만 재무장한다.
- 중복 trigger 프로세스를 막는 파일 lock, 종료 시 자식 촬영/검사 프로세스 정리,
  이전 latest 결과 재사용 차단, 상태·결과·report 경로 ROS 토픽을 추가했다.
- 실제 컨베이어 구동에서 검사선 정지와 자동 검사 시작을 확인했다. 이 노드는
  `/cmd_vel`을 발행하지 않으며 컨베이어 이동은 기존 별도 제어기가 담당한다.

## 2026-08-31 — 검사 정지 후 촬영 전용 데이터 수집

- `/vision/conveyor/inspection/stop_trigger`를 재사용해 검사 위치 정지 0.35초 후
  S22 망원 촬영만 수행하는 수집 모드를 추가했다. 기존 OpenCV 불량 판정은 이
  경로에서 실행하지 않는다.
- trigger가 계속 참인 같은 기판은 한 번만 촬영하며, 다음 기판이 upstream에서
  확인된 뒤에만 재무장한다. 촬영 trigger 실행기는 모터 명령을 발행하지 않고
  실제 이동은 `run_conveyor_to_inspection.sh`에서만 수행한다.
- 현재 SMD가 없는 기판은 `known_defect/missing_smd`로 명시하여 정상 데이터와
  분리한다. 모의 촬영 및 gate 테스트 5개가 통과했으며, 이번 변경 중 실제 모터
  명령은 전송하지 않았다.

## 2026-08-31 — 카메라 프레임 저하 시 정지선 통과 방지

- S22 제어 입력을 약 22 FPS에서 29 FPS 이상으로 개선하고, 기판 검출 직후 UI
  렌더링보다 먼저 stop trigger를 발행하도록 변경했다. 화면용 오버레이 FPS와
  물리 정지 판단 FPS는 서로 독립적이다.
- source timestamp 기준 0.20초 이상 지연된 프레임은 사용하지 않는다. 비전
  ready/trigger가 0.25초 동안 갱신되지 않아도 컨베이어 제어기가 즉시 0속도를
  발행한다.
- `/cmd_vel` publisher를 reliable depth 10에서 KEEP_LAST(1)로 바꿔 네트워크 정체
  시 과거 속도 명령이 zero 명령보다 먼저 재생될 가능성을 제거했다. 제어 확인
  주기는 20 Hz에서 50 Hz로 높였다.
- 테스트 30개와 ROS 빌드를 통과했고 S22+정지선만 무동작 실측했다. 실제 0.10 m/s
  재주행은 아직 수행하지 않았다.

## 2026-09-01 — 새 S22 위치의 2개 정지선 확정 및 정지 선행 보상

- S22 overview를 1.5배로 다시 고정한 화면에서 기판 2개 검출을 확인했다.
  960px 제어 폭 기준 수동 배치 trailing edge 초기값은 조립 `175.69px`, 검사
  `574.67px`였고 정지선을 각각 `0.18301061`, `0.59861813`으로 저장했다.
  정지선 간 정규화 간격은 `0.41560752`이며 spacing interlock은 true였다.
- 사용자가 실제 0.10m/s 컨베이어 구동에서 기존 `stop_trigger_lead_px=10`으로
  선을 지난 뒤 정지하는 잔차를 확인했다. 화면의 목표선은 이동하지 않고 제어
  trigger만 20px 먼저 발생하도록 변경했다.
- 프레임 지연 시 계속 이동하는 시간을 줄이기 위해 stale cutoff를 0.15초,
  controller heartbeat timeout을 0.15초로 단축했다. trigger callback의 즉시
  zero publish, 20ms 반복 zero, reliable KEEP_LAST(1) 명령 QoS는 유지했다.
- 설정 적용 후 ROI 노드 로그에서 assembly `0.18301`, inspection `0.59862`,
  lead `20.0px`, stale cutoff `0.150s`, `/cmd_vel` publisher 없음이 확인됐다.
  테스트 `35 passed`와 bash 구문 검사를 통과했다.
- 이번 수정·검증에서는 로봇과 컨베이어 실제 명령을 전송하지 않았다. 사용자가
  보고한 기존 실동작 overrun을 근거로 한 1차 보정이므로 같은 0.10m/s에서 다시
  주행해 정지 잔차를 측정하고 필요하면 lead만 소폭 조정해야 한다.

## 2026-09-01 — 비전 검사 정지 위치 최종 변경

- 사용자가 선택한 새 물리 위치에서 3.5배 검사 원본에 기판 전체가 들어오는 것을
  확인한 뒤, 1.5배 overview의 trailing edge `503.7585px/960px`를 검사선으로
  사용했다. inspection line을 `0.59861813`에서 `0.52474848`로 변경했다.
- assembly line `0.18301061`과 stop trigger lead `20px`는 유지했다. 새 정지선
  간격 `0.34173787`은 minimum separation `0.20`을 만족한다.
- 노드 재시작 로그에서 assembly `0.18301`, inspection `0.52475`, separation
  `0.34174`, lead `20.0px`, `/cmd_vel` publisher 없음이 확인됐다. 테스트는
  `35 passed`였고 이번 적용에서 실제 모터 명령은 보내지 않았다.

## 2026-09-01 — 검사 정지선 최신 수동 위치 반영

- 현재 기판 trailing edge를 `485.0px/960px`로 다시 측정해 inspection line을
  `0.52474848`에서 `0.50520833`으로 옮겼다. assembly line `0.18301061`과
  trigger lead `20px`는 변경하지 않았다.
- 새 separation `0.32219772`는 안전 기준을 통과했고 테스트는 `35 passed`였다.
  사용자 요청에 따라 실행 중 ROI 노드는 재시작하지 않았으며 실제 `/cmd_vel`
  명령도 보내지 않았다.

## 2026-09-03 — Main Server/Unity용 원격 컨베이어 서비스

- 상시 실행형 `conveyor_remote_server`를 추가하고
  `/conveyor/move_to_assembly`, `/conveyor/move_to_inspection`,
  `/conveyor/stop`, `/conveyor/reset` Trigger 서비스를 구현했다.
- `/conveyor/state`에 10 Hz JSON 상태 heartbeat, `/conveyor/moving`에 명령 기준
  이동 여부를 발행한다. 상태는 IDLE, 두 station 이동/정지, MANUAL_STOP,
  FAULT를 구분한다.
- 실제 속도 권한은 이 서버 하나만 갖는다. 다른 `/cmd_vel` publisher가 있으면
  출발을 거부하고 이동 중 발견 시 FAULT 정지한다. 기존 검증값인
  `TwistStamped.linear.x=-0.10 m/s`, S22 heartbeat 0.15초, 최대 이동 30초를
  적용했다.
- `/cell/fr5_clear_for_conveyor=True`가 0.25초 안에 갱신돼야 출발한다. 이동 중
  false 또는 timeout이면 즉시 0속도와 FAULT를 발행한다. 실제 FR5 clear
  publisher는 Main/Robot executor에서 아직 연결해야 한다.
- `assembly-r1`의 `move_conveyor_to_assembly`와
  `move_conveyor_to_inspection` operation을 각각 서비스에 매핑하고, 서비스 수락이
  아닌 ASSEMBLY_STOP/INSPECTION_STOP 상태를 operation 완료 조건으로 정의했다.
- 원격 서버 실행은 `--execute --confirm-motion`을 모두 요구한다. monitor-only
  검증에서 이동 요청 거절, stop 성공, MANUAL_STOP JSON을 확인했다. 별도 ARMED
  검증에서는 네 안전 heartbeat 아래 assembly 이동 수락, 격리 토픽의
  `linear.x=-0.10`, 비전 trigger 이후 `ASSEMBLY_STOP/moving=false` 전이를
  확인했다. 검증용 명령은 `/test/conveyor_cmd_vel`로 격리해 실제 로봇·컨베이어에는
  어떤 이동 명령도 보내지 않았다.
- Vision 패키지 전체 47개 테스트와 ROS 빌드가 통과했다. 상세 팀 연동 계약은
  `docs/CONVEYOR_API_HANDOFF.md`에 기록했다.
