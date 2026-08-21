# Mock DB MVP 구현 통합 보고서

## 결과 요약

기존 Unity와 기존 Mock 로봇 코드를 수정하지 않고 `mock_db_mvp` 독립 ROS2 패키지를 추가했다.
Unity는 기존 서비스와 feedback만 사용하며 DB 자격증명이나 SQL을 갖지 않는다. bridge가 Job과
Unit을 만들고, 기존 Mock의 실제 `COMPLETED`를 받은 뒤 재고 차감·검사·Job 종료를 처리한다.
모든 DB 작업이 성공한 경우에만 Unity에 최종 `COMPLETED`를 전달한다.

코드와 SQL 작성, Mock DB 기준정보 적용, 안전 가드 이후 통합 테스트, 권한 매트릭스, 패키지
빌드와 ROS graph 검증까지 완료됐다. 실제 `main_unity_mock` role 적용, 반복 검증용 영구 테스트
DB, Unity 전체 시연과 Real 연동은 아직 남아 있다.

## 최종 파이프라인

```text
Unity
  Scenario -> IRobotScenarioControl.ExecuteAsync() -> mockAsyncPlay
  /unity/assembly/start
          |
          v
ROS2 mock_db_bridge
  1. start_job(MOCK-SEMICONDUCTOR-ASSEMBLY, mock-v1, 1, mock-r1)
  2. start_next_unit(job_id)
  3. 내부 Mock 서비스 호출
          |
          v
기존 mock_sim.py
  /mock_db_mvp/internal/assembly/start
  25개 observation 실행
  /mock_db_mvp/internal/assembly/feedback
          |
          v
ROS2 mock_db_bridge
  STARTED/PICKED/PLACED -> Unity에 중계
  COMPLETED -> 재고 차감 -> random 검사 -> Job 종료
  DB 성공 -> Unity에 COMPLETED
  DB/Mock 실행 실패 -> Job FAILED 및 Unity에 FAILED
          |
          v
PostgreSQL main_unity_mock

DataStation -> 별도 read-only LOGIN -> datastation_reader -> SELECT
```

launch remap이 기존 Mock의 `/unity/assembly/start`와 `/unity/assembly/feedback`을 내부 이름으로
숨기므로 외부 Unity endpoint는 bridge만 제공한다.

검사 `FAIL`은 실행 실패와 다르다. 조립과 검사 처리가 정상 종료되면 Unit과 Job은
`COMPLETED`, `inspection_result=FAIL`, defect 1건으로 저장되고 Unity에도 `COMPLETED`가 전달된다.
또한 bridge 시작 시 active DB Job이 있으면 영속되지 않은 Unity `request_id`를 복구할 수
없으므로 외부 endpoint를 열기 전에 fail-fast한다.

## 생성 파일과 역할

| 경로 | 역할 |
|---|---|
| `DATA_STATION/DB/004_mock_seed.sql` | `mock-r1.yaml`과 일치하는 Mock 제품, 6 parts, 25 slots와 완성품 10대분 재고를 멱등 저장 |
| `DATA_STATION/DB/005_roles.sql` | ROS2 writer와 DataStation reader의 NOLOGIN 최소 권한 정의. 실제 적용과 LOGIN 생성은 별도 |
| `Farino_AIO/src/mock_db_mvp/CMakeLists.txt` | 두 Python script와 launch를 설치하는 최소 ament package 설정 |
| `Farino_AIO/src/mock_db_mvp/package.xml` | 기존 ROS2 package 및 설치된 psycopg 의존성 선언 |
| `Farino_AIO/src/mock_db_mvp/scripts/production_store.py` | psycopg3 업무 단위 transaction과 조회 API |
| `Farino_AIO/src/mock_db_mvp/scripts/mock_db_bridge.py` | Unity 계약 유지, DB 수명주기 소유, 내부 Mock 중계, random 검사와 commit-gated 완료 처리 |
| `Farino_AIO/src/mock_db_mvp/launch/mock_db_mvp.launch.py` | 기존 Mock 노드 remap, Unity endpoint와 bridge 실행, 검사 확률/seed 설정 |
| `Farino_AIO/src/mock_db_mvp/test/test_production_store.py` | `_test` 전용 DB에서 정상·멱등·검사 규칙·rollback을 검증하는 통합 테스트 |

빌드 과정의 `build/`, `install/`, `log/` 및 Python `__pycache__`는 생성 소스가 아니라 재생성
가능한 산출물이다.

## ProductionStore 계약

공개 API는 다음으로 확정됐다.

