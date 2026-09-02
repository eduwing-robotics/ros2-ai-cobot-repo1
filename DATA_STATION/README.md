# Data Station

PostgreSQL 생산 데이터 계약과 검증용 SQL을 관리합니다.

## 역할과 책임

- 역할: MainServer와 AssemblySequencer가 공유하는 DB 스키마 기준점
- 책임: `production` 스키마, 제약조건·인덱스, 조회 예제, smoke test와 Mock seed 제공
- 책임 아님: DB 서버 운영, HTTP API, 조립 실행과 런타임 데이터 쓰기

`DB/production_schema.sql`이 기준 스키마이며 나머지 SQL은 조회·검증·Mock 데이터 준비에 사용합니다.
