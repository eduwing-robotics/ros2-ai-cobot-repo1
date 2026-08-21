# MAIN_SERVER — 아키텍처와 경계

기능은 [README.md](./README.md), 소유 정보 규격은 [Information.md](./Information.md), 설계
근거와 결정 이력은 [Design.md](./Design.md)에 있다. 이 문서는 **구조**와 **해도 되는 것 / 하면 안 되는 것**을 정한다.

---

## 1. 전체 구조

```text
┌──────────────────────────────────────────────────────────────────┐
│                             Unity                                │
│                     조작 · 표시 · 3D 트윈                          │
└──────────────────────────────────────────────────────────────────┘
       │ HTTP                                    ▲ ROS2 Topic
       │ POST /jobs · GET 조회                    │ 관절·TCP·카메라
       ▼                                         │ feedback(slot_code)
┌────────────────────────┐                       │
│      MainServer        │                       │
│      HTTP 서버 (유일)    │                      │
│  접수 · 조회 · 품질 · 문서 │                      │
└────────────────────────┘                       │
       │  ▲                                      │
       │  └── SELECT ─────────┐                  │
       │                      │ datastation_     │
       │ HTTP (셀이 폴링)       │ reader           │
       │ GET /cell/next-job   │                  │
       ▼                      ▼                  │
┌────────────────────────┐  ┌──────────────────┐ │
│    assembly_bridge     │─▶│   PostgreSQL     │ │
│      셀 수명주기         │  │  production      │ │
│  jobs·units·재고·검사    │  │  part_catalog    │ │
└────────────────────────┘  │  defect_report   │ │
       │  production_writer └──────────────────┘ │
       │ ROS2 Action (AssemblyJob)               │
       ▼                                         │
┌────────────────────────┐                       │
│       조립 노드          │───────────────────────┘
│   레시피 · 좌표 · 실행    │
│    ├─ Mock             │   recipes/*.yaml
│    └─ Real (FR5+비전)   │   frames.yaml · tools.yaml
└────────────────────────┘
       │ movej · 그리퍼
       ▼
   로봇 컨트롤러
```

화살표가 두 종류다. **HTTP는 지시만 나르고, DB는 기록을 소유한다.**
셀에서 MainServer로 돌아가는 HTTP는 없다.

---

## 2. 프로세스별 소유

| 프로세스 | HTTP | DB 계정 | 소유 |
|---|---|---|---|
| Unity | 클라이언트 | **없음** | 화면 상태, 카메라 시점 |
| **MainServer** | **서버 (유일)** | `datastation_reader` · `defect_report` | 대기 요청, 품질 판정, 대책서 |
| assembly_bridge | 클라이언트 (폴링) | `production_writer` | 작업 수명주기, 실행 기록 |
| 조립 노드 | 없음 | 없음 | 레시피, 좌표, 스텝 실행, 검사 판정 |

### 데이터 변경 소유자

| 데이터 변경 | 소유자 | 계정 |
|---|---|---|
| 스키마 · 마이그레이션 | MainServer | 배포 전용 |
| 제품 · 재고 · 작업 · 품질 **조회** | MainServer | `datastation_reader` |
| `jobs` · `units` 생성 | assembly_bridge | `production_writer` |
| 유닛 완료 · 재고 차감 · 검사 기록 | assembly_bridge | `production_writer` |
| 품질 임계 판정 · 대책서 | MainServer | `defect_report` |
| 레시피 · 좌표 · 모션 | 조립 노드 | **DB 아님 — 파일 + Git** |

---

## 3. 쓰기 소유권 — 이 구조의 이유

> **물리 작업과 그 기록 사이에 네트워크를 두지 않는다.**

로봇 조립은 되돌릴 수 없다. 부품이 꽂혔으면 롤백이 없다. 완료 보고를 HTTP로 셀에서 서버로
올리면, 셀 입장에서 구분 불가능한 세 상태가 **하나의 타임아웃**으로 보인다.

