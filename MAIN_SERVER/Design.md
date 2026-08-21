# MainServer — 경계와 소유권

## 이 문서의 범위

MainServer를 도입할 때 **프로세스를 몇 개 두고, DB 쓰기를 누가 소유하며, 레시피와 좌표를
누가 갖고, 실물 로봇이 어느 지점에 붙는지**를 정한다.

새 설계가 아니라 기존 세 문서의 경계 조정이다. 아래 결정은 그대로 유지한다.

| 유지하는 결정 | 근거 문서 |
|---|---|
| `production` 쓰기는 셀의 ROS2 계층이 소유한다 | [Architecture.md](<../UnityDT/Docs/Architecture.md>) |
| Unity는 DB에 직접 접속하지 않는다 | Architecture.md |
| 전송은 ROS2, 진실은 DB | Architecture.md |
| Level 2와 Level 3를 합친다 (셀 1개) | Architecture.md |
| 스키마 3개와 역할 분리 | [DataStation.md](../DATA_STATION/DataStation.md), `DATA_STATION/DB/005_roles.sql` |
| 조회는 파라미터화된 `GET` 전용 | DataStation.md |
| 레시피는 로봇이 소유한다 (DB 아님, 파일 + Git) | [Recipe.md](<../UnityDT/Docs/Recipe.md>) |

이 문서가 바꾸는 것은 9절에 모아 둔다.

구현 문서는 별도로 둔다.

| 문서 | 담는 것 |
|---|---|
| 이 문서 | 결정과 근거. 왜 이 경계인가 |
| [README.md](./README.md) | 기능. 엔드포인트 · 조회 · 스캔 · 코드 구성 |
| [Response.md](./Response.md) | 아키텍처 · 해야 할 것 / 하면 안 되는 것 |
| [Information.md](./Information.md) | MainServer 소유 정보와 참조 정보 규격 |

---

## 1. 결론

```
프로세스 4개.  HTTP 서버 1개.  완료 기록은 네트워크를 건너지 않는다.
좌표는 로봇이 갖는다.
```

네 문장이 전부이고, 나머지는 이 네 문장의 근거다.

---

## 2. 구조

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

화살표가 두 종류인 것에 주목한다. **HTTP는 지시만 나르고, DB는 기록을 소유한다.**

---

## 3. 프로세스별 정의

| 프로세스 | HTTP 역할 | DB 계정 | 소유 |
|---|---|---|---|
| Unity | 클라이언트 | 없음 | 화면 상태, 카메라 시점 |
| **MainServer** | **서버 (유일)** | `datastation_reader` · `defect_report` | 대기 요청, 품질 판정, 대책서 |
| assembly_bridge | 클라이언트 (폴링) | `production_writer` | 셀 작업 수명주기, 실행 기록 |
| 조립 노드 | 없음 | 없음 | 레시피, 좌표, 스텝 실행, 검사 판정 |

### ① Unity — 표시 계층

하는 일.

- 작업 요청 발행 (`POST /jobs`)
- 진행 상태 · 결과 조회 (`GET`)
- ROS2 feedback의 `slot_code`로 씬 슬롯을 찾아 부품 스냅
- 관절 · TCP · 카메라 토픽 구독해 3D 트윈 갱신

몰라야 하는 것.

- 조립 순서, 슬롯 좌표, 부품 pose — **현재 위반 중** (`MockAsyncPlay.cs:609 BuildObservations()`)
- 로봇 기구학 (TCP→wrist3 변환) — **현재 위반 중** (`MockAsyncPlay.cs:696 ToRosPoseRequest`)
- DB 스키마와 접속 정보
- Mock/Real 분기 (`RobotMaster`가 주입한다)

### ② MainServer — 접수 · 조회 계층

하는 일.

- 작업 요청 접수와 입력 검증, `request_id` 발급
- 제품 · 재고 · 작업 · 품질 조회 (`DataStation.md` 5절의 10가지)
- 품질 임계 초과 스캔
- 대책서 생성과 상태 관리

몰라야 하는 것.

- Unity `GameObject` · `Transform` · `Pose`
- `rclpy` · `fairino_msgs` · ROS 토픽 이름
- 컨베이어 모터 명령, MoveJ/MoveL · 그리퍼 순서
- 비전 좌표 변환
- Mock/Real 분기
- 하드웨어 안전 조건
- 레시피 본문 (`recipe_version` 문자열만 다룬다)

`MAIN_SERVER/`에서 `rclpy`를 import 하면 이 경계가 깨진 것이다.

### ③ assembly_bridge — 기록 계층

