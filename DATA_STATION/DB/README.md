# production 데이터 설계

`production_schema.sql`은 production 데이터 계약의 기준 원본입니다. 이 문서는 테이블과 컬럼을 복제하지 않고 스키마가 보장해야 할 업무 의미와 소유 경계만 설명합니다.

## 소유 범위

production 데이터는 다음 사실을 보존합니다.

- 생산 대상 제품과 부품 구성
- 사용자가 요청한 PASS 목표 수량
- 각 생산 시도의 조립·검사 결과
- 검사된 제품 슬롯과 확정 불량 여부
- 실제 생산에 따른 재고 변동 원인
- 확정 불량의 품질 문서 전송 상태

DB 서버 운영, HTTP 처리, 레시피 실행과 설비 제어는 이 계약의 책임이 아닙니다.

## 핵심 관계

```text
Product ──< Product Slot >── Part
Product ──< Job ──< Unit ──< Unit Defect >── Product Slot
Part ──< Inventory Movement >── Unit
Unit Defect ── Defect Report Delivery
```

Job은 생산 요청이고 Unit은 실제 생산 시도입니다. 이 둘을 분리해 검사 FAIL 뒤 재시도하더라도 요청 수량과 모든 생산 이력을 보존합니다.

## 불변 조건

- Job의 요청 수량은 PASS 목표 수량입니다.
- 동시에 `RUNNING`인 Job은 하나입니다.
- 한 Job에서 동시에 `RUNNING`인 Unit도 하나입니다.
- 검사 결과는 이송 전에도 기록하며 Unit은 전체 workflow 성공 후 `COMPLETED`가 됩니다. 목표 PASS 수에는 `COMPLETED`·`PASS` Unit만 포함합니다.
- 검사 이후 실행 실패·재시작 시 결과를 보존하고 Unit은 `FAILED`가 됩니다. 검사 FAIL도 전체 workflow가 성공하면 완료된 시도로 남습니다.
- 실행 실패 Unit은 `FAILED`로 남습니다.
- 생산에 사용된 제품 정의는 과거 의미가 바뀌지 않아야 합니다.
- 재고 현재값과 변동 원장은 같은 생산 사실을 가리켜야 합니다.
- 슬롯 검사 행은 Unit과 제품 슬롯을 함께 식별합니다. 기존 `unit_defects` 이름을 유지하며 `defect_type IS NULL`은 확정 불량이 없음을 뜻합니다.
- 보관 JSON은 판정·의심 항목·상세 측정값과 슬롯 행 UID를 연결합니다. 신규 검사 결과는 전체 제품 슬롯을 기록하며 과거 불량 전용 행의 누락 슬롯을 추정해 채우지 않습니다.
- `UNKNOWN` 검사 결과는 Unit을 RUNNING으로 보류합니다. 재시작 복구 시 Unit FAILED 전이와 함께 결과를 보존할 수 있습니다.
- 확정 불량마다 품질 문서 전송 상태가 하나만 존재해야 합니다.

가능한 불변 조건은 애플리케이션 관례가 아니라 DB 제약조건으로 보장합니다.

## 쓰기 권한

MainServer는 새 Job 등록과 생산 조회를 담당합니다. Sequencer는 Job·Unit 실행 상태, 검사와 재고를 기록합니다. 조회 전용 사용자는 production 사실을 변경할 수 없습니다.

Sequencer는 확정 불량과 자료가 준비된 품질 문서 전송 대기를 같은 transaction에 기록합니다. 정상·미확정 슬롯 행에는 전송 대기를 만들지 않습니다. MainServer는 대기 건의 발송 상태만 갱신하며 전송 실패로 확정된 검사 결과를 변경하지 않습니다.

## 저장하지 않는 데이터

- 레시피 본문과 조립 단계
- 설비 좌표와 calibration
- 실시간 관절·TCP·카메라 스트림
- 중간 단계 checkpoint
- 부품 공급 후보와 가격 원본
- 생성된 품질 문서와 담당자 회신

`defect_report_deliveries`는 문서 내용이 아니라 확정 불량의 전송 여부와 재시도만 보존합니다. DB에는 실행에 사용한 레시피 버전과 확정 결과만 기록합니다.

## 변경과 검증

스키마 변경은 기존 production 사실을 보존하는 migration으로 적용합니다. 변경 후에는 다음을 확인합니다.

- DDL과 migration 적용
- 참조 무결성과 단일 실행 제약
- 역할별 권한
- Job·Unit 상태 전이
- 검사와 재고 원장
- smoke test

DDL, migration, 역할, 조회 예제와 검증 SQL은 이 폴더의 실행 가능한 원본을 따릅니다.

## 배포 환경 식별

DB 관리자 설정 `app.runtime_mode`가 DB 환경을 식별합니다. Job·Unit 필드는 변경하지 않습니다.
MainServer와 Sequencer는 DB 전체 설정을 카탈로그에서 읽고 연결마다 기대 모드와 비교합니다.
미설정·불일치는 생산 데이터 작업 전에 차단합니다. 배포 절차는
[Mock 올인원 실행](../../Farino_AIO_Mock/README.md#mock-올인원-실행)을 따릅니다.
