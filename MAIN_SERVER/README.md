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


## 검사 자료 보관 조회

MainServer는 `DEFECT_IMAGE_ROOT`의 Unit별 `result.json`을 DB UID와 대조하고
검사 조회 응답에 슬롯·findings를 제공합니다. PNG는 같은 보관 루트의 파일을
크기·SHA256 검증 후 HTTP로 제공합니다. SQL에는 파일 본문을 저장하지 않습니다.
대책서 생성기는 동일 자료를 읽고 확정 불량의 UID·이미지를 검증합니다.
자료 누락·불일치는 생산 판정이나 파일을 수정하지 않고 조회·생성 실패로 전달합니다.


## 로컬 대책서

기존 `generate_defect_reports.py`는 기본 `local` 모드로 확정 불량 XLSX를 생성합니다.
같은 문서가 있으면 보존하며 로컬 생성은 발송 대기 기록을 claim하거나 SENT로 바꾸지 않습니다.
품질 화면은 MainServer에서 제품·슬롯별 문서 준비 여부를 조회하고 XLSX를 내려받습니다.
Unity 다운로드는 `Application.persistentDataPath/DefectReports`에 저장하며 기존 파일을 덮어쓰지 않습니다.
이메일 전송은 생성기의 명시적 `email` 모드에서만 수행합니다.
실행·보관 경로 설정은 [Mock 올인원 실행](../Farino_AIO_Mock/README.md#mock-올인원-실행)을 따릅니다.