현재 `Farino_AIO/src/mock_db_mvp/scripts/mock_db_bridge.py`가 이미 이 역할을 한다.
네 가지를 소유하며, **바꾸는 것은 ①의 입구뿐이다.**

| 역할 | 현재 위치 | 변경 |
|---|---|---|
| ① 요청 파싱·검증 | `parse_command` (`:30`) | 입구를 ROS 서비스 → HTTP 폴링 |
| ② 진입 통제 | BUSY 거부, 기동 시 미완 작업 확인 (`:168`) | 유지 |
| ③ 작업 수명주기 소유 | `store.start_job` (`:256`), `start_next_unit` (`:259`) | 유지 |
| ④ DB 트랜잭션 경계 | 완료 3커밋 (`:377-384`), `fail_job` | 유지 |

②③④를 옮기지 않는 것이 이 설계의 핵심이다. 이유는 4절에 있다.

몰라야 하는 것: 좌표, 레시피 본문, 스텝 실행 순서, 비전.

### ④ 조립 노드 — 실행 계층

하는 일.

- 레시피 로드와 로드 시 검증 (버전 일치, `order` 연속, `tool` · `frame` 존재)
- `frames.yaml` 기준 상대 pose → 로봇 절대좌표 변환
- Mock은 레시피 공칭값 그대로, Real은 `source.pose`를 비전 측정값으로 보정
- MoveJ/MoveL · 그리퍼 · 컨베이어 순서 실행
- 스텝별 `verify` 검사 판정
- feedback 발행 (`slot_code`, `step_order`, 상태)

몰라도 되는 것: MainServer의 존재, HTTP 스펙, DB 스키마, Unity 씬 구조, 폴링 주기.

---

## 4. 쓰기 소유권 — 핵심 규칙

> **물리 작업과 그 기록 사이에 네트워크를 두지 않는다.**

로봇 조립은 되돌릴 수 없다. 부품 25개가 꽂혔으면 롤백이 없다. 그 사실을 기록하는 경로에
네트워크가 끼면, 구분 불가능한 세 가지 상태가 생긴다.

| 실제로 일어난 일 | 셀이 보는 것 | 위험 |
|---|---|---|
| 요청이 안 닿음 | 타임아웃 | 재시도 안 하면 기록 유실 |
| 서버는 커밋했는데 응답만 유실 | **똑같은 타임아웃** | 재시도하면 재고 이중 차감 |
| 셀 프로세스가 그 사이 죽음 | 아무것도 못 봄 | 완료 사실 영구 소멸 |

이걸 해결하려면 영속 outbox와 멱등 처리가 필요하다. **그래서 처음부터 그 구간을 만들지
않는다.** assembly_bridge가 `psycopg`로 직접 커밋하면 하나의 트랜잭션이고, 실패는 즉시
알려지며, outbox 문제가 발생 자체를 하지 않는다.

### 방향별 안전성

| 방향 | 유실되면 | 판정 |
|---|---|---|
| MainServer → 셀 (작업 지시) | 아무 일도 안 일어남. 다시 보내면 됨 | **안전** |
| 셀 → 기록 (완료·재고·검사) | 실물은 있는데 기록이 없음 | **위험** |

안전한 방향에만 네트워크를 둔다. 위험한 방향은 같은 프로세스 안에 가둔다.

### 데이터 변경 소유자

| 데이터 변경 | 소유자 | 역할 |
|---|---|---|
| 스키마 · 마이그레이션 | MainServer | 배포 시 별도 자격 |
| 제품 · 재고 · 작업 · 품질 조회 | MainServer | `datastation_reader` |
| `jobs` · `units` 생성 | assembly_bridge | `production_writer` |
| 유닛 완료 · 재고 차감 · 검사 기록 | assembly_bridge | `production_writer` |
| 품질 임계 판정 · 대책서 | MainServer | `defect_report` RW |
| 레시피 · 좌표 · 모션 | 조립 노드 | DB 아님. 파일 + Git |

`005_roles.sql`의 `production_writer` / `datastation_reader` 분리가 이미 이 구조를 전제로
작성돼 있다. 새로 만들 것이 없다.

---

## 5. 작업 한 건의 흐름

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

**셀에서 MainServer로 돌아가는 HTTP가 없다.** 완료 보고 채널이 DB이기 때문이다. 이것이
outbox를 없애는 지점이다.

### 지시는 at-most-once다

MainServer는 대기 요청을 메모리에 들고 있고, 셀에 건네준 순간 지운다. 셀이 받자마자 죽으면
요청은 사라진다. 물리 작업이 시작되지 않았으므로 안전하고, Unity가 다시 요청하면 된다.

