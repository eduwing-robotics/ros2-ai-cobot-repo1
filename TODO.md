# TODO

이 문서는 레포 전체의 활성 작업 계획과 UR/SR 구현 상태를 함께 관리한다. Confluence의
[User Requirements](https://ros2-ai-cobot-project-01-team-01.atlassian.net/wiki/spaces/KSMC/pages/720937/User+Requirements)와
[System Requirements](https://ros2-ai-cobot-project-01-team-01.atlassian.net/wiki/spaces/KSMC/pages/720914/System+Requirements)는
읽기 기준으로만 사용하며 이 작업에서 수정하지 않는다.

상태 기준:

- **구현**: 현재 호출 경로에서 실행되거나 조회된다.
- **부분 구현**: Mock·단일 계층·프로토타입만 있거나 사용자 흐름에 연결되지 않았다.
- **미구현**: 표시 자리만 있거나 실행 경로가 없다.

우선순위 기준:

- **P0**: 현재 Mock 필수 흐름의 완료를 막는 통합 문제와 안전 기능.
- **P1**: 필수 UR/SR의 Real·검사·이력·화면 연결.
- **P2**: 권장 UR/SR과 필수 시연 뒤의 생산·품질 확장.

## UR/SR 구현 상태 요약

| UR / SR | 기능 | 전체 상태 | 주 담당 | 우선순위 | 현재 경계 |
|---|---|---|---|---|---|
| UR-01 / SR-01 | 부품 Pick | 부분 구현 | Unity, AIO | P0 Mock / P1 Real | Mock 실행·피드백은 있고 Real 자동조립은 없다. |
| UR-02 / SR-02 | 부품 Place | 부분 구현 | Unity, AIO | P0 Mock / P1 Real | Mock 슬롯 배치는 있고 Real은 없다. 고정 수량은 레시피가 소유한다. |
| UR-03 / SR-03 | 기판 운반 | 부분 구현 | Unity, AIO | P0 Mock / P1 Real | Unity Mock 컨베이어만 있고 실제 컨베이어 흐름은 없다. |
| UR-04 / SR-04 | 조립·검사 위치 정지 | 부분 구현 | Unity, AIO | P0 Mock / P1 Real | Mock 정지점은 있으나 전체 시연과 실제 센서 완료 판정이 없다. |
| UR-05 / SR-05 | 조립 후 운반 재개 | 부분 구현 | Unity, AIO | P0 Mock / P1 Real | Scenario 호출은 있으나 Mock 전체 종료 검증과 Real 흐름이 없다. |
| SR-06 | 보드·부품 위치/방향 인식 | 부분 구현 | AIO, Unity | P1 | 수신·실험 코드는 있으나 배포 노드와 Scenario 연결이 없다. |
| SR-07 | 보드 위치·회전 보정 | 부분 구현 | AIO, Unity | P1 | Unity 보정 메서드는 있으나 실제 기판 Pose 경로에 연결되지 않았다. |
| UR-07 / SR-08 | 로봇·설비 상태 | 부분 구현 | AIO, Unity, MainServer | P0/P1 | 로봇 상태는 표시하지만 컨베이어·카메라 공통 상태 계약이 없다. |
| UR-09 / SR-09 | 조립 품질 검사 | 부분 구현 | AIO, MainServer, Unity | P1 | Mock 난수 판정·DB 저장만 있고 실제 비전 검사와 UI 연결이 없다. |
| UR-06 / SR-10 | 진행도·기판 번호 | 부분 구현 | AIO, MainServer, Unity | P0 | 슬롯 진행은 보이지만 `job_id`·Unit/기판 식별자가 UI까지 오지 않는다. |
| UR-09 / SR-11 | PASS/FAIL 확인 | 부분 구현 | AIO, MainServer, Unity | P1 | Mock 결과 저장·조회 API는 있고 INSPECT 화면 연결이 없다. |
| UR-08 / SR-12 | 시작·정지·일시정지·재개 | 부분 구현 | AIO, MainServer, Unity | P0 | 시작만 연결됐다. STOP·PAUSE·RESUME 실행 계약이 없다. |
| UR-10 / SR-13 | 작업·검사 이력 | 부분 구현 | MainServer, DB, Unity | P1 | 단건 Job·Unit·불량률 조회만 있고 목록·오류/취소 이력 UI가 없다. |
| UR-13 / SR-14 | 사람 감지 즉시 정지 | 미구현 | AIO, Unity | P0 | 감지 입력부터 로봇·컨베이어 정지까지의 경로가 없다. |
| SR-15 | 비상정지 | 부분 구현 | AIO, Unity | P0 | 로봇 E-STOP 상태 표시는 있으나 로봇·컨베이어 동시 정지 검증이 없다. |
| UR-11 / SR-16 | 남은 부품 수량 | 구현, 범위 결정 필요 | AIO, MainServer, Unity | P2 또는 제외 | backend 재고 검증·차감과 상세 수량 UI가 있다. |
| UR-12 / SR-17 | 경로 시각화 | 부분 구현·미연결 | AIO, Unity | P2 | AIO 발행과 Unity 재생 코드는 있으나 실제 소비 호출자가 없다. |

## P0. 공통 통합과 요구사항 결정

- [ ] UR-08의 `일시정지·재개`와 SR-12의 `시작·정지`를 합친 최소 제어 계약을 사용자가 확정한다.
- [ ] UR-13은 권장, SR-14는 필수인 우선순위 차이를 로컬 계획에서는 안전 P0로 처리한다.
- [ ] UR-11/SR-16 상세 재고 수량을 MVP에서 제외할지 확정한다. backend 재고 검증과 차감은 유지한다.
- [ ] SR-02의 부품별 고정 수량은 기능 코드가 아니라 제품 슬롯·레시피 검증 데이터가 소유한다고 로컬 기술 문서에 명시한다.
- [ ] `mock_db_bridge`의 `job_id`를 상태 snapshot과 MainServer 응답을 거쳐 Unity까지 전달한다.
- [ ] SR-10의 기판 번호를 기존 `unit_id`로 사용할지 별도 식별자로 둘지 사용자가 확정한다.
- [ ] Unity → AIO → `mock_db_bridge` → PostgreSQL → MainServer → Unity 흐름을 PASS/FAIL 각각 반복 검증한다.
- [ ] DB commit 성공 뒤에만 외부 `COMPLETED`, DB 오류 시 `FAILED`가 전달되는지 검증한다.
- [ ] 사람 감지와 물리 E-STOP이 로봇 명령 차단과 컨베이어 정지까지 이어지는 공통 안전 계약을 확정한다.

완료 기준: Mock 한 회의 Job·Unit·재고·검사 결과와 Unity 표시가 같은 식별자를 사용하고, 중지와 안전 입력의 책임 경계가 정해진다.

## Unity 범위

### 현재 구현

| 관련 요구사항 | 상태 | 현재 구현 |
|---|---|---|
| UR-01~05 / SR-01~05 | 부분 구현 | Mock Pick·Place 시각화, Scenario와 Mock 컨베이어 호출이 있다. |
| UR-06 / SR-10 | 부분 구현 | `placed_count / expected_step_count` 기반 슬롯 진행을 표시한다. |
| UR-07 / SR-08 | 부분 구현 | 로봇 연결·운전·E-STOP·오류와 영상 링크를 표시한다. |
| UR-08 / SR-12 | 부분 구현 | START만 Scenario에 연결되고 PAUSE·ABORT·STOP은 버튼만 있다. |
| SR-06~07 | 부분 구현 | 비전 Pose 수신과 보정 클래스는 있으나 호출 흐름이 없다. |
| UR-09~10 / SR-09·11·13 | 미구현 | INSPECT·QUALITY는 영상 또는 빈 상태만 표시한다. |
| UR-11 / SR-16 | 구현, 재검토 | 비활성 REQUEST 화면이 MainServer의 상세 재고 수량을 표시한다. |
| UR-12 / SR-17 | 부분 구현·미연결 | 수동 관절 Ghost는 사용하고 경로 재생기는 호출되지 않는다. |
| UR-13 / SR-14~15 | 미구현 | E-STOP 수신 표시는 있으나 작업·컨베이어 정지 연동은 없다. |

### P0 — Mock UI와 안전

- [ ] REQUEST 화면을 `고정 제품·레시피 + 인터록 + START`로 축소하고 실행에 전달되지 않는 제품·생산 수량 선택을 제거한다.
- [ ] 상세 재고 UI를 제외하면 `조립 가능` 또는 `부품 부족` 판정만 남긴다.
- [ ] Mock 컨베이어의 속도·거리·타임아웃 불일치를 수정하고 조립·검사 정지점 도달과 Scenario 전체 종료를 검증한다.
- [ ] RUN에 AIO에서 전달된 `job_id`와 Unit/기판 식별자를 표시한다.
- [ ] 로봇뿐 아니라 컨베이어와 비전의 연결·운전 상태를 공통 상태로 표시한다.
- [ ] 확정된 PAUSE·RESUME·STOP 계약만 UI에 연결하고 미지원 버튼은 비활성 사유를 표시하거나 제거한다.
- [ ] 사람 감지·E-STOP 시 새 로봇 명령을 차단하고 `MockConveyor.StopConveyor()`를 호출하는 안전 경계를 검증한다.

### P1 — 필수 Real·검사·이력

- [ ] `RealAssemblyScenarioControl.ExecuteAsync()`를 실제 ROS2 조립 노드에 연결하고 Mock과 같은 완료·실패·타임아웃 의미를 제공한다.
- [ ] Vision Pose → Calibration → Real 조립 목표 경로를 연결한다.
- [ ] 기존 MainServer Job·Unit API를 RUN과 INSPECT에 연결한다.
- [ ] INSPECT에 PASS/FAIL, 불량 슬롯, 검사 이미지를 실제 값으로 표시한다.
- [ ] QUALITY에 우선 기존 슬롯별 불량률 API를 연결한다.
- [ ] 작업 목록·오류/취소 API가 생기면 기본 이력 화면을 연결한다.

### P2 — 권장 기능

- [ ] UR-11/SR-16을 유지할 때만 상세 재고 수량 UI를 되돌린다.
- [ ] 실제 `JointTrajectory` 소비 계약이 생길 때만 Ghost 경로 재생을 연결한다.
- [ ] 표시할 연결·진단 데이터가 확정된 뒤에만 SETUP 화면을 추가한다.

## MainServer·DB 범위

### 현재 구현

| 관련 요구사항 | 상태 | 현재 구현 |
|---|---|---|
| UR-01~02 / SR-01~02 | 부분 구현 | 제품·슬롯 조회와 조립 요청 전달은 있으나 실행 완료를 직접 판정하지 않는다. |
| UR-06 / SR-10 | 부분 구현 | 단건 Job 진행률과 Unit 조회는 있으나 `job_id` 발견 경로와 보드 번호 계약이 없다. |
| UR-09 / SR-09·11 | 부분 구현 | Mock PASS/FAIL·불량 슬롯 저장 및 조회가 있다. |
| UR-10 / SR-13 | 부분 구현 | 단건 Job·Unit과 슬롯 불량률만 있고 작업 목록·기간·오류/취소 이력이 없다. |
| UR-11 / SR-16 | 구현, 재검토 | 제품 생산 가능 수량, 필요·보유·부족 수량 API가 있다. |
| SR-12 | 부분 구현 | `POST /assemblies`와 현재 snapshot 조회만 있고 중지·일시정지·재개가 없다. |
| DB 권한 | 부분 구현 | writer·reader 역할 SQL은 있으나 실제 계정 적용과 허용·거부 검증이 없다. |
| `part_catalog`·`defect_report` | 스키마만 구현 | 적재·스캔·알림·대책서 실행 코드는 없다. |

### P0 — Mock 데이터 연결

- [ ] AIO snapshot의 `job_id`를 `POST /assemblies`와 `GET /assemblies/current` 응답에서 보존한다.
- [ ] 제품·생산 수량·상세 재고 API의 MVP 공개 범위를 Unity 결정과 맞춘다.
- [ ] AIO 제어 계약이 준비되면 STOP·PAUSE·RESUME 요청을 같은 P0 경로로 얇게 전달한다.
- [ ] 격리 `_test` DB를 마련하고 `production_writer`와 `datastation_reader`를 실제 계정에 적용해 허용·거부를 검증한다.
- [ ] PASS/FAIL 각각에서 Job·Unit·재고·검사 트랜잭션 일관성을 반복 검증한다.
- [ ] 수량 1 계약 동안 `jobs.requested_quantity`는 내부값 `1`로 유지하고 외부 선택 기능으로 노출하지 않는다.

### P1 — 필수 조회와 제어

- [ ] 작업 목록·기간 조회와 최소 종료 오류 코드·메시지 API를 추가한다.
- [ ] SR-10의 보드 식별자 결정에 맞춰 Unit 조회 응답을 확정한다.
- [ ] AIO 공통 상태 계약이 준비된 뒤 로봇·컨베이어·카메라 상태 조회를 제공한다.
- [ ] 기존 Unit·불량 슬롯·슬롯별 불량률 API가 Unity 요구 필드를 모두 제공하는지 통합 검증한다.

### P2 — 생산·품질 확장

- [ ] 데이터시트 적재 경로와 `part_catalog` 갱신 책임을 확정하고 구현한다.
- [ ] 품질 임계 스캔과 중복 방지된 `defect_report` 알림 생성을 구현한다.
- [ ] 고정 evidence로 불량대책서를 생성하고 레시피 변경 전후 효과를 검증한다.
- [ ] `part_catalog`와 `defect_report`의 쓰기·읽기 역할을 실제 필요가 확정될 때 추가한다.

## AIO·ROS2 범위

### 현재 구현

| 관련 요구사항 | 상태 | 현재 구현 |
|---|---|---|
| UR-01~02 / SR-01~02 | 부분 구현 | Mock 레시피 Pick·Place·그리퍼·단계 피드백은 있고 Real은 독립 프로토타입뿐이다. |
| UR-03~05 / SR-03~05 | 미구현 | 실제 컨베이어 명령은 조립 흐름에 연결되지 않았다. |
| SR-06~07 | 부분 구현 | 비전 실험 스크립트는 있지만 기판·방향 인식과 배포 노드가 없다. |
| UR-06~07 / SR-08·10 | 부분 구현 | Mock 단계 피드백과 Real 로봇 상태 토픽은 있으나 공통 설비 상태·기판 번호가 없다. |
| UR-08 / SR-12 | 미구현 | 외부 조립 계약은 `start/status`뿐이다. |
| UR-09 / SR-09·11 | 부분 구현 | Mock 난수 판정과 DB 기록만 있고 실제 검사 노드가 없다. |
| UR-10 / SR-13 | 부분 구현 | Job·Unit·재고·검사를 기록하지만 취소·오류 이벤트는 남기지 않는다. |
| UR-11 / SR-16 | backend 구현 | 재고 부족 검증과 차감은 구현돼 있다. |
| UR-12 / SR-17 | 발행 구현 | 계획 경로 토픽은 발행하지만 Unity 소비 흐름은 없다. |
| UR-13 / SR-14~15 | 미구현 | E-STOP 상태 기반은 있으나 사람 감지와 로봇·컨베이어 동시 정지 경로가 없다. |

### P0 — Mock 완결과 안전 게이트

- [ ] Unity 요청 → DB bridge → Mock → PostgreSQL의 PASS/FAIL 경로를 반복 실행한다.
- [ ] DB 기록 완료 뒤에만 외부 terminal feedback을 보내고 실패 시 Job·Unit을 일관되게 마감하는지 검증한다.
- [ ] STOP·PAUSE·RESUME을 로봇과 컨베이어에 함께 적용하는 최소 조립 제어 계약을 구현한다.
- [ ] 사람 감지 입력과 물리 E-STOP이 로봇 정지·새 명령 거부·컨베이어 정지로 이어지는지 검증한다.
- [ ] 실제 조립 TCP Pose를 슬롯 Target으로 교시하고 Mock j3 하한 `0 deg`에서 필수 목표를 plan-only로 검증한다.
- [ ] Unity TCP, ROS `wrist3_link`, 실제 FAIRINO Tool 좌표와 배치 회전 기준을 일치시킨다.
- [ ] 슬롯 Target·Slot ID 누락을 실행 전에 거부한다.

근거와 측정값은 [좌표 도달 실패 조사 보고서](else/Report.md)에 유지한다.

### P1 — Real·비전·검사

- [ ] Real 자동조립 노드가 Mock과 같은 시작·완료·실패·타임아웃 계약을 제공한다.
- [ ] 부품·기판 위치와 방향을 출력하는 배포 가능한 비전 노드를 구현한다.
- [ ] 기판 보정 Pose를 레시피 슬롯 목표에 적용한다.
- [ ] 실제 컨베이어의 조립 위치 이동·정지·검사 위치 재이동을 완료 신호까지 처리한다.
- [ ] 로봇·카메라·컨베이어를 `IDLE/WORKING/STOPPED/EMERGENCY/ERROR` 공통 상태로 제공한다.
- [ ] 누락·위치·방향·균열 검사와 PASS/FAIL, 불량 슬롯, evidence 저장을 구현한다.
- [ ] 작업 실패 원인과 취소 이벤트를 DB 기록 경계에 전달한다.
- [ ] 상태 수신 → 저속 단일 관절 → Home → 다관절 → TCP 이동 순서로 실기 안전 검증을 진행한다.
- [ ] 물리 비상정지, 작업 영역과 속도 제한을 확인하기 전 Real 자동 실행을 활성화하지 않는다.

### P2 — 권장 기능

- [ ] UR-12/SR-17을 유지할 때만 기존 계획 경로 토픽의 Unity 소비 계약을 확정한다.
- [ ] UR-11/SR-16을 유지할 때만 상세 재고 숫자를 외부 UI 계약으로 제공한다.

## 요구가 생길 때만 확장

- [ ] 취소나 장시간 실행에서 현재 서비스+토픽 계약이 부족할 때만 ROS2 Action으로 교체한다.
- [ ] 수량 2개 이상이 필요할 때 Unit 반복, 재고 예약과 실패 Unit 정책을 추가한다.
- [ ] 셀이 2개 이상일 때 작업 큐, claim과 셀 배정을 추가한다.
- [ ] 프로세스 재시작 뒤 같은 요청의 중복 방지가 필요할 때 영속 `request_id`와 복구 정책을 추가한다.
- [ ] 외부망 또는 다중 사용자가 생길 때 인증·권한·감사 기록을 추가한다.
- [ ] 실제 조회 지연이 확인될 때만 캐시나 별도 메시지 계층을 검토한다.