```python
start_job(product_code, product_version, quantity, recipe_version) -> job_id
start_next_unit(job_id) -> unit_id
complete_assembly_and_consume_stock(unit_id)
record_inspection(unit_id, result, defects, image_path=None)
fail_unit(unit_id)
finish_job(job_id, final_status)
get_job_state(job_id)
get_active_job_state()
get_product_slot_codes(job_id)
```

- write API마다 새 connection과 transaction을 사용하며 오류를 호출자에게 전달한다.
- `PRODUCTION_DB_DSN`은 필수이고 기본 DB fallback은 없다.
- `%s` parameter와 `FOR UPDATE`를 사용한다.
- 조립 완료 transaction 안에서 재고 전체 차감과 timestamp를 함께 commit한다.
- 조립 완료와 동일 검사 callback은 멱등 처리한다.
- PASS/FAIL 결함 수, defect type과 제품 슬롯 정합성을 검사한다.
- 요청 수량 초과 Unit과 미완료/실패 Unit이 있는 Job 완료를 거부한다.
- 실패 사유 column이 없는 현재 schema에 맞춰 이유 저장 인자를 추가하지 않았다.

## 선택한 분기점과 대안

| 분기점 | MVP 선택 | 보류한 대안과 전환 시점 |
|---|---|---|
| Unity↔ROS2 통신 | 기존 service+feedback 유지 | 취소·장시간 작업·Real 전에 ROS2 Action 검토 |
| 격리 방식 | 독립 `mock_db_mvp` package와 launch remap | 시연 후 실제 중복이 확인될 때만 기존 package에 통합 |
| 제품/수량 | Mock 제품 `mock-v1`, 수량 1 고정 | UI 입력과 다수량은 첫 시연 이후 |
| 검사 | Mock에서 기본 20% random FAIL | Real에서는 random을 제거하고 실제 비전 결과 사용 |
| DB 코드 | Mock/Real 공용 ProductionStore 하나 | 모드별 쿼리 복사본은 만들지 않음 |
| transaction | 업무 API별 독립 commit | 전 과정 단일 transaction/outbox/보상 transaction은 MVP 제외 |
| 요청 멱등성 | 실행 중 메모리 `request_id` 상관관계 | 재시작 복구가 필요할 때 DB UNIQUE request key와 복구 상태 추가 |
| 실패 Unit | Job을 실패로 종료 | 동일 Job 재시도 정책은 sequence/schema 의미 결정 후 구현 |

## 검증 결과

### 완료된 검증

1. Schema와 Seed 적용

```bash
psql -X -v ON_ERROR_STOP=1 -d main_unity_mock \
  -f DATA_STATION/DB/001_schema.sql
psql -X -v ON_ERROR_STOP=1 -d main_unity_mock \
  -f DATA_STATION/DB/004_mock_seed.sql
```

현재 읽기 전용 재확인 결과:

- 제품: `MOCK-SEMICONDUCTOR-ASSEMBLY`, version `mock-v1`, selectable
- parts: 6
- slots: 25
- `buildable_quantity`: 10
- jobs/units/unit_defects: 0/0/0
- `production_writer`/`datastation_reader` DB role: 아직 없음

2. ProductionStore

정상 완료와 중복 조립 완료, Job 수량 제한, Job 종료 후 동일 검사 callback, 타제품 슬롯과
PASS/FAIL 규칙, 부족 재고 rollback을 포함한 최신 통합 테스트 3건을 안전 가드 이후 격리
`main_unity_mock_test`에서 실행했다.

- `PRODUCTION_DB_TEST_DSN` 필수
- 연결한 실제 DB명이 `_test`로 끝나야 실행
- 검증된 DSN만 `PRODUCTION_DB_DSN`으로 주입

- 결과: `Ran 3 tests ... OK` (0.343초)
- cleanup 확인: `jobs|units|unit_defects = 0|0|0`
- 격리 PostgreSQL 서버와 임시 디렉터리는 검증 후 종료·삭제

3. DB role 권한

- 격리 DB에 `005_roles.sql` 적용 성공
- 권한 매트릭스: `t|t|t|f|f|t|t|f`
- writer 허용 연산과 reader SELECT 성공
- writer의 `product_name` UPDATE 거부
- reader의 `jobs` INSERT 거부
- 실제 `main_unity_mock`에는 아직 role SQL을 적용하지 않음

4. ROS2 package와 bridge