셀이 조립 중에 죽은 경우는 Architecture.md의 **조립 노드 재시작** 절차가 이미 다룬다.
`in_flight > 0`인 유닛을 재개하거나 `FAILED`로 정리한다. MainServer는 관여하지 않는다.

### DB를 큐로 쓰지 않는 이유

`jobs`에 `PENDING` 행을 넣고 셀이 DB를 폴링하는 방식도 가능하다. 채택하지 않는다.

- `production`은 "확정된 기록만 담고 수정하지 않는다"는 계약이다. 대기 중인 요청은 확정
  사실이 아니다.
- MainServer가 `production`에 쓰기 권한을 갖게 되어 `datastation_reader` 분리가 무너진다.
- 완료 조건 "조회 서버 계정으로 `production` 쓰기가 거부된다"를 만족할 수 없다.

---

## 6. HTTP 계약

DataStation.md 6절의 `GET` 목록을 그대로 쓰고 **두 개만 추가한다.**

```text
POST /jobs                    Unity → MainServer   작업 접수
GET  /cell/next-job           셀 → MainServer      대기 요청 수령 (at-most-once)
```

### `POST /jobs`

```json
{ "product_code": "...", "quantity": 1, "recipe_version": "mock-r1" }
```

| 상황 | 상태 |
|---|---:|
| 접수됨 | `202` + `request_id` |
| 잘못된 제품·수량·레시피 | `400` |
| 대기 요청이 이미 있음 | `409` |
| DB 조회 실패 | `503` |

작업 지시에 좌표를 싣지 않는다. 제품 · 수량 · 레시피 버전 · 요청 ID가 전부다.

### `GET /cell/next-job`

| 상황 | 상태 |
|---|---:|
| 대기 요청 있음 | `200` + 본문 |
| 없음 | `204` |

폴링 주기는 1초로 시작한다. 셀이 서버가 아니므로 인바운드 포트를 열지 않으며, 셀이
재시작해도 다시 물어보는 것으로 복구가 끝난다.

### 로봇 제어 API는 만들지 않는다

수동 조그와 저수준 제어는 기존 ROS2 경로를 유지한다. MainServer에 제어 엔드포인트가
생기면 3절의 "몰라야 하는 것" 경계가 무너진다.

---

## 7. 레시피와 좌표 — 로봇이 소유한다

### 규칙

> **레시피가 공칭 좌표를 소유하고, 비전은 보정만 한다. Unity는 좌표를 보내지 않는다.**

- 좌표는 `frames.yaml` 기준 **상대값**으로 레시피 파일에 적는다. 지그를 옮기면 `frames.yaml`
  한 곳만 고친다.
- **Mock**은 레시피 값을 그대로 실행한다. 보정이 없다.
- **Real**은 같은 레시피를 읽되 `source.pose`를 비전 측정값으로 덮어쓴다. 레시피는 "여기쯤
  있을 것", 비전은 "실제로 여기 있다".
- Unity는 feedback의 `slot_code`로 씬 슬롯을 찾아 스냅만 한다 — **이미 그렇게 하고 있다.**

이 규칙이 성립하면 Mock과 Real의 계약이 같아지고, 차이는 "비전 보정 유무" 한 곳으로 줄어든다.

### 현재 상태와의 차이

`mock-r1.yaml`에는 pose가 한 줄도 없다. 순서 · `part_id` · `slot_code`와 모션 파라미터만
있고, 좌표 25개는 Unity가 씬 `Transform`에서 계산해 `observations`로 보낸다.
`mock_sim.py:250 resolve_observations()`가 레시피 step과 Unity observation을 `order` ·
`part_id`로 짝지어 실행한다.

```text
현재  진실의 출처는 Unity SampleScene.  레시피가 씬을 따라간다.
변경  진실의 출처는 레시피 파일.        씬이 레시피를 따라간다.
```

| 항목 | 현재 | 변경 후 |
|---|---|---|
| 좌표 소유 | Unity 씬 `Transform` | 레시피 파일 (Git) |
| Mock / Real 계약 | 다름 (씬 좌표 vs 비전) | 동일 |
| 로봇 기구학 | Unity가 wrist3 변환 수행 | 조립 노드 소유 |
| 좌표 재현성 | 씬 편집하면 조용히 바뀜 | `git diff`로 드러남 |
| `recipe_version` 의미 | 실행 조건을 특정 못 함 | 실행 조건을 완전히 특정 |
| Unity 없이 실행 | 불가 | 가능 |
| 코드량 | `BuildObservations` + 헬퍼 약 90 LOC | 삭제 |

