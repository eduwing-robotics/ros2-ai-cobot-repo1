# Mock 우선 DB 연동 구현 계획

## 목표와 고정 경계

Unity가 PostgreSQL을 직접 수정하지 않고, 기존 Mock 조립의 실제 완료를 ROS2가 확인한 뒤
작업·완성품·재고·검사 결과를 기록하는 1대 조립 MVP를 시연한다.

- Unity는 DB 접속 문자열과 SQL을 갖지 않으며, 주입된 `IRobotScenarioControl.ExecuteAsync()`만 호출한다.
- Mock/Real 선택은 `RobotMaster` 한 곳에 유지한다.
- ROS2 조립 실행 프로세스가 `production` 쓰기를 소유한다.
- DataStation은 읽기 전용이다.
- Mock과 Real은 같은 스키마와 `production_store.py`를 사용하고 접속 문자열만 바꾼다.
- FR5 저수준 제어, 비전 노드, Unity에는 SQL을 넣지 않는다.
- 스텝 진행, 관절 상태와 TCP Pose는 DB에 저장하지 않는다.
- ORM, Repository 계층, 메시지 큐, 캐시와 범용 프레임워크는 만들지 않는다.

DB 연동은 다음 독립 패키지에 격리한다.

```text
Farino_AIO/src/mock_db_mvp/
├── CMakeLists.txt
├── package.xml
├── scripts/
│   ├── production_store.py
│   └── mock_db_bridge.py
├── launch/
│   └── mock_db_mvp.launch.py
└── test/
    └── test_production_store.py
```

기존 `Farino_AIO/notebooks/mock_sim.py`, 기존 launch, Unity C#, Scene과 Prefab은 수정하지
않는다. 위 디렉터리를 제거하고 기존 launch를 사용하면 DB 연동 전 동작으로 복귀한다.

## 현재 구현 파이프라인

```text
Unity Scenario
  -> IRobotScenarioControl.ExecuteAsync()
  -> mockAsyncPlay: /unity/assembly/start
  -> mock_db_bridge
       -> start_job(MOCK-SEMICONDUCTOR-ASSEMBLY, mock-v1, 1, mock-r1)
       -> start_next_unit(job_id)
       -> /mock_db_mvp/internal/assembly/start
  -> 기존 mock_sim.py: 25개 observation 조립
  -> /mock_db_mvp/internal/assembly/feedback
       -> STARTED/PICKED/PLACED는 그대로 중계
       -> COMPLETED 수신 시 재고 차감 -> Mock 검사 -> Job 종료
       -> 세 DB 작업이 모두 commit된 뒤에만 외부 COMPLETED 중계
  -> /unity/assembly/feedback
  -> PostgreSQL main_unity_mock

DataStation
  -> datastation_reader가 부여된 별도 LOGIN 계정
  -> PostgreSQL SELECT만 수행
```

각 쓰기 API는 자체 connection과 transaction을 갖는다. 따라서 조립 완료 및 재고 차감,
검사 확정, Job 종료는 각각 독립 commit이다. 중간 오류는 Unity에 `COMPLETED` 대신
`DB_ERROR/FAILED`로 전달하지만 앞에서 이미 성공한 transaction을 되돌리는 보상 처리는 이
MVP에 없다.

## 현재 상태

- [x] `main_unity_mock` 생성 및 `001_schema.sql` 적용
- [x] `004_mock_seed.sql` 작성 및 적용
- [x] `MOCK-SEMICONDUCTOR-ASSEMBLY`/`mock-v1`, 6 parts, 25 slots 저장
- [x] Seed 재실행 멱등성과 `buildable_quantity=10` 확인
- [x] `jobs/units/unit_defects=0`인 기준 상태 확인
- [x] `005_roles.sql` 최소 권한 정의 작성
- [x] psycopg3 기반 공용 업무 쿼리 구현
- [x] 독립 `mock_db_mvp` package/bridge/launch 구현
- [x] Mock 검사 기본 FAIL 20%와 launch 조정 구현
- [x] 기존 Unity 주입 및 서비스/feedback 경로 정적 확인
- [x] 안전 가드 이후 격리 `_test` DB에서 ProductionStore 통합 테스트 3건 통과
- [x] 격리 `_test` DB에서 role SQL과 writer/reader 권한 허용·거부 검증
- [x] bridge ROS graph 계약, 정상 종료, build/self-check/package 실행 정보 검증
- [ ] `005_roles.sql`을 관리자 권한으로 실제 DB에 적용하고 LOGIN 계정을 연결
- [ ] 반복 검증용 영구 `_test` DB 마련
- [ ] Unity 시작부터 DB 결과까지 전체 런타임 시연
- [ ] Real 로봇 연결