- 최종 package build 성공
- bridge self-check 성공
- package executable 조회와 launch `--show-args` 성공
- bridge 단독 ROS graph에서 외부 service server/publisher와 내부 client/subscriber type 계약 확인
- Ctrl-C 종료 코드 0, traceback 없음
- 재고 변경과 Unity GUI 실행을 피하기 위해 full launch와 Unity GUI 전체 시연은 실행하지 않음

```bash
cd Farino_AIO
colcon build --packages-select mock_db_mvp --symlink-install
source install/setup.bash
PYTHONDONTWRITEBYTECODE=1 \
  python3 src/mock_db_mvp/scripts/mock_db_bridge.py --self-check
```

### 반복 검증 및 운영 적용 명령

아래는 이미 임시 격리 DB에서 통과한 테스트를 영구 테스트 DB에서 반복할 때 사용하는 명령이다.

```bash
createdb main_unity_mock_test
psql -X -v ON_ERROR_STOP=1 -d main_unity_mock_test \
  -f DATA_STATION/DB/001_schema.sql
PRODUCTION_DB_TEST_DSN='dbname=main_unity_mock_test' \
  python3 Farino_AIO/src/mock_db_mvp/test/test_production_store.py -v
```

role SQL은 관리자 권한으로 명시적으로 적용한다. 애플리케이션 LOGIN과 비밀번호는 저장소 밖에서
생성하고 NOLOGIN group role에 연결한다.

```bash
psql -X -v ON_ERROR_STOP=1 -d main_unity_mock \
  -f DATA_STATION/DB/005_roles.sql
```

Mock 실행 예시는 다음과 같다.

```bash
cd Farino_AIO
source install/setup.bash
export PRODUCTION_DB_DSN='postgresql://<writer-login>@<host>/main_unity_mock'
ros2 launch mock_db_mvp mock_db_mvp.launch.py \
  inspection_fail_probability:=0.0 random_seed:=1
```

## 미완료 TODO

1. PostgreSQL 관리자가 `005_roles.sql`을 적용하고 deployment LOGIN 계정 두 개를 각 group
   role에 연결한다. 검증된 권한 매트릭스를 실제 `main_unity_mock` 계정으로 확인한다.
2. 반복 통합 검증에 사용할 영구 `_test` DB를 마련한다.
3. Unity 전체 시연에서 25개 진행 feedback, DB commit 뒤 COMPLETED, 재고 감소, PASS/FAIL 저장과
   오류 경로를 확인한다.
4. Mock 시연 후 service+feedback을 ROS2 Action으로 전환할지 결정한다.
5. Real 구현은 같은 ProductionStore를 사용하고 random 검사를 실제 비전 결과로 바꾼다.
6. bridge 재시작/재전송을 지원하기 전에 `request_id` 영속 UNIQUE 키와 복구 정책을 설계한다.
7. 실패 Unit을 동일 Job에서 재시도할지 Job 전체 실패로 둘지 정책을 정한다.
8. Unity+Mock 검증과 별도로 실제 FR5, 실제 비전, Real DB 접속을 포함한 실기 시연을 수행한다.

## 기존 변경 보호와 폐기/원복 경계

- 기존 `Farino_AIO/notebooks/mock_sim.py`, 기존 launch, Unity C#, Scene과 Prefab은 수정하지 않았다.
- `notebooks/mock_sim.py`의 `--preview-seconds` 기본값 2→0 변경은 이번 작업 전부터 있던 사용자
  변경이며, 이번 작업에서는 수정하거나 되돌리지 않았다.
- 저장소에 이미 있던 사용자 변경과 이번 작업과 무관한 파일은 수정하거나 되돌리지 않았다.
- DB 연동 실행은 새 `mock_db_mvp.launch.py`를 선택했을 때만 활성화된다.
- 기존 launch를 사용하면 DB 없는 기존 Mock 경로가 유지된다.
- `Farino_AIO/src/mock_db_mvp/`를 제거하면 bridge/DB 연동 코드가 사라지고 기존 동작으로 복귀한다.
- `004_mock_seed.sql`은 동일 Mock 기준정보의 반복 적용에 안전하지만 기존 슬롯 매핑이 다르면
  조용히 덮어쓰지 않고 실패한다.
- DB schema와 seed를 원복하려고 기존 객체나 DB를 삭제하지 않는다. 이번 시험 데이터는 격리
  `_test` DB에서 cleanup했고 임시 서버와 디렉터리도 제거했다. 이후 시험도 `_test`에서만 한다.
- `005_roles.sql`은 아직 적용되지 않았으므로 현재 DB 권한 상태에는 원복할 변경이 없다.
