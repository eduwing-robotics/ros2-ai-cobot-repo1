# 0831 AssemblySequencer · MainServer 복잡도 리팩터링 보고서

## 기준과 롤백 지점

- 작업일: 2026-08-31
- 작업 전 체크포인트 커밋: `02fef16efe7786560fffdf318bc1c51b658d8c98`
- Annotated tag: `ROLLBACK831`
- 리팩터링 커밋: `57e858a` (`refactor: deepen assembly component boundaries`)
- `ROLLBACK831`은 작업 전 존재하던 `.gitignore` 변경과 241개 파일의 대규모 삭제까지 포함한 당시 작업 트리를 먼저 커밋한 지점이다. 리팩터링 변경과 기존 변경을 섞지 않았다.

## 평가 기준

John Ousterhout의 deep module 원칙에 따라 오케스트레이터가 JSON·ROS·timeout·상태 검증 세부사항을 알지 않도록 하고, 각 컴포넌트의 작은 API 안에서 복잡성을 완결했다. Martin Fowler의 책임별 Extract Class/Function 관점은 실제로 변경 이유와 실패 원인이 다른 경계에만 적용하고, 테스트 가능한 작은 단계로 동작을 보존했다.

MainServer `ApiHandler`는 307줄이지만 HTTP routing·입력 경계라는 하나의 책임을 가지며 endpoint 대부분이 이미 `queries`, `datasheet`, `AssemblyGateway`로 위임된다. endpoint별 클래스를 추가하면 얕은 모듈과 이동 비용만 늘어나므로 분할하지 않았다.

## 복잡도 평가

AST 분기 점수는 `1 + if/loop/except/bool branch`로 계산한 비교용 값이며 외부 표준 도구 점수는 아니다.

| 대상 | ROLLBACK831 | 변경 후 | 평가 |
| --- | ---: | ---: | --- |
| `mock_node.py` 파일 길이 | 603줄 | 342줄 | ROS wiring과 업무 순서 중심으로 축소 |
| `poll_queue()` | 80줄 / 분기 15 | 52줄 / 분기 12 | claim → 검증 → backend 시작 흐름이 위에서 아래로 보임 |
| `on_internal_feedback()` | 109줄 / 분기 15 | 56줄 / 분기 11 | 계약 검증·상태 전이·실패 마감을 하위 API로 이동 |
| 활성 작업 실패 마감 구현 | 여러 경로에 반복 | `fail_active()` 1곳 | DB 마감·terminal snapshot·로그·발행을 한 경계에서 처리 |
| MainServer `_serve()` | 21줄 / 분기 8 | 21줄 / 분기 8 | 이미 적절한 오케스트레이션이므로 유지 |
| Mock runtime 총 길이 | 603줄 | 667줄 | 엄격한 feedback 검증과 ROS 응답 timeout 64줄이 순증; 단순 파일 이동으로 수치를 숨기지 않음 |

## 최종 구조와 API

```text
MainServer ApiHandler
  ├─ POST /assemblies ──→ queries.enqueue_assembly()
  └─ GET /assemblies/current ──→ AssemblyGateway.status()

MockAssemblySequencer
  ├─ mock_contract.parse_command()/parse_feedback()
  ├─ DbWriter.claim()/assembly_completed()/inspection_recorded()/finish()
  └─ MockBackend.status()/start()/transfer_assembled_pcb()
```

- `MockBackend`가 내부 ROS Service 발견, 요청 JSON 생성, 응답 형식·거절 검증, 5초 응답 timeout과 `None` 응답 실패를 완결한다.
- `mock_contract`가 UUID, feedback 상태, 필수 필드, 타입, Pick/Place 단계 정보를 검증하고 snapshot 및 상태 전이를 담당한다.
- 오케스트레이터는 command claim, 시작, 완성 PCB 이송, 검사, 완료·실패 순서만 표현한다.
- MainServer는 raw JSON `call()`을 공개하지 않고 `AssemblyGateway.status()`만 사용한다.
- HTTP route, ROS topic/service 이름, 메시지 JSON 필드, DB schema와 Unity 공개 계약은 변경하지 않았다.

## 파일 변경

### 생성

- `ASSEMBLY_SEQUENCER/src/assembly_sequencer/assembly_sequencer/mock_contract.py`
  - Mock command·feedback 검증, 상태 전이, snapshot, inspection 선택과 self-check