## 확정된 통신과 상태 정책

- 첫 시연은 기존 `/unity/assembly/start` 서비스와 `/unity/assembly/feedback` 토픽을 유지한다.
- launch remap으로 기존 Mock 노드에는 `/mock_db_mvp/internal/assembly/*`만 보인다.
- `job_id`는 bridge가 생성하고 Unity `request_id`는 런타임 상관관계에만 사용한다.
- bridge 입력은 기존 계약인 `request_id`, `recipe_version`, `observations`를 유지한다.
- 제품과 수량은 첫 시연 범위에서 `MOCK-SEMICONDUCTOR-ASSEMBLY`, `mock-v1`, 1대로 고정한다.
- `STARTED`, `PICKED`, `PLACED`는 진행 상태이고 `COMPLETED`, `FAILED`는 종결 상태다.
- 내부 `FAILED` 또는 DB 오류는 Job을 `FAILED`로 종료하고 외부에도 실패를 전달한다.
- Mock 검사는 기본 PASS 80%/FAIL 20%다. FAIL이면 제품 슬롯 1개와 `MISSING`,
  `POSITION_ERROR`, `ORIENTATION_ERROR`, `CRACK` 중 하나를 선택한다.
- 검사 `FAIL`은 실행 실패가 아니다. 조립과 검사가 정상 종료된 Unit/Job은 `COMPLETED`이고,
  `inspection_result=FAIL`과 defect 1건으로 품질 불량을 표현한다.
- `inspection_fail_probability=0` 또는 `1`과 `random_seed`로 시연을 재현한다.
- bridge 시작 시 active DB Job이 있으면 저장되지 않은 Unity `request_id`를 복구할 수 없으므로
  외부 endpoint를 열기 전에 fail-fast한다.

정식 ROS2 Action, 취소 의미, 다수량 입력은 첫 시연 이후에 결정한다.

## 구현된 ProductionStore API

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

구현 규칙:

- `PRODUCTION_DB_DSN`이 없거나 비어 있으면 연결을 시도하지 않고 실패한다.
- 모든 값은 `%s` parameter로 전달하고 write마다 connection/transaction을 닫는다.
- 재고, Job과 Unit 갱신 전 `FOR UPDATE`로 경합 대상을 잠근다.
- 요청 수량 전체의 재고가 부족하면 Job INSERT 자체가 rollback된다.
- `start_next_unit()`은 실행 중 Unit 및 요청 수량을 초과하는 sequence를 거부한다.
- 한 Unit의 조립 완료 시 6종의 슬롯별 사용량 차감과 `assembly_completed_at`을 한 번에 commit한다.
- 동일 조립 완료 callback은 재고를 다시 차감하지 않는다.
- PASS는 defect 0개, FAIL은 1개 이상만 허용한다.
- defect 슬롯은 해당 Unit 제품에 속해야 한다.
- 동일한 검사 callback은 Job 종료 후에도 no-op이고, 다른 검사 데이터 재수신은 거부한다.
- `COMPLETED` Job은 완료 Unit 수가 요청 수량과 같고 FAILED/RUNNING Unit이 없어야 한다.
- 현재 schema에 실패 사유 column이 없으므로 실패 사유 저장 인자는 제공하지 않는다.

## 검증 상태

완료:

- `001_schema.sql`과 `004_mock_seed.sql`을 `main_unity_mock`에 적용했다.
- 현재 조회값은 6 parts, 25 slots, `buildable_quantity=10`, 실행 테이블 0건이다.
- ProductionStore의 정상 완료/중복 완료, 검사 규칙/타제품 슬롯, 부족 재고 rollback 통합
  테스트 3건은 안전 가드 이후 격리 `main_unity_mock_test`에서 `OK`로 통과했다(0.343초).
- 테스트 종료 후 임시 기준정보와 생산 데이터 cleanup이 `0|0|0`임을 확인했다.
- 같은 격리 DB에 `005_roles.sql`을 적용하고 권한 매트릭스 `t|t|t|f|f|t|t|f`를 확인했다.
  writer 허용 작업과 reader SELECT는 성공했고 writer의 `product_name` UPDATE와 reader의
  `jobs` INSERT는 거부됐다.
- 격리 PostgreSQL 서버와 임시 디렉터리는 검증 후 종료·삭제했다.
- 최종 build, bridge `--self-check`, package executable 조회와 launch `--show-args`가 통과했다.
- bridge 단독 ROS graph에서 외부 service server/publisher와 내부 client/subscriber의 type
  계약을 확인했고, Ctrl-C 종료 코드는 0이며 traceback은 없었다.

남음:

