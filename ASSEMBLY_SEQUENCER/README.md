# Assembly Sequencer

production Job을 조립·검사 실행으로 조정하는 업무 계층입니다.

## 역할

- 실행 가능한 Job 선택과 단일 실행 보장
- Unit 생성과 Job·Unit 상태 전이
- Mock 시작 시 YAML 레시피 검증과 실행 중 snapshot 고정
- 조립, 이송과 검사 순서 조정
- backend 완료·실패·timeout 전달
- 생산 결과, 검사와 재고 기록

Unity UI, HTTP 요청 수신, 좌표 변환, Raw ROS 메시지와 하드웨어 저수준 제어는 소유하지 않습니다.

## 실행 경계

Sequencer는 생산 공정을 조정하고 로봇 실행기는 조립 내부 순서를 소유합니다.
Real은 YAML을 읽거나 개별 MoveJoint·Pick·Place를 실행하지 않습니다.
공정 책임은 **컨베이어 조립 위치 이동 → 로봇 전체 Start → 컨베이어 검사 위치 이동 → 검사**입니다.
로봇의 준비 촬영·계획 생성·Pick/Place는 전체 Start 내부 책임이며, 외부 단계로 재실행하지 않습니다.
검사 후 로봇 PCB 이송·배출은 이 공정의 필수 조건이 아닙니다.
Real은 새 현장 확인을 포함한 명시적 `start`에서 준비 상태와 생산 슬롯을 검증한 뒤 Job을 claim하고
네 단계를 순서대로 실행합니다. 준비 실패는 claim 전에 `NOT_READY`로 반환합니다.
PENDING Job만으로 자동 기동하지 않으며, 다음 Unit에도 새 실행 ID와 현장 확인이 필요합니다.
Mock은 기존 YAML 실행 경로를 사용하며, 통신·timeout·실제 완료 판정은 backend가 완결합니다.

Job·Unit, 수량, 검사 FAIL, 재시작과 안전정지의 공통 의미는 [시스템 아키텍처](../docs/architecture/index.md)가 소유합니다.

## 공개 API

외부 ROS 경계는 공통 service와 feedback topic이며 실행 모드별 domain을 사용합니다. 구체 endpoint와 payload는 [Assembly Sequencer ROS API](API.md)를 따릅니다.

`sequencer_node.py`는 Job·Unit 흐름과 Mock YAML 실행을, `recipe_contract.py`는
공통 요청·상태 검증과 Mock 레시피 검증을 소유합니다.
`mock_backend.py`는 Mock 동작 완료와 Unity 컨베이어 신호 대기·난수 검사를 소유합니다.
Mock YAML의 `before_all`·`per_step`·`after_all`은 필수 동작과 순서까지 검증합니다.
Mock 컨베이어 피드백은 이동마다 Job·Unit·이동 UUID를 대조합니다.
Real 컨베이어는 수락된 motion_id와 서버 instance·도착 상태를 대조합니다. 외부에서 이미 완료된 이동을 현재 Job·Unit에 연결하거나 재사용하는 기능은 없습니다.

`real_backend.py`는 `/real/robot/status`와 `/real/assembly/status`의 생산 v2 capability를
조회하고 컨베이어 이동·도착 대기, 로봇 전체 Start와 Vision HTTP 검사 경계를 소유합니다.
Sequencer가 `execute_assembly()`를 호출하면 단일 Start를 발행하고 실행 식별자가 일치하는
진행·전체 완료·실패를 기다립니다.
요청을 `DEFECT_IMAGE_ROOT/executions/<unit_id>/request.json`에 발행 전에 저장하고,
소비한 callback snapshot을 `events.jsonl`에 남깁니다. 이 로그는 모든 원격 event의 무손실 보관을 보장하지 않습니다.
전체 완료는 25개 슬롯 집합·생산 식별자·정지·복구 해제·non-SMD/SMD 계획 해시를 검증합니다.
수락·개별 동작 완료는 전체 완료가 아니며, event 없는 거절과 서버 변경도 처리합니다.
1800초 전체 완료 timeout 또는 전송 후 불명확한 결과는 `SAFETY_STOP`으로 전달합니다.
로봇 개별 동작 publisher, 동작별 재전송, 취소형 Pause 연결과 로컬 파지 상태는 없습니다.
생산 v2 Pause/Resume/Cancel은 로봇 조립 중 연결되어 있습니다. 일시정지는 전달된 동작 종료 후 확인하며, 제어 ID와 실제 상태를 대조합니다. 취소를 상태 보존형 일시정지로 표현하지 않습니다.
Unity의 실측·Ghost·부품 이벤트 수신과 수동 로봇 조작은 이 제거 범위에 포함되지 않습니다.

### Runner의 SDK·저수준 제어 금지