작업 계약도 함께 바뀐다.

```text
현재  job = { request_id, recipe_version, observations[25] }   ← Unity 씬 좌표
변경  job = { job_id, product_code, quantity, recipe_version }      ← 좌표 없음
```

`Recipe.md`가 규정한 파일 규격(`source.frame` · `source.pose` · `target` ·
`motion.insert.force_n` · `verify`)과 실제 `mock-r1.yaml`은 아직 다른 형식이다. 규격은 있고
구현이 따라가지 않은 상태이며, 이 절이 그 간극을 메우는 방향을 고정한다.

### 실물 로봇이 붙는 지점

**팀원이 구현하는 것은 ROS2 Action 하나다.**

```text
assembly_bridge
      │ AssemblyJob.action   ← 팀원이 구현하는 계약
      ▼
 조립 노드 ─┬─ Mock  (mock_sim)
            └─ Real  (실물 FR5 + 비전)
```

```text
AssemblyJob.action
  goal:     { job_id, product_code, quantity, recipe_version }   ← 좌표 없음
  feedback: { step_order, part_id, slot_code, state }
  result:   { 성공/실패, 불량 슬롯 }
```

팀원이 몰라도 되는 것: MainServer의 존재와 HTTP 스펙, `POST /jobs` · `GET /cell/next-job`,
DB 스키마와 접속 정보, Unity 씬 구조와 `Transform`, 폴링 주기와 요청 ID 규칙.

좌표 이관을 하지 않으면 MainServer를 만들어도 팀원은 Mock 경로를 재사용할 수 없고, 통합이
경계 재작성이 된다.

---

## 8. 코드베이스

```text
MAIN_SERVER/
├── README.md          기능 — 엔드포인트 · 조회 · 스캔 · 코드 구성
├── Response.md        아키텍처 · 해야 할 것 / 하면 안 되는 것
├── server.py          HTTP 라우팅
├── queries.py         읽기 전용 SQL (datastation_reader)
├── scan_quality.py    임계 스캔 → alerts · evidence · XLSX
├── templates/         대책서 공식 양식 · 샘플 · 필드매핑
├── data/              참조 데이터시트 XLSX 1개
└── tests/
```

`DATA_STATION/DataStation.md` 7절이 예고한 `server.py` · `scan_quality.py`가 여기로 온다.
`scan_quality`는 마이크로서비스나 메시지 큐 없이 단발성 명령으로 두고, systemd timer 또는
cron이 호출한다. API 프로세스와 코드베이스는 공유하되 DB 계정은 분리한다.

### 금지 참조

```text
Unity          → DB 직접 접속                금지
Unity          → 좌표 · 조립 순서 소유         금지 (현재 위반)
MAIN_SERVER    → Unity Assets / C#          금지
MAIN_SERVER    → mock_sim.py                금지
MAIN_SERVER    → rclpy · fairino_msgs       금지
MAIN_SERVER    → production_store.py        금지 (셀 소유)
MAIN_SERVER    → production 쓰기             금지
MAIN_SERVER    → PostgreSQL                 허용 (읽기 전용 역할)
MAIN_SERVER    → 셀 HTTP 계약                허용
조립 노드       → DB · HTTP                  금지
```

`production_store.py`는 MainServer로 옮기지 않는다. 4절에 따라 쓰기는 셀이 소유하므로 셀에
남는다. MainServer는 자기 몫의 읽기 전용 `queries.py`를 따로 갖는다. 경로 import로 공유하지
않는다 — 중복 몇 줄이 프로세스 간 결합보다 싸다.

---

## 9. 이 문서가 바꾸는 결정

| 문서 | 기존 | 변경 |
|---|---|---|
| DataStation.md 6절 | "`POST /jobs`와 로봇 제어 API는 만들지 않는다" | `POST /jobs`만 추가. 로봇 제어 API는 계속 만들지 않는다 |
| DataStation.md 10절 | "작업 생성 HTTP API" 제외 | 제외에서 해제 |
| DataStation.md | 이름 "조회 서버" | "MainServer"로 승격. 조회 + 접수 + 품질 + 문서 |
| Architecture.md 확장점 | HTTP 어댑터를 "같은 노드 프로세스에" | 별도 MainServer 프로세스로. 노드는 ROS2만 안다 |
| Architecture.md | 대책서 발행 백엔드 (별도 프로세스) | MainServer에 흡수. 읽기 전용 원칙은 유지 |
| API.md 4.3 | Unity → `/unity/assembly/start` | Unity는 `POST /jobs`. 셀 입구는 HTTP 폴링 |
| `mock_db_bridge.py` | 이름 | `assembly_bridge`. 역할 ②③④는 그대로 |
| `mock-r1.yaml` · `MockAsyncPlay` | 좌표를 Unity 씬이 소유 | 좌표를 레시피가 소유. `BuildObservations()` 삭제 |
| `request_id` | Unity가 `Guid.NewGuid()`로 발급 | MainServer가 접수 시 발급 |

