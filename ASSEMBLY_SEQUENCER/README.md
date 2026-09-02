# Assembly Sequencer

이 폴더는 MainServer와 독립 실행하는 자동 조립 ROS 2 프로세스와 공통 DB
Writer를 소유한다. Mock 실행 노드와 DB Writer는 구현됐고 Real 실행 노드는
팀 구현과 합류할 때 같은 DB 경계를 사용한다.

## 역할과 책임

- 역할: PostgreSQL 조립 요청을 실제 Mock/Real 작업 흐름으로 실행하는 Orchestrator
- 책임: Job claim·중복 실행 방지, 조립·이송·검사 순서, 완료·실패·timeout 전달, 생산 DB 갱신
- 책임 아님: Unity UI, HTTP 요청 수신, 좌표 변환, Raw ROS 메시지와 하드웨어 직접 제어

## 구현 상태

| 구분 | 현재 구현 | Sequencer 역할 |
| --- | --- | --- |
| Mock orchestration | `assembly_sequencer.mock_node` | Job·Unit claim 이후 시작·이송·검사·완료 순서와 단계별 실패 마감만 담당한다. |
| Mock contract | `assembly_sequencer.mock_contract` | 명령·feedback 검증, 상태 전이와 snapshot 생성을 완결한다. |
| Mock backend | `assembly_sequencer.mock_backend`, 기존 `mock_sim.py` | 내부 ROS Service 요청·응답 검증과 실제 Mock 로봇 실행을 담당한다. |
| Recipe parser | `assembly_sequencer.recipe` | Mock·Real 공통 YAML schema를 시작 전에 엄격 검증한다. |
| DB | `db.production_store`, `db.writer` | UUID Job claim과 Unit 생성은 원자적 transaction, 완료 갱신은 bounded FIFO Worker가 담당한다. |
| Real | 공통 Recipe parser 구현, 실행 노드 미구현 | 타 브랜치 Action과 FR5 경계가 합류하면 같은 Recipe snapshot으로 실행한다. |

## 프로세스 경계

```text
Unity ── HTTP Job ──→ MainServer ── INSERT ──→ production.jobs
  │                                               │
  │ Mock 현재 좌표                               │ claim
  └──────── ROS start ───────────────→ AssemblySequencer
                                             │ Job·Unit 상태
                                             ▼
                                      Mock 또는 Real backend
```

MainServer는 UUID Job만 생성한다. Sequencer는 Job을 검증하고 Unit을 생성한 뒤
실행 완료·검사 결과를 DB에 반영한다. Mock 좌표는 Unity가 ROS 시작 시점에 보내며
DB에 저장되지 않는다. Real backend는 같은 지점에서 비전·센서로 좌표를 구한다.

Sequencer의 업무 흐름에는 좌표 변환, SQL 또는 하드웨어 저수준 명령을 넣지
않는다. 통신·timeout·실제 완료 감지는 각 backend 공개 진입점이 완결한다.

## 공통 Recipe parser

`assembly_sequencer.recipe.load_recipe()`가 AssemblySequencer 소유 YAML을 읽고
파일명·`recipe_version`, `base_link` frame, 관절점, motion, 단일-key workflow,
gripper profile과 연속된 steps를 fail-closed로 검증한다. Real 실행 노드는 ROS
초기화와 장비 명령 전에 한 번 로드한 snapshot만 사용해야 한다.

소스 트리에서 실제 Recipe를 검사하는 명령:

```bash
PYTHONPATH=ASSEMBLY_SEQUENCER/src/assembly_sequencer \
python3 -m assembly_sequencer.recipe \
  ASSEMBLY_SEQUENCER/src/assembly_sequencer/config/recipes/assembly-r1.yaml
```

Parser는 로봇·비전·컨베이어 API를 호출하지 않는다. 실행 순서의 의미와 각
컴포넌트 계약은 아래 API 문서가 소유한다.

## Real API 계약