| 실제로 일어난 일 | 셀이 보는 것 | 위험 |
|---|---|---|
| 요청이 안 닿음 | 타임아웃 | 재시도 안 하면 기록 유실 |
| 서버는 커밋했는데 응답만 유실 | **똑같은 타임아웃** | 재시도하면 재고 이중 차감 |
| 셀 프로세스가 그 사이 죽음 | 아무것도 못 봄 | 완료 사실 영구 소멸 |

해결하려면 영속 outbox와 멱등 처리가 필요하다. **그래서 처음부터 그 구간을 만들지 않는다.**

| 방향 | 유실되면 | 판정 |
|---|---|---|
| MainServer → 셀 (작업 지시) | 아무 일도 안 일어남. 다시 보내면 됨 | **안전** — 네트워크 허용 |
| 셀 → 기록 (완료 · 재고 · 검사) | 실물은 있는데 기록이 없음 | **위험** — 같은 프로세스에 가둔다 |

---

## 4. 작업 한 건의 흐름

```text
Unity ──POST /jobs──────────▶ MainServer
                              입력 검증 · 재고 사전 조회
                              대기 요청 1건 보관 (메모리)
      ◀──202 request_id──────

                              assembly_bridge ──GET /cell/next-job──▶
                              ◀────200 {request_id, product_code,
                                         quantity, recipe_version}────────
                              (건네준 즉시 서버 메모리에서 제거)

                              assembly_bridge
                                BUSY 확인 · 레시피 버전 대조
                                jobs INSERT → RUNNING
                                units INSERT → RUNNING
                                    │ ROS2 Action goal
                                    ▼
                                 조립 노드 (Mock / Real)
                                   레시피 로드 · 좌표 결정
                                   컨베이어 → 조립 → 검사

Unity ◀──ROS2 feedback────────  스텝 진행 (표시 전용, DB 기록 없음)

                              assembly_bridge
                                ASSEMBLED → 재고 차감      (트랜잭션)
                                INSPECTED → 판정·불량 기록 (트랜잭션)
                                COMPLETED → jobs 마감

Unity ──GET /jobs/{job_id}──▶ MainServer ──SELECT──▶ DB
```

---

## 5. MainServer — 해야 할 것

- 작업 요청 접수와 **입력 검증**. 잘못된 제품 · 수량 · 레시피는 `400`으로 즉시 거부한다.
- 접수 시 재고를 **사전 조회**해 시작할 수 없는 작업을 걸러낸다.
- `request_id`를 **서버가 발급**한다.
- 대기 요청은 1건만 보관하고, 이미 있으면 `409`를 준다.
- 셀에 건네준 즉시 메모리에서 제거한다 (at-most-once).
- 모든 SQL을 **파라미터화**한다.
- 기간 조회는 `[period_start, period_end)`로 통일한다.
- 조회는 `datastation_reader` 계정으로만 한다.
- DB 접속 정보는 **실행 환경에서 주입**한다.
- 오류 응답에서 내부 SQL · 접속 문자열 · 비밀번호를 **제거**한다.
- 품질 스캔은 단발성 명령으로 두고 timer/cron이 호출한다.
- 대책서 근거 행을 `evidence`로 **고정**해 나중에 집계가 바뀌어도 문서가 흔들리지 않게 한다.

## 6. MainServer — 하면 안 되는 것

| 금지 | 이유 |
|---|---|
| `production` 스키마에 **쓰기** | assembly_bridge 소유. 이걸 어기면 4장 구조 전체가 무너진다 |
| 셀에서 오는 완료 보고 HTTP 엔드포인트 | outbox 문제를 스스로 만드는 일 |
| `jobs`에 `PENDING` 행을 넣고 셀이 DB를 폴링 | `production`은 확정 기록만 담는 계약. 쓰기 권한이 필요해짐 |
| 로봇 제어 엔드포인트 (조그 · MoveJ · 그리퍼) | 수동 제어는 기존 ROS2 경로 유지 |
| 작업 지시에 좌표를 싣기 | 좌표는 조립 노드 소유 |
| `production_store.py`를 옮겨오거나 import | 셀 소유. 프로세스 간 결합이 된다 |
| 조회 결과 캐싱 · ORM · 메시지 큐 | 조회 지연이 실제 문제가 되기 전에는 불필요 |
| 문자열 연결로 SQL 조립 | 파라미터화만 쓴다 |

