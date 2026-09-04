# MainServer

외부 클라이언트와 production 데이터 사이의 요청·조회 경계입니다.

## 역할

- 외부 입력과 업무 식별자 검증
- 제품, 재고, Job, Unit과 품질 결과 조회
- 호출자가 만든 UUID `job_id`로 `PENDING` Job 등록
- 확정된 생산·검사 사실을 이용한 품질 문서 생성과 전송 상태 관리

Job·Unit 실행 상태 전이, 조립 순서, 좌표 해석과 설비 제어는 소유하지 않습니다.

## 경계

`production.jobs`가 영속 생산 요청의 유일한 진입점입니다. 같은 `job_id`와 같은 내용의 재요청은 기존 Job을 반환하고 다른 내용은 거절합니다.

Job 등록 성공은 실행 시작이나 완료가 아닙니다. MainServer 조회 실패도 실행 중인 설비나 저장된 production 상태를 변경하지 않습니다.

품질 문서는 확정된 불량 사실로 생성하며 작업자 회신을 보호하기 위해 기존 파일을 덮어쓰지 않습니다. 문서 전송 실패는 확정된 Unit과 검사 결과를 바꾸지 않습니다.

## 공개 진입점

HTTP endpoint, payload와 오류는 [MainServer HTTP API](Main_serverAPI.md)가 소유합니다. Mock 전체 실행과 환경 구성의 단일 기준은 [Mock 올인원 실행](../Farino_AIO_Mock/README.md#mock-올인원-실행)입니다.

## 관련 설계

- [시스템 아키텍처](../docs/architecture/index.md)
- [production 데이터 설계](../DATA_STATION/DB/README.md)
- [불량대책서 필드 계약](templates/불량대책서_필드매핑.md)
