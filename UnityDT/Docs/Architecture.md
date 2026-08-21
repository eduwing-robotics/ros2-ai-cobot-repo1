# 시스템 구조 — Unity · ROS2 조립 노드 · 로봇

## 이 문서의 범위

조립 작업 한 건이 사용자 요청에서 실적 기록까지 도달하는 동안 **누가 무엇을 소유하고 무엇을
주고받는지**를 정한다.

| 문서 | 내용 |
|---|---|
| [DB.md](./DB.md) | `production` 스키마 명세 |
| [DB3.md](./DB3.md) | 3스키마 통합 설계 |
| [Recipe.md](./Recipe.md) | 레시피 파일 규격 — 로봇이 소유하는 것 |
| [API.md](./API.md) | Unity ↔ ROS2 구체 인터페이스 목록 |
| [fr5-ui-requirements.md](./fr5-ui-requirements.md) | Unity 화면 요구사항 |
| [UI.md](./UI.md) | 화면 기능 정의와 페이지 분할 |

ISA-95(IEC 62264)의 계층 개념을 **참조해** 책임을 나눴다. B2MML 같은 표준 메시지 형식은
사용하지 않는다. 표준을 준수하는 것이 아니라 경계를 정하는 어휘로 빌려 쓴다.

## 세 계층

```
┌───────────────────────────────────────────────────────────────┐
│  Unity — 조작과 표현                                            │
│  작업 요청 · 진행 표시 · 3D 트윈 · 수동 조그                      │
│  상태를 소유하지 않는다. 꺼져도 작업은 계속된다                    │
└───────────────────────────────────────────────────────────────┘
      ↕  ROS2 Action / Topic / Service
┌───────────────────────────────────────────────────────────────┐
│  ROS2 조립 노드 — 작업 실행 (ISA-95 Level 3 + Level 2 통합)      │
│  레시피 로드 · 제어 큐 생성 · 스텝 실행 · 검사 판정                │
│  production 스키마 읽기·쓰기 · 재고 차감                          │
│  상태의 유일한 소유자                                             │
└───────────────────────────────────────────────────────────────┘
      ↕  movej · 그리퍼 · 힘 제어
┌───────────────────────────────────────────────────────────────┐
│  로봇 컨트롤러 (ISA-95 Level 1)                                  │
│  궤적 보간 · 힘 제어 · 관절 상태 발행                              │
└───────────────────────────────────────────────────────────────┘

  별도 프로세스 ─ 대책서 발행 백엔드
  production 읽기 전용 · part_catalog 읽기 전용 · defect_report 읽기·쓰기
  ROS2 를 쓰지 않는다
```

### Level 2와 Level 3를 합친 이유

로봇 한 대짜리 셀에서 작업 관리와 시퀀스 실행을 분리하면 얻는 것보다 잃는 것이 크다.

- **이벤트 유실 문제가 사라진다.** 분리하면 "1대 조립 완료"를 놓쳤을 때 재고가 차감되지
  않는다. 통합하면 내부 함수 호출이라 유실이 없다.
- **트랜잭션이 단순해진다.** 조립 완료와 재고 차감을 한 트랜잭션으로 묶는 것이 자연스럽다.
- **지켜야 할 분리는 그대로다.** 요구사항은 "Unity가 상태를 소유하지 않는다"였지 "노드가
  둘이어야 한다"가 아니었다.

대책서 발행 백엔드는 여전히 별도 프로세스다. `production`을 읽기 전용으로만 보므로 문서
발행이 작업 실적을 바꿀 수 없다.

### 소유 데이터

| 계층 | 소유 | 소유하지 않는 것 |
|---|---|---|
| Unity | 화면 상태, 카메라 시점 | 작업 상태, DB 커넥션 |
| ROS2 조립 노드 | `production` 스키마, 레시피 파일, 스텝 진행 상태 | 모션 파라미터의 물리적 실행 |
| 로봇 컨트롤러 | 궤적, 관절 상태 | 위 전부 |
| 대책서 백엔드 | `defect_report` 스키마 | `production` 쓰기 권한 |

## 통신 채널의 역할 구분

거의 모든 통신이 ROS2를 지나지만 **한 채널로 통합한 것이 아니다.** 성격이 다른 두 종류를
구분해 다른 방식으로 다룬다.

| 성격 | 예 | 요구 | 담당 |
|---|---|---|---|
| 제어·상태 스트림 | 관절, TCP Pose, 스텝 진행 | 저지연, 손실 허용, 영속 불필요 | **ROS2** |
| 업무 트랜잭션 | 작업 요청, 완성품 완료, 재고 차감, 검사 결과 | 손실 불가, 영속, 트랜잭션 | **DB** |