세부 상태·Schema와 구현자 준수사항은 [`API.md`](API.md)를 따른다.

| 기능 | 인터페이스 | 송신자 → 수신자 | 상태 |
| --- | --- | --- | --- |
| 조립 시작 | `/real/assembly/start` | AssemblySequencer Real adapter → `real_assembly` | 계약 확정·미구현 |
| 상태 조회 | `/real/assembly/status` | AssemblySequencer Real adapter → `real_assembly` | 계약 확정·미구현 |
| 진행·완료·실패 | `/real/assembly/progress` | `real_assembly` → AssemblySequencer Real adapter → Unity | 계약 확정·미구현 |
| FR5 명령 | `/fairino_remote_command_service` | `real_assembly`의 Robot 경계 → `fr_command_server` | 저수준 부분 구현 |
| FR5 상태 | `/nonrt_state_data` | `fr_command_server` → `real_assembly` | 구현 |
| Pick·Place 자세 | `/vision/pick_place/resolve` Action | `real_assembly` → Pick/Place Vision | 계약 확정·비전 브랜치 구현 필요 |
| 검사 | `/vision/inspection/run` Action | `real_assembly` → Inspection Vision | 계약 확정·검사 비전 브랜치 구현 필요 |
| 컨베이어 이동 | `/conveyor/move_to_station` Action | `real_assembly` → Conveyor controller | 계약 확정·비전/컨베이어 브랜치 구현 필요 |
| 컨베이어 상태 | `/conveyor/state` Topic | Conveyor controller → `real_assembly`, Unity | 계약 확정·비전/컨베이어 브랜치 구현 필요 |

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

Pause·resume은 기존 `/unity/assembly/start` 서비스에 `job_id`와 함께 보내며,
Mock은 YAML 고수준 동작 경계에서 정지하고 `PAUSED` 피드백으로 확인한다. DB Job·Unit은
`RUNNING`을 유지한다.

MainServer는 별도 터미널에서 같은 DB를 가리키고 `MAIN_SERVER_MODE=mock`으로
실행한다. POST와 조회 API에는 ROS가 필요 없고, 현재 상태 route를 사용할 때만
같은 ROS 환경을 source한다. 기존
`ros2 launch mock_db_mvp launch_mock.launch.py` 올인원 명령도 호환된다.

## 비동기 production 갱신

`production.jobs`가 유일한 영속 작업 진입점이다. `DbWriter` queue는 실제 완료
뒤 DB 갱신을 callback 밖에서 재시도하는 프로세스 내부 bounded FIFO다.

```python
work = writer.claim(job_id, product_code, product_version, recipe_version)
writer.assembly_completed(work["unit_id"])
writer.inspection_recorded(work["unit_id"], result, defects, image_path)
writer.finish(work["job_id"], "COMPLETED")
```

Job 완료는 검사 `PASS` 누적이 `requested_quantity`에 도달했을 때만 허용된다.
검사 FAIL Unit은 완료된 시도로 남고 Sequencer가 같은 Unity 좌표로 새 Unit을 만든다.
Sequencer
재시작은 실행 중 Unit만 FAILED로 바꾸고 Job은 RUNNING으로 유지한다. Mock 좌표는
폐기하며 Unity가 같은 `job_id`로 현재 좌표를 다시 보내야 한다.

## 안전·실패 정책

- 물리 E-STOP은 하드와이어드 안전회로가 수행한다.
- ROS 2는 안전 상태를 수신해 신규 명령을 차단하고 작업 실패를 전달한다.
- DB 지연·실패가 안전 상태 callback과 로봇 정지를 막아서는 안 된다.
- 실제 작업 완료 상태와 DB 동기화 상태는 분리한다.
- DB를 기준으로 확인해야 하는 재고·레시피 조건을 검증할 수 없으면 신규 작업을 시작하지 않는다.

이 설계는 SECS/GEM Spooling 개념을 참고하지만 SECS/GEM 호환 구현은 아니다.
