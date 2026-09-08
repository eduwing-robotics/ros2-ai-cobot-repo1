# Assembly Sequencer

production Job을 조립·검사 실행으로 조정하는 업무 계층입니다.

## 역할

- 실행 가능한 Job 선택과 단일 실행 보장
- Unit 생성과 Job·Unit 상태 전이
- 시작 시 레시피 검증과 실행 중 snapshot 고정
- 조립, 이송과 검사 순서 조정
- backend 완료·실패·timeout 전달
- 생산 결과, 검사와 재고 기록

Unity UI, HTTP 요청 수신, 좌표 변환, Raw ROS 메시지와 하드웨어 저수준 제어는 소유하지 않습니다.

## 실행 경계

Sequencer는 레시피 순서에 따라 backend의 의미 단위 공개 동작만 호출합니다. 통신, 좌표 변환, timeout과 실제 완료 판정은 backend가 완결합니다.

Job·Unit, 수량, 검사 FAIL, 재시작과 안전정지의 공통 의미는 [시스템 아키텍처](../docs/architecture/index.md)가 소유합니다.

## 공개 API

외부 ROS 경계는 공통 service와 feedback topic이며 실행 모드별 domain을 사용합니다. 구체 endpoint와 payload는 [Assembly Sequencer ROS API](API.md)를 따릅니다.

`sequencer_node.py`가 공통 YAML·Job·Unit 흐름을, `recipe_contract.py`가 입력 검증을 소유합니다.
`mock_backend.py`는 Mock 동작 완료와 Unity 컨베이어 신호 대기·난수 검사를 소유합니다.
`real_backend.py`는 Real 상태 조회·실행 준비 거절과 Vision 검사 경계를 소유합니다.
Real의 실제 이동·그리퍼·컨베이어·reset·좌표 공급은 아직 연결되지 않아 실행 요청은
Job claim 전에 `NOT_READY`로 실패합니다. Mock으로 자동 대체하지 않습니다.

Mock 전체 스택의 유일한 실행 진입점은 [Mock 올인원 실행](../Farino_AIO_Mock/README.md#mock-올인원-실행)입니다.

## 관련 설계

- [공개 API 목록](../docs/API.md)
- [production 데이터 설계](../DATA_STATION/DB/README.md)


## 검사 자료 저장 경계

검사 저장은 Unit 실행 완료가 아닙니다. 전체 workflow 성공 뒤 `DbWriter.unit_completed(unit_id)`를 기록하고 `flush()`를 확인한 후 다음 Unit 또는 Job 완료로 진행합니다. 실패 시 이미 저장된 검사 자료는 유지합니다.


`real_backend.inspect()`는 Vision의 완료 JSON과 검증된 PNG를
`{"data": dict, "image_bytes": bytes | None}`로 반환하는 동기 함수입니다.
공통 runner에서 사용하는 `RealBackend.inspect_unit()`은 별도 worker에서 이를 호출합니다.
같은 Job·Unit에서 같은 검사 UUID를 사용하며 ROS callback을 HTTP 대기로 막지 않습니다.
실제 Real 전체 흐름은 실행 준비 경계에서 차단되어 아직 검사 단계에 도달하지 않습니다.

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