---

## 10. 하지 않는 것

각 항목이 필요해지는 조건을 함께 적는다. 조건이 성립하기 전에는 만들지 않는다.

| 제외 | 만들 조건 |
|---|---|
| 영속 outbox | DB 쓰기를 셀에서 서버로 옮길 때. 4절 구조에서는 발생하지 않음 |
| Cell Agent 별도 프로세스 | assembly_bridge가 이미 그 역할이다. 프로세스를 늘리지 않음 |
| `PENDING` 작업 큐 · 셀 배정 · claim | 셀이 2개 이상이 될 때 |
| 사용자 인증 · 권한 · 감사 기록 | 외부망 공개 또는 다중 사용자 |
| 메시지 큐 · 캐시 · ORM | 조회 지연이 실제 문제가 될 때 |
| 대책서 메일 자동 발송 | 발송 대상과 승인 절차가 확정될 때 |
| 수량 2개 이상, 작업 취소 | `todo.md`의 기존 항목 순서를 따름 |

**네트워크 단절 중 완료된 작업의 기록은 4절 구조에서 유실되지 않는다.** 셀과 DB가 끊기면
커밋이 실패하고 셀이 즉시 `FAILED`로 처리한다. 실물은 있는데 기록이 없는 상태는 생기지
않는다.

---

## 11. 전환 순서

1. **레시피에 좌표를 넣는다** — `mock-r1.yaml`에 `source` · `target` pose 추가,
   `joint_points`의 `item_ready` · `assembly_ready` placeholder를 실측값으로 교체.
   현재 씬이 진실이므로 지금 값을 뽑아 YAML에 박고 방향만 뒤집는다.
2. **`mock_sim.py`에서 `observations` 제거** — `resolve_observations()`를 레시피 단독 로드로
   바꾸고, `parse_command`에서 `observations` 검증을 걷어낸다.
3. **Unity에서 좌표 소유 제거** — `BuildObservations()`와 `ToRosPoseRequest` 삭제.
   `request_id` 발급도 Unity에서 뺀다.
4. `mock_db_bridge` 입구를 ROS 서비스 → HTTP 폴링으로 교체. ②③④는 손대지 않는다.
5. `MAIN_SERVER/` 구현. `queries.py` + `GET` 목록 + `POST /jobs` + `GET /cell/next-job`.
6. Unity `Scenario.Run()`에서 컨베이어 순서 소유를 제거하고 `POST /jobs` 호출로 교체.
7. `scan_quality.py`와 XLSX 생성.
8. 팀원의 Real 조립 노드를 `AssemblyJob.action`에 연결.

1~3을 건너뛰고 5부터 하면 서버는 생기지만 좌표는 여전히 Unity에 남는다. 그 상태로 Real
노드를 붙이면 통합이 아니라 경계 재작성이 된다.

---

## 12. 열려 있는 결정

1. **대기 요청 영속화** — 현재는 MainServer 메모리. 서버 재시작 중 요청 유실을 허용하지
   않으려면 테이블 추가. 물리 작업 전이라 안전하므로 우선순위 낮음.
2. **`part_id` ↔ `group_id` 연결** — 양식의 「대체품」·「판단자료 D」와 조회 9가
   `alerts.part_id`에서 `part_catalog`로 넘어가야 하는데 공통 키가 없다.
   `part_catalog.part_group_links` 신설을 권한다 (`templates/불량대책서_필드매핑.md`).
3. **`source_recipe_version` 결정 규칙** — 기간 내 레시피가 섞일 때 문서를 나눌지.
4. **`mock_sim.py` 위치** — 1,185 LOC 실행 로직이 `Farino_AIO/notebooks/`에 있다.
5. **XLSX 생성 라이브러리** — 새 외부 의존성이므로 AGENTS.md에 따라 승인 필요.
6. **레시피 좌표 단위** — `Recipe.md`는 frame 상대 mm/deg, 현재 Unity는 절대 mm + 쿼터니언.
   1번 작업에서 어느 쪽으로 통일할지 확정.