정확한 표현은 **"전송은 ROS2, 진실은 DB"** 다. ROS2 메시지는 아무것도 소유하지 않는다.
Action feedback을 놓쳐도 `units` 행은 이미 커밋되어 있고, Unity가 어긋나도 Service 한 번으로
복구된다.

## ROS2 인터페이스

구체 토픽·서비스 목록은 [API.md](./API.md)에 있다. 여기서는 조립 작업에 쓰는 것만 정의한다.

| 용도 | 방식 | 이유 |
|---|---|---|
| 작업 요청 · 진행 · 완료 | **Action** | 수 분짜리 작업. goal/feedback/result 구조가 그대로 대응하고 취소가 따라온다 |
| 관절 · TCP 스트림 | Topic | 고빈도. 기존 섀도잉 경로를 그대로 쓴다 |
| 진행 상황 조회 | Service | Unity 재시작 시 복구 |
| 수동 조그 | Topic / Service | 작업 흐름 밖 |

Service는 blocking이라 긴 작업에 맞지 않고, Topic은 응답 보장이 없다. 그래서 작업 요청은
Action이다.

### AssemblyJob.action

```
# Goal
int64  job_id
int64  product_id
string product_code
string product_version
string recipe_version
int32  requested_quantity
---
# Result
string job_status              # COMPLETED / FAILED / CANCELLED
int32  completed_quantity
---
# Feedback
int32  unit_sequence_in_job
string unit_phase              # STARTED / ASSEMBLED / INSPECTED / FAILED
int32  step_order
string slot_code
```

노드는 goal 수신 즉시 레시피를 로드하고 [Recipe.md](./Recipe.md)의 로드 시 검증을 수행한다.
`recipe_version`이 일치하지 않으면 **작업을 시작하지 않고 goal을 거부한다.** 어떤 레시피로
만들었는지 확정할 수 없는 완성품은 만들지 않는다.

### feedback 시점과 DB 기록

`unit_phase`가 바뀔 때 노드는 DB에 쓰고 동시에 feedback을 발행한다.

| `unit_phase` | DB 처리 |
|---|---|
| `STARTED` | `units` INSERT (`RUNNING`) |
| `ASSEMBLED` | `assembly_completed_at` 갱신 + **부품 재고 차감** (한 트랜잭션) |
| `INSPECTED` | `inspection_result` 갱신 + `unit_defects` INSERT (한 트랜잭션) |
| `FAILED` | `unit_status = 'FAILED'`, `inspection_result` 는 `PENDING` 유지 |

`step_order`와 `slot_code`만 담긴 feedback(스텝 진행)은 **DB에 쓰지 않는다.** Unity 표시용
이다.

검사 결과를 기록할 때 노드는 `slot_code`와 `defect_type`만 가지고 있다.
`unit_id → jobs.product_id → product_slots(product_id, slot_code)` 경로로 `product_slot_id`를
확정하며, 이 검증과 INSERT는 하나의 공개 함수 안에서 완결된다. `DB.md`의 슬롯·부품 정합성
계약 그대로다.

## 실행 순서

```text
Unity ──Action goal (product_id, recipe_version, qty)──▶ ROS2 조립 노드
                                                         레시피 로드 + 검증
                                                         재고 사전 검증 (전체 수량분)
                                                         jobs INSERT → RUNNING
                                                         제어 큐 생성

      ◀─feedback STARTED(seq=1)──   units INSERT
      ◀─feedback step_order 1..6─   Unity 표시만. DB 기록 없음
                                     movej · 그리퍼 → 로봇 컨트롤러
      ◀─feedback ASSEMBLED(seq=1)─  재고 차감 (트랜잭션)
                                     카메라 촬영 · 판정
      ◀─feedback INSPECTED(seq=1)─  판정 + 불량 슬롯 기록 (트랜잭션)
                                     ... seq 2, 3 반복
      ◀─result (COMPLETED, 3)─────  jobs → COMPLETED
```

## Unity

### 하는 일과 대화 상대

| 기능 | 상대 | 비고 |
|---|---|---|
| 완성체 선택 + 수량 요청 | 조립 노드 (Action) | Job을 **요청**할 뿐 실행하지 않는다 |
| 진행률 · 검사 결과 표시 | 조립 노드 (feedback) | 구독 |
| 관절 · TCP 3D 렌더링 | **로봇 직접** (Topic) | 수십 Hz. DB를 거치지 않는다 |
| 재시작 시 상태 복구 | 조립 노드 (Service) | 노드가 DB 조회해 응답 |
| 수동 조그 | 조립 노드 (Topic/Service) | 작업 흐름 밖 |

