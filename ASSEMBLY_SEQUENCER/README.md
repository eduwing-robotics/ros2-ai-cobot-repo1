# Assembly Sequencer

생산 Job을 실제 Mock/Real 조립·검사 흐름으로 조정하는 업무 계층입니다.

## 역할과 책임

- 실행 가능한 Job 선택과 단일 실행 보장
- Unit 생성과 Job·Unit 상태 전이
- 실행 시작 전 레시피 검증과 고정
- 조립, 이송, 검사 순서 조정
- backend 완료·실패·timeout 전달
- 생산 결과, 검사와 재고 기록

Unity UI, HTTP 요청 수신, 좌표 변환, Raw ROS 메시지와 하드웨어 저수준 제어는 소유하지 않습니다.

## 실행 모델

MainServer는 `PENDING` Job을 등록하고 Sequencer가 하나를 선택해 실행합니다. Sequencer는 Job마다 한 Unit만 실행하며, 레시피 순서를 위에서 아래로 조정합니다.

각 단계에서는 로봇·비전·컨베이어 backend의 의미 단위 공개 동작만 호출합니다. 통신, 좌표 변환, 재시도, timeout과 실제 완료 판정은 해당 backend가 완결합니다.

## Job과 Unit

요청 수량은 검사 PASS 목표입니다. 검사 FAIL은 정상적으로 끝난 생산 시도로 보존하고 같은 Job에서 다음 Unit을 시작합니다. 설비 동작 실패는 Unit `FAILED`로 기록합니다.

PASS 누적이 목표 수량에 도달한 뒤에만 Job을 완료합니다.

## 레시피

레시피는 조립 순서와 `part_id`·`slot_code`의 의미를 소유합니다. 시작 시 검증한 snapshot만 실행하며, DB에 레시피 본문이나 단계 checkpoint를 복제하지 않습니다.

현재 파일 형식의 기준은 실제 YAML과 parser입니다. 과거 확장 설계안은 `docs/archive/`에 보관하며 실행 계약으로 사용하지 않습니다.

## 재시작과 안전

재시작 시 실행 중이던 Unit은 실패로 마감하지만 Job은 유지합니다. 설비 준비와 reset을 확인한 뒤 새 Unit으로 레시피 처음부터 실행합니다.

안전정지 중에는 Job과 Unit을 `RUNNING`으로 유지하고 신규 동작을 차단합니다. DB 지연이나 실패가 설비 정지와 정리를 방해해서는 안 됩니다.

## 문서

- [공개 API 계약](API.md)
- [계층 간 통합 계약](../docs/API.md)
- [생산 데이터 설계](../DATA_STATION/DB/README.md)