- `ASSEMBLY_SEQUENCER/src/assembly_sequencer/assembly_sequencer/mock_backend.py`
  - 내부 Mock ROS Service의 `status`, `start`, `transfer_assembled_pcb` API와 통신 안전 처리
- `0831.md`
  - 본 변경·평가·검증 보고서

### 수정

- `ASSEMBLY_SEQUENCER/src/assembly_sequencer/assembly_sequencer/mock_node.py`
  - 계약·ROS 세부 구현을 컴포넌트로 이동하고 오케스트레이션 및 공통 실패 마감 중심으로 정리
- `ASSEMBLY_SEQUENCER/README.md`
  - Mock orchestration, contract, backend 책임 표 갱신
- `MAIN_SERVER/assembly_gateway.py`
  - 직관적인 `status()` API 추가, raw 호출은 `_call()`로 비공개화
- `MAIN_SERVER/server.py`
  - 현재 조립 조회에서 `AssemblyGateway.status()` 사용
- `MAIN_SERVER/test_server.py`
  - Fake gateway를 새 API에 맞추고 호출자 없는 `start_response`·raw `call()` 제거

### 삭제·기타

- 리팩터링 과정에서 삭제한 파일과 폴더 없음
- 신규 폴더, 외부 의존성, 인터페이스, 팩토리, 설정 파일, 테스트 파일, Unity Asset·`.meta` 생성 없음
- Unity MCP Test Runner가 일시 변경한 `UnityDT/ProjectSettings/EditorSettings.asset`은 원래 값으로 복원해 최종 diff에서 제외함

## SLOP 점검

- 제거: 새 `status()` API 뒤 호출자가 없어진 `FakeGateway.start_response`와 raw `call()`
- 축소: 실제 gateway raw `call()`을 `_call()`로 비공개화
- 통합: 서비스 발견과 응답 timeout의 동일한 5초 값을 `SERVICE_TIMEOUT_SECONDS` 한 곳에서 소유
- 보류하지 않은 항목: 입력 검증, DB 실패 마감, timeout, terminal 오류 전달과 로그는 안전 경계이므로 축소 대상에서 제외
- 최종 판정: 추가로 삭제 가능한 speculative abstraction·dead flexibility·신규 dependency 없음 (`Lean already. Ship.`)

## 검증 결과

| 검증 | 결과 |
| --- | --- |
| 변경 Python `py_compile` | 통과 |
| Mock contract self-check | 통과 |
| Mock backend 정상 응답·timeout self-check | 통과 |
| DbWriter FIFO·retry·overflow 단위 테스트 | 2/2 통과 |
| ProductionStore 로컬 test DB 통합 테스트 | 6/6 통과 |
| MainServer API·DB 통합 테스트 | 7/7 통과 |
| `colcon build --symlink-install` | `assembly_sequencer` 패키지 통과 |
| 빌드된 `ros2 run assembly_sequencer mock_node --self-check` | 통과 |
| `git diff --check` | 통과 |

### Unity MCP

- 연결 인스턴스: `UnityDT@9f95204a`, Unity `6000.3.21f1`, LinuxEditor
- 최종 Editor 상태: idle, Play Mode 종료, compilation 및 domain reload 대기 없음, tools ready
- EditMode·PlayMode Test Runner job: 모두 `succeeded`, `resultState=Passed`
- 프로젝트에 발견된 실제 테스트 case는 두 mode 모두 0개이므로 Unity 기능 테스트 coverage로 과장하지 않는다.
- 검증 전 Console에 이전 Mock 비활성화 E2E 기록 2건이 있었고 이번 Python 변경과 무관함을 확인했다. 기준선을 분리해 Console을 비운 뒤 Test Runner 종료 후 error/warning 0건을 확인했다.

## 남은 위험

- Unity → MainServer → PostgreSQL → ROS2 Mock backend 전체 프로세스를 동시에 띄운 live E2E는 실행하지 않았다. 로컬 DB 통합 테스트와 ROS2 빌드·entrypoint 검증 범위까지 완료했다.
- 내부 Mock Service timeout 분기는 fake Future self-check와 ROS2 빌드로 검증했으며 실제 응답 지연을 주입한 live ROS2 테스트는 수행하지 않았다.
- Real AssemblySequencer backend는 기존 문서와 동일하게 미구현 범위다.
