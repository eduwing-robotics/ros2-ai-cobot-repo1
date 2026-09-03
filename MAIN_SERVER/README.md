# MAIN_SERVER

외부 클라이언트와 생산 데이터 사이의 HTTP 요청 경계입니다.

## 역할과 책임

- 외부 입력과 업무 식별자 검증
- 제품, 재고, Job, Unit과 품질 결과 조회
- 클라이언트가 만든 UUID `job_id`로 `PENDING` Job 등록
- 저장된 생산·검사 사실을 이용한 품질 문서 생성

Job·Unit 실행 상태 전이, 조립 순서, 좌표 해석과 로봇 직접 제어는 소유하지 않습니다.

## Job 등록 원칙

`production.jobs`가 유일한 영속 생산 요청 진입점입니다. 같은 `job_id`와 같은 내용의 재요청은 기존 Job을 반환하고, 다른 내용은 거절합니다.

Job 등록 성공은 실행 시작이나 생산 완료가 아닙니다. 실행 상태와 결과는 Assembly Sequencer가 소유하며 MainServer의 조회 경로는 상태를 변경하지 않습니다.

## 조회 경계

MainServer는 production 데이터를 읽어 사용자에게 필요한 업무 단위로 제공합니다. Unity 오브젝트, 설비 좌표와 ROS 메시지 의미를 해석하지 않습니다.

현재 실행 snapshot을 조회할 수 있지만 조회 실패가 설비 동작이나 저장된 생산 상태를 바꾸어서는 안 됩니다.

## 품질 문서

불량대책서는 FAIL 검사에서 확정된 불량 한 건마다 즉시 생성합니다. Sequencer가 불량과
전송 대기를 같은 DB 트랜잭션에 기록하고, MainServer worker가 양식을 생성해 이메일에
첨부합니다. 기존 문서는 작업자 회신을 보호하기 위해 덮어쓰지 않습니다.

`production.parts`는 Part ID·이름·범주·재고를 소유합니다. 사양·공급사·가격과 검사
기준은 부품 데이터시트에서 정확한 범주·MPN 매칭으로 가져옵니다. 검사 이미지가 있으면
허용된 루트 아래의 JPEG·PNG만 문서에 포함하며 이미지 오류는 문서 발행을 막지 않습니다.

이메일은 SSL 또는 STARTTLS만 허용하고, 수신자 도메인 allowlist와 권한 `0600`인 비밀
파일을 사용합니다. 비밀번호는 환경 변수나 저장소에 넣지 않습니다. 전체 실행 변수와
검증 절차는 [Mock 올인원 실행](../Farino_AIO_Mock/README.md#mock-올인원-실행)을 따릅니다.

## 문서

- [HTTP API 계약](Main_serverAPI.md)
- [시스템 아키텍처](../docs/architecture/index.md)
- [생산 데이터 설계](../DATA_STATION/DB/README.md)
- [불량대책서 필드 계약](templates/불량대책서_필드매핑.md)
