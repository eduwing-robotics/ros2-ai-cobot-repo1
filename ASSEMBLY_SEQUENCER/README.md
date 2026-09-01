# Assembly Sequencer

이 폴더는 MainServer와 독립 실행하는 자동 조립 ROS 2 프로세스와 공통 DB
Writer를 소유한다. Mock 실행 노드와 DB Writer는 구현됐고 Real 실행 노드는
팀 구현과 합류할 때 같은 DB 경계를 사용한다.

## 역할과 책임

- 역할: PostgreSQL 조립 요청을 실제 Mock/Real 작업 흐름으로 실행하는 Orchestrator
- 책임: 요청 claim·중복 방지, 조립·이송·검사 순서, 완료·실패·timeout 전달, 생산 DB 갱신
- 책임 아님: Unity UI, HTTP 요청 수신, 좌표 변환, Raw ROS 메시지와 하드웨어 직접 제어

## 구현 상태

| 구분 | 현재 구현 | Sequencer 역할 |
| --- | --- | --- |
| Mock orchestration | `assembly_sequencer.mock_node` | claim 이후 시작·이송·검사·완료 순서와 단계별 실패 마감만 담당한다. |
| Mock contract | `assembly_sequencer.mock_contract` | 명령·feedback 검증, 상태 전이와 snapshot 생성을 완결한다. |
| Mock backend | `assembly_sequencer.mock_backend`, 기존 `mock_sim.py` | 내부 ROS Service 요청·응답 검증과 실제 Mock 로봇 실행을 담당한다. |
| DB | `db.production_store`, `db.writer` | PostgreSQL command claim과 Job·Unit 생성은 원자적 transaction, 완료 갱신은 bounded FIFO Worker가 담당한다. |
| Real | 저수준 FR5 명령·상태만 부분 구현 | 향후 Real 노드가 같은 Writer를 호출한다. |

## 프로세스 경계

```text
Unity ── HTTP POST ──→ MainServer ── INSERT ──→ PostgreSQL control queue
                                                   │ claim + Job·Unit
                                                   ▼
                                            AssemblySequencer
                                                   │
                                                   ├─ ROS2 ─→ Mock 또는 Real Robot
                                                   ├─ Conveyor·Inspection
                                                   └─ DB Writer ─→ PostgreSQL production

Unity·MainServer ── ROS2 status ───────────────────┘
```

- AssemblySequencer는 MainServer와 별도 프로세스로 실행한다.
- MainServer가 중단되어도 PostgreSQL에 저장된 요청과 이미 시작한 작업은 계속 처리한다.
- MainServer HTTP를 통한 신규 요청은 MainServer 중단 중 사용할 수 없다.
- MainServer는 `production`을 조회하고 `control.assembly_requests`만 기록한다.

- AssemblySequencer만 Job·Unit·재고·검사 등 `production`을 갱신한다.

Sequencer의 업무 흐름에는 좌표 변환, Raw ROS 메시지 조립, SQL과 하드웨어 직접 제어를 넣지 않는다. 입력 검증, 변환, 통신, 실제 완료 감지와 timeout은 각 하위 공개 진입점이 완결한다.

## Real API 계약

세부 상태·Schema와 구현자 준수사항은 [`API.md`](API.md)를 따른다.

| 기능 | 인터페이스 | 송신자 → 수신자 | 상태 |
| --- | --- | --- | --- |
| 조립 시작 | `/real/assembly/start` | AssemblySequencer Real adapter → `real_assembly` | 계약 확정·미구현 |
| 상태 조회 | `/real/assembly/status` | AssemblySequencer Real adapter → `real_assembly` | 계약 확정·미구현 |
| 진행·완료·실패 | `/real/assembly/progress` | `real_assembly` → AssemblySequencer Real adapter → Unity | 계약 확정·미구현 |
| FR5 명령 | `/fairino_remote_command_service` | `real_assembly`의 Robot 경계 → `fr_command_server` | 저수준 부분 구현 |
| FR5 상태 | `/nonrt_state_data` | `fr_command_server` → `real_assembly` | 구현 |
| 검사 | `TBD` Action | `real_assembly` → `inspection_node` | 제안·협의 필요 |
| 컨베이어 | `TBD` Action | `real_assembly` → `conveyor_controller` | 제안·협의 필요 |

HTTP의 `accepted=true`는 PostgreSQL 저장 성공만 뜻한다. Sequencer가 요청을 claim해 Job·Unit을 만든 뒤 Real backend에 실행을 요청하며, 실제 조립과 검사 결과가 확정된 뒤에만 terminal 진행 상태를 발행한다.

