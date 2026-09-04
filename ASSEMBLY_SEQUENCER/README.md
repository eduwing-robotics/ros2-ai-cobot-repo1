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

현재 구현된 외부 ROS 경계는 Mock service와 feedback topic입니다. 구체 endpoint와 payload는 [Assembly Sequencer ROS API](API.md)를 따릅니다.

Real 자동 조립 API는 구현되어 있지 않으며 미구현 이름을 예약하지 않습니다. 구현이 추가될 때 코드·IDL과 API 문서를 같은 변경에서 갱신합니다.

Mock 전체 스택의 유일한 실행 진입점은 [Mock 올인원 실행](../Farino_AIO_Mock/README.md#mock-올인원-실행)입니다.

## 관련 설계

- [공개 API 목록](../docs/API.md)
- [production 데이터 설계](../DATA_STATION/DB/README.md)