### Unity는 DB에 직접 접속하지 않는다

커넥션 관리·트랜잭션·재시도가 렌더링 루프에 얽히면 안 된다. 더 중요하게는, Unity가 DB를
쓰기 시작하면 **상태 소유자가 둘이 되어** 아래 복구 시나리오가 성립하지 않는다.

재시작 복구는 Service 하나로 해결된다. Unity는 여전히 DB를 모른다.

### 수동 조작 모드

수동 조그는 작업 흐름 밖이므로 별도 경로를 허용한다. 대신 **`jobs`를 만들지 않고 DB에
아무것도 기록하지 않는다.** 수동으로 움직여 만든 것은 완성품이 아니므로 실적이 아니다.
이 경로로 부품을 소모했다면 재고는 실사 조정으로 맞춘다.

## 저장하지 않는 것

| 데이터 | 저장 안 함 | 대신 |
|---|---|---|
| 스텝 진행 이벤트 | DB | Unity 실시간 표시 후 소멸. 필요하면 파일 로그 |
| 관절 · TCP Pose 스트림 | DB | Unity 렌더링용으로만 소비 |
| 레시피 본문 (순서·Pose·힘) | DB | 레시피 파일 + Git ([Recipe.md](./Recipe.md)) |
| 수동 조작 이력 | DB | 작업 실적이 아님 |

### 스텝 이벤트를 저장하지 않는 이유

**첫째, 이 DB가 답하기로 한 질문에 필요하지 않다.** `DB.md`의 기능 범위 7개 질문 — 선택
가능한 완성체, 재고 충분 여부, 요청·완료 수량, 검사 판정, 불량 슬롯과 유형, 누적 불량률,
개선 전후 비교 — 은 전부 완성품 1대 단위로 답이 나온다.

**둘째, 불변성 계약이 오염된다.** `production`은 확정된 기록만 담고 수정하지 않는다. 스텝
이벤트는 `started → done`으로 상태가 변하므로, 변하는 행과 확정 기록이 섞이면 "이 스키마의
데이터는 전부 확정 사실"이라는 규칙이 사라진다.

**셋째, 쓰기 부하가 실행 경로에 얹힌다.** 조립 중 매 스텝 INSERT가 발생하면 DB 지연이나
커넥션 장애가 조립에 영향을 준다. 1대 단위 보고는 분당 몇 회에 불과해 이 결합이 없다.

디버깅이 목적이라면 보존 기간과 전문 검색이 필요하므로 관계형 DB가 아니라 로그가 맞는
도구다. 스텝별 소요시간 분석이나 병목 탐색이 실제 요구가 되면 그때 별도 이벤트 테이블을
추가한다 (`DB.md` 후속 조건).

### 다만 한 가지 공백

조립이 실패했을 때 **어느 슬롯에서 멈췄는지**가 남지 않는다. 현재는 `unit_status = 'FAILED'`
뿐이다. 이 요구가 생기면 스텝 전체를 저장할 것이 아니라 `units`에 실패 슬롯 칼럼 하나를
더하는 편이 훨씬 싸다. feedback에 이미 `slot_code`가 있으므로 준비는 되어 있다.

## 장애와 복구

### Unity 종료

작업에 영향이 없다. 상태를 소유하지 않기 때문이다. 재실행하면 Service로 현재 상태를 조회해
화면을 복원한다.

```sql
SELECT j.job_id, j.requested_quantity,
       COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'COMPLETED') AS completed_quantity,
       ROUND(100.0 * COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'COMPLETED')
             / j.requested_quantity, 2) AS progress_percent
FROM production.jobs j
LEFT JOIN production.units u ON u.job_id = j.job_id
WHERE j.job_status = 'RUNNING'
GROUP BY j.job_id, j.requested_quantity;
```

### 조립 노드 재시작

미완결 작업을 탐지한다. 스키마 변경 없이 기존 상태값으로 처리된다.

```sql
SELECT j.job_id, j.requested_quantity, j.recipe_version,
       COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'COMPLETED') AS done,
       COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'RUNNING')   AS in_flight
FROM production.jobs j
LEFT JOIN production.units u ON u.job_id = j.job_id
WHERE j.job_status = 'RUNNING'
GROUP BY j.job_id, j.requested_quantity, j.recipe_version;
```

`in_flight > 0`이면 그 완성품은 중단된 것이다. 로봇의 현재 위치를 확인해 재개하거나, 해당
행을 `FAILED`로 정리하고 다음 대수부터 진행한다.

### ROS-TCP-Endpoint 두절

Unity가 눈이 멀 뿐 **조립은 계속된다.** 노드가 DB에 직접 쓰기 때문이다. 재연결 시 Service로
현재 상태를 다시 받아 화면을 맞춘다.