Real runner와 Real backend는 로봇 SDK, 드라이버 서비스, 직접 IO, 장비 소켓 또는
외부 프로세스를 통한 저수준 제어를 사용하지 않습니다. TCP·IK·그리퍼 세부 동작은
로봇 PC가 소유합니다. Sequencer는 기존 장비 공개 API의 의미 단위 완료만 기다립니다.
API 부재·실패·timeout 시 직접 제어로 우회하지 않고 실행을 거절하거나 보류합니다.
기존 Mock 내부 서비스는 이 Real 장비 제어 경로와 별개입니다.
기존 테스트에서 Real backend의 import·ROS endpoint 허용 목록과 저수준 호출 부재를 검사합니다.
이는 코드 회귀 검사이며 운영체제 수준의 네트워크 접근 차단을 뜻하지 않습니다.

Mock 전체 스택의 유일한 실행 진입점은 [Mock 올인원 실행](../Farino_AIO_Mock/README.md#mock-올인원-실행)입니다.

## Real 연결 설정

기존 Real 프로세스에서 `VISION_BASE_URL` 환경 변수 또는 `vision_base_url` ROS 파라미터로
검사 HTTP origin을 지정합니다. `KSMC_VISION_API_TOKEN`은 서버 프로세스 환경에만 제공하고
Unity·로그·Git에 포함하지 않습니다. `DEFECT_IMAGE_ROOT`는 실행 원문과 검사 자료를 보존할
공유 저장소입니다. 설정이 없거나 잘못되면 준비 검증을 통과하지 못합니다.
생산 DB에는 제품·버전·25개 슬롯과 실제 재고가 준비되어 있어야 합니다. 테스트 성공 기록에서
재고를 추정하거나 생성하지 않습니다. `fr5_interlock_required=false`는 제공 서버의 미사용 계약을
따르며, true일 때만 FR5 clear와 freshness를 요구합니다. 누락·잘못된 형식은 준비 실패입니다.

## 관련 설계

- [공개 API 목록](../docs/API.md)
- [production 데이터 설계](../DATA_STATION/DB/README.md)


## 검사 자료 저장 경계

검사 저장은 Unit 실행 완료가 아닙니다. 전체 workflow 성공 뒤 `DbWriter.unit_completed(unit_id)`를 기록하고 `flush()`를 확인한 후 다음 Unit 또는 Job 완료로 진행합니다. 실패 시 이미 저장된 검사 자료는 유지합니다.


`real_backend.inspect()`는 Vision의 완료 JSON과 검증된 PNG를
`{"data": dict, "image_bytes": bytes | None}`로 반환하는 동기 함수입니다.
`RealBackend.inspect_unit()`은 별도 worker에서 이를 호출합니다.
같은 Job·Unit에서 같은 검사 UUID를 사용하며 ROS callback을 HTTP 대기로 막지 않습니다.
전체 조립 완료 기록과 검사 위치 도착을 확인한 뒤 호출합니다.

기존 `DbWriter.inspection_recorded(unit_id, result, defects, image_path=None)`는
선택적 `inspection`, `image_bytes` 키워드 인자로 Vision 자료를 받을 수 있습니다.
이 경우 `result`는 원본 decision, `defects=None`, `image_path=None`으로 전달합니다.
`flush()`가 성공해야 저장 완료이며, 하위 `production_store.record_inspection()`의
동기 반환값은 `slot_code`와 `unit_defect_id`의 매핑 목록입니다.
생산 lifecycle은 고정된 프로세스 모드와 같은 DB만 사용하며 Vision 자료 저장은 Real 프로세스·DB만 허용합니다.

Unit당 재검사는 허용하지 않습니다. 같은 내용은 기존 UID를 복구하고 다른 내용은 거절합니다.
모든 제품 슬롯을 검사 JSON과 대조하고, 확정 불량 없는 슬롯은 `defect_type=NULL`로 저장합니다.
`UNKNOWN`은 Unit을 RUNNING으로 보류하고 발행 대기를 만들지 않습니다.
제품 슬롯 수는 DB 구성과 정확히 일치해야 하며 누락된 검사 상세를 만들어 넣지 않습니다.

`DEFECT_IMAGE_ROOT` 아래 `inspections/<unit_id>/response.json`에 원본 응답,
`result.json`에 원본 `data`와 `unit_defects` UID 매핑, `02_annotated_report.png`에 이미지를 보관합니다.
파일은 DB commit보다 먼저 준비하며 조회자는 UID를 DB와 대조합니다.
DB rollback 뒤 파일은 삭제하지 않고 같은 요청으로 복구합니다.
파일 보관과 데이터베이스를 함께 백업해야 기존 결과 비교와 UID 연결을 보존할 수 있습니다.

확정 코드 `COMPONENT_MISSING`은 `MISSING`, `DIRECTION_ERROR`는 `ORIENTATION_ERROR`로 대응합니다.
`SEATING_ERROR`, `UNCLASSIFIED_ANOMALY`는 같은 이름으로 저장합니다.
원본 코드는 JSON에 유지하며 미지원 코드·한 슬롯의 여러 확정 유형은 자동 축약하지 않고 거절합니다.
이미지 미준비 FAIL은 결과를 보존하지만 대책서 발행 대기는 생성하지 않습니다.
