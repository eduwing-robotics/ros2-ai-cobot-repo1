# Production Data Contract

`DATA_STATION/DB`는 MainServer와 Assembly Sequencer가 공유하는 PostgreSQL 데이터 계약과 검증 SQL을 관리합니다. 실행 서비스, HTTP API, 별도 시스템 계층이나 설비 backend가 아닙니다.

## 소유 범위

- `production` 스키마와 참조 무결성
- 동시 실행과 상태 전이를 보조하는 제약조건·인덱스
- 역할별 최소 권한
- 기존 데이터를 보존하는 migration
- 조회 예제와 smoke test
- 로컬 Mock 실행용 seed와 sample data

`production_schema.sql`이 신규 DB의 기준 DDL입니다. migration, 역할, 조회와 검증 SQL은 같은 폴더에서 이 계약을 적용하거나 확인합니다.

Mock으로 구분되는 자산은 seed와 sample data뿐입니다. production 스키마, migration과 역할 권한은 특정 실행 모드에 속하지 않습니다.

## 소비자 경계

MainServer는 조회와 새 Job 등록을 담당하고, Sequencer는 Job·Unit 실행 상태, 검사와 재고 결과를 기록합니다. Unity와 설비 backend는 production 테이블을 직접 사용하지 않습니다.

업무 의미와 불변 조건은 [production 데이터 설계](DB/README.md)를 따릅니다.