### 조립 실패

`unit_status = 'FAILED'`, `inspection_result = 'PENDING'`으로 남긴다. 검사를 못 했으므로
판정이 없는 것이 맞고, `DB.md`의 `ck_units_inspected` 제약과도 일치한다.

### 재고 부족

Job 시작 **전에** `requested_quantity` 전체분을 검증한다. MVP는 로봇 한 대와 활성 작업 한
건만 허용하므로 작업 도중 재고가 빠질 경로가 없다. 대당 차감 직전에도 재확인하고 부족하면
그 트랜잭션 전체를 실패시킨다.

## 구현 시 주의

**ROS2 콜백 안에서 blocking DB I/O를 하지 않는다.** 기본 `SingleThreadedExecutor`에서 DB
호출이 executor를 막으면 그동안 관절 스트림 발행과 다른 콜백이 멈춰 Unity 섀도잉이 끊겨
보인다. `MultiThreadedExecutor` + `ReentrantCallbackGroup`을 쓰거나 DB 쓰기를 별도 워커
스레드 큐로 넘긴다. 조립 실행 자체는 초 단위라 여유가 있다.

## 보안 전제

**격리된 제어망을 전제한다.** ROS2 기본 설정에는 인증도 암호화도 없으므로, 같은 네트워크에
있으면 누구나 Action goal을 발행할 수 있다.

외부 노출이 필요해지면 다음을 적용한다.

- SROS2(DDS-Security)로 노드 인증과 토픽 암호화
- 아래 HTTP 어댑터에 별도 인증
- 제어망과 업무망 분리

현재 범위에서는 적용하지 않으며, 이는 **모르는 것이 아니라 범위 밖으로 둔 것**이다.

## 확장점 — HTTP 어댑터

지금 구조에서는 ROS2 클라이언트가 되어야만 시스템에 접근할 수 있다. 웹 대시보드나 모바일에서
작업을 걸거나 진행률을 보려면 경로가 없다.

같은 노드 프로세스에 얇은 HTTP 레이어를 얹으면 해결된다. Action은 그대로 두고 어댑터만
추가한다.

```python
@app.post("/jobs")                # 작업 요청 → 내부적으로 Action goal 발행
@app.get("/jobs/{job_id}")        # 진행률 → DB 조회
@app.get("/parts/defect-rate")    # 불량률 → DB 조회
```

현재는 구현하지 않는다. 필요해질 때 붙일 자리로 남겨둔다.

## 시연 시나리오

계층 분리가 그림이 아니라 실제임을 보이는 절차다.

```text
1. Unity 에서 완성체 3대 요청 → 조립 시작
2. 1대 완료 시점에 Unity 강제 종료
3. 로봇은 계속 조립 (2대째 진행)
4. Unity 재실행
5. 진행률 "3대 중 2대 완료" 가 복원되어 표시됨
```

`DB.md`가 `requested_quantity`를 저장하는 이유로 적어둔 "재시작 후에도 진행률을 복구한다"가
그대로 실현된다.

## 표준 참조

| 표준 | 사용 범위 |
|---|---|
| ISA-95 (IEC 62264) | 계층 경계와 지시·보고 방향성의 **참조 어휘**. 메시지 형식은 자체 정의 |
| ISA-88 | 레시피가 제어 도메인에 속한다는 구분의 근거 |
| ISO 10218 · ISO/TS 15066 | 로봇 안전. 이 문서 범위 밖이나 실제 구축 시 필수 |

"ISA-95를 준수한다"고 말하지 않는다. B2MML 등 표준 메시지 형식을 쓰지 않기 때문이다.
정확한 표현은 **"계층 경계를 ISA-95 참조 모델에 맞춰 정리했다"** 이다.

표준 이름과 무관하게 이 구조가 실제로 지키는 원리는 셋이다.

1. 실적을 기록하는 층과 UI를 분리한다 — 재시작 후 복구가 가능해진다
2. "무엇을"과 "어떻게"를 다른 층이 소유한다 — 레시피 튜닝이 제품 버전을 오염시키지 않는다
3. 지시는 내려가고 보고는 올라온다 — 결합이 단방향으로 유지된다

## 열려 있는 결정

1. **조립 실패 슬롯 기록** — `units`에 실패 슬롯 칼럼을 둘지. 실패 원인 분석 요구가 생기면
   추가한다.
2. **수동 조작 중 부품 소모** — 실사 조정으로 맞출지, 별도 경로를 둘지.
3. **HTTP 어댑터 도입 시점** — 현재는 자리만 남겨둔 상태다.