- 반복 검증에 계속 사용할 영구 `_test` DB는 아직 없다.
- `production_writer`, `datastation_reader`는 실제 `main_unity_mock`에는 아직 적용되지 않았다.
- bridge ROS graph는 검증했지만 Unity를 포함한 전체 시연은 아직 수행하지 않았다.
- 재고 변경과 Unity GUI 실행을 피하기 위해 full launch와 Unity GUI 시연은 의도적으로 실행하지 않았다.

## 다음 작업 순서

### 1. 반복 검증용 테스트 DB

- [x] 격리 임시 `main_unity_mock_test` 생성 및 `001_schema.sql` 적용
- [x] 안전 가드가 포함된 통합 테스트 3건 실행 및 cleanup 확인
- [x] 임시 PostgreSQL 서버와 디렉터리 종료·삭제
- [ ] 동일 검증을 반복할 영구 `_test` DB 마련

테스트는 기준정보를 임시 INSERT/DELETE하므로 제한된 runtime writer 계정이 아니라 테스트 DB
owner로 실행한다.

### 2. 실제 권한 적용

- [x] 격리 임시 DB에 `005_roles.sql` 적용 및 권한 매트릭스 확인
- [x] writer/reader 허용 연산과 금지 연산 실제 확인
- [ ] 관리자가 실제 `main_unity_mock`에 role SQL을 적용하고 deployment LOGIN 연결 및
  `PRODUCTION_DB_DSN` 설정

Unity용 DB 계정은 만들지 않는다.

### 3. Mock 전체 시연

- [ ] `inspection_fail_probability:=0`으로 PASS 경로를 실행한다.
- [ ] Unity의 25개 PICKED/PLACED와 최종 COMPLETED를 확인한다.
- [ ] Job/Unit/검사와 부품별 정확한 재고 감소를 조회한다.
- [ ] `inspection_fail_probability:=1`로 FAIL 검사 저장을 확인한다.
- [ ] DB 오류 시 외부 COMPLETED가 전달되지 않는지 확인한다.
- [ ] 기존 launch는 DB 없이 동일하게 동작하는지 확인한다.

### 4. 시연 후 분기점

- [ ] 장시간 실행, 취소와 Real 연결 전에 서비스+토픽을 ROS2 Action으로 바꿀지 결정한다.
- [ ] Real에서는 같은 ProductionStore를 재사용하고 Mock 전용 random 검사를 실제 비전 결과로 대체한다.
- [ ] 재시작 후 중복 요청을 막아야 할 때 DB에 `request_id` UNIQUE 키와 복구 정책을 추가한다.
- [ ] 실패 Unit을 동일 Job에서 다시 만들지, Job 전체를 실패시킬지 정책을 정한 뒤 sequence 규칙을 바꾼다.
- [ ] Unity+Mock 시연 이후 별도로 실제 FR5와 비전까지 포함한 Real 시연을 수행한다.

현재 `request_id`는 메모리에만 있으므로 bridge 재시작 후 같은 요청의 멱등성은 보장하지 않는다.
또한 실패 Unit 재시도는 현재 MVP에서 제외되어 수량 1의 Unit 실패는 Job 실패로 종료한다.

## 이번 MVP에서 만들지 않는 것

- Real 로봇용 DB 코드 복사본 또는 Mock 전용 테이블/쿼리
- Unity PostgreSQL 드라이버, DB 계정 또는 DataStation 쓰기 API
- 스텝 이벤트, 관절/TCP Pose 저장
- ORM, Repository/Service 계층, 메시지 큐, outbox, 캐시, 자동 재시도 프레임워크
- 여러 작업 동시 실행과 재고 예약
- HTTP 작업 생성 API
- 기존 `mock_sim.py`, 기존 launch, Unity C#/Scene/Prefab 수정

## 사용자 결정 기록

| 항목 | 선택 | 상태 |
|---|---|---|
| Mock 첫 시연 통신 | 기존 서비스+토픽 유지 | 구현 완료, Action은 시연 후 |
| Job 생성 | bridge가 생성, Unity `request_id`는 상관관계 전용 | 구현 완료 |
| 첫 제품과 수량 | `MOCK-SEMICONDUCTOR-ASSEMBLY`/`mock-v1`, 1대 고정 | 구현 완료 |
| Mock 검사 | 기본 FAIL 20%, launch에서 0~1 및 seed 조정 | 구현 완료 |
| PostgreSQL 드라이버 | 기존 `psycopg 3.1.17` 직접 사용 | 구현 완료 |
| 실패 사유 | schema 변경 없이 저장하지 않음 | MVP 확정 |
| 재시작 멱등성/실패 Unit 재시도 | 현재 MVP 제외 | 후속 결정 |