### 금지 import

```text
MAIN_SERVER → Unity Assets / C#            금지
MAIN_SERVER → rclpy · fairino_msgs         금지
MAIN_SERVER → mock_sim.py                  금지
MAIN_SERVER → production_store.py          금지 (셀 소유)
MAIN_SERVER → PostgreSQL                   허용 (읽기 전용 역할)
MAIN_SERVER → 셀 HTTP 계약                  허용
```

`MAIN_SERVER/`에서 `rclpy`를 import 하면 경계가 깨진 것이다.

### MainServer가 몰라야 하는 것

- Unity `GameObject` · `Transform` · `Pose`
- ROS 토픽 · 서비스 · 액션 이름
- 컨베이어 모터 명령, MoveJ/MoveL · 그리퍼 순서
- 비전 좌표 변환
- Mock / Real 분기
- 하드웨어 안전 조건
- 레시피 본문 (`recipe_version` 문자열만 다룬다)

---

## 7. 다른 프로세스가 지켜야 할 것

### Unity

| 해야 할 것 | 하면 안 되는 것 |
|---|---|
| `POST /jobs`로 작업 요청 | DB 직접 접속 |
| feedback의 `slot_code`로 씬 슬롯 스냅 | 좌표 · 조립 순서 소유 |
| 관절 · TCP · 카메라 토픽 구독 | 로봇 기구학 변환 (TCP→wrist3) |
| 진행 상태를 `GET`으로 조회 | Mock/Real 직접 분기 |

> 현재 `MockAsyncPlay.BuildObservations()`가 씬 좌표 25개를 만들어 보내고 있다.
> **이 구조 기준으로는 위반이며, 삭제 대상이다.**

### assembly_bridge

| 해야 할 것 | 하면 안 되는 것 |
|---|---|
| `GET /cell/next-job` 폴링 (1초) | 인바운드 포트 열기 |
| BUSY 거부, 기동 시 미완 작업 확인 | 완료 사실을 HTTP로 보고 |
| `jobs` · `units` 생성과 마감 | 좌표 · 레시피 해석 |
| 재고 차감 · 검사 기록을 **트랜잭션**으로 | 커밋 실패를 로그만 남기고 넘어가기 |

### 조립 노드

| 해야 할 것 | 하면 안 되는 것 |
|---|---|
| 레시피 로드와 **로드 시 검증** | DB 접속 |
| `frames.yaml` 기준 상대 pose → 절대좌표 변환 | HTTP 통신 |
| Real은 `source.pose`를 비전으로 보정 | MainServer의 존재를 알기 |
| 스텝별 `verify` 검사 판정 | Unity 씬 구조에 의존 |
| feedback으로 `slot_code` · `step_order` 발행 | 좌표를 외부에서 받기 |

**팀원이 구현하는 것은 ROS2 Action 하나다.**

```text
AssemblyJob.action
  goal:     { job_id, product_code, quantity, recipe_version }   ← 좌표 없음
  feedback: { step_order, part_id, slot_code, state }
  result:   { 성공/실패, 불량 슬롯 }
```

---

## 8. 아직 만들지 않는 것

각 항목이 필요해지는 조건을 함께 적는다. 조건이 성립하기 전에는 만들지 않는다.

| 제외 | 만들 조건 |
|---|---|
| 영속 outbox | DB 쓰기를 셀에서 서버로 옮길 때. 3장 구조에서는 발생하지 않음 |
| 대기 요청 영속화 테이블 | 서버 재시작 중 요청 유실을 허용하지 않게 될 때 |
| Cell Agent 별도 프로세스 | assembly_bridge가 이미 그 역할이다 |
| `PENDING` 작업 큐 · 셀 배정 · claim | 셀이 2개 이상이 될 때 |
| 사용자 인증 · 권한 · 감사 기록 | 외부망 공개 또는 다중 사용자 |
| 메시지 큐 · 캐시 · ORM | 조회 지연이 실제 문제가 될 때 |
| 대책서 메일 자동 발송 | 발송 대상과 승인 절차가 확정될 때 |
| 수량 2개 이상, 작업 취소 | `todo.md`의 기존 항목 순서를 따름 |