## Mock 실행

AssemblySequencer와 기존 Mock backend만 독립 실행할 수 있다.

```bash
cd /home/codlab/Main_Unity
source /opt/ros/jazzy/setup.bash
source Farino_AIO_Mock/install/setup.bash

cd ASSEMBLY_SEQUENCER
colcon build --symlink-install
source install/setup.bash

export PRODUCTION_DB_DSN='dbname=main_unity_mock_test'
ros2 launch assembly_sequencer mock.launch.py
```

MainServer는 별도 터미널에서 같은 DB를 가리키고 `MAIN_SERVER_MODE=mock`으로
실행한다. POST와 조회 API에는 ROS가 필요 없고, 현재 상태 route를 사용할 때만
같은 ROS 환경을 source한다. 기존
`ros2 launch mock_db_mvp launch_mock.launch.py` 올인원 명령도 호환된다.

## Queue 구분

- `control.assembly_requests`는 PostgreSQL 영속 command queue다. MainServer가
  요청을 저장하고 AssemblySequencer가 runtime mode별 FIFO로 claim한다. 아직
  claim하지 않은 `QUEUED` 요청은 프로세스 재시작을 넘어 보존된다.
- `DbWriter` queue는 AssemblySequencer 프로세스 내부의 비영속 bounded queue다.
  실제 작업 완료 뒤 production 갱신을 callback 밖에서 재시도한다.

### 비동기 production 갱신

별도 DB Writer 서버나 메시지 브로커는 두지 않는다.

```text
Robot·Inspection callback
  → 작업 상태 확정
  → DB Update Event enqueue
  → callback 반환

Async DB Worker
  → PostgreSQL transaction
  → commit 성공: queue 제거
  → 실패: 재시도하고 오류 보존
```

- callback에서 PostgreSQL 응답을 기다리지 않는다.
- 검사 callback은 DB 이벤트를 추가하며 queue를 제거하지 않는다.
- queue 항목은 DB commit 성공 후에만 제거한다.
- Raw SQL 대신 `ASSEMBLY_COMPLETED`, `INSPECTION_RECORDED`,
  `JOB_FINISHED` 도메인 이벤트를 저장한다.
- 각 이벤트는 추적용 `event_id`를 가지며 재시도 안전성은 Store의 현재 상태
  검사로 보장한다.
- 관절·TCP 스트림과 고빈도 상태는 생산 DB에 저장하지 않는다.
- 재고 확인·예약처럼 작업 시작 전 필수인 검증은 비동기 이력 저장과 분리한다.
- queue가 가득 차거나 재시도가 실패해도 이벤트를 조용히 폐기하지 않는다.

내부 이벤트의 최소 필드는 다음과 같다.

| 필드 | 설명 |
| --- | --- |
| `event_id` | 중복 적용 방지 식별자 |
| `event_type` | DB 갱신 종류 |
| `job_id`, `unit_id` | 작업·Unit 식별자 |
| `payload` | 갱신에 필요한 데이터 |
| `created_at` | 이벤트 생성 시각 |
| `attempt_count`, `next_retry_at`, `last_error` | 재시도 상태 |

`QUEUED` command는 PostgreSQL에 영속된다. Sequencer가 재시작되면 이전
`RUNNING` 요청은 안전하게 `FAILED`로 마감하며 중간 로봇 동작을 자동 재개하지
않는다. production update event를 재시작 후에도 재시도하는 Outbox와 SECS/GEM
Adapter는 확장 범위이며 현재 구현으로 간주하지 않는다.

정상 claim 이후 production 갱신 호출은 다음처럼 제한한다.

```python
work = writer.claim(runtime_mode, product_code, product_version, recipe_version)
writer.assembly_completed(work["unit_id"])
writer.inspection_recorded(work["unit_id"], result, defects, image_path)
writer.finish(work["job_id"], "COMPLETED")
```

## 안전·실패 정책

- 물리 E-STOP은 하드와이어드 안전회로가 수행한다.
- ROS 2는 안전 상태를 수신해 신규 명령을 차단하고 작업 실패를 전달한다.
- DB 지연·실패가 안전 상태 callback과 로봇 정지를 막아서는 안 된다.
- 실제 작업 완료 상태와 DB 동기화 상태는 분리한다.
- DB를 기준으로 확인해야 하는 재고·레시피 조건을 검증할 수 없으면 신규 작업을 시작하지 않는다.

이 설계는 SECS/GEM Spooling 개념을 참고하지만 SECS/GEM 호환 구현은 아니다.
