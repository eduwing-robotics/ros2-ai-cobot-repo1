# Production DB와 파일 기반 품질 문서

## 현재 구성

2026-08-31 기준 DDL은 `production` 6개 테이블과 `control` 1개 테이블을
정의한다.

| 저장 위치 | 대상 | 소유·용도 |
|---|---|---|
| PostgreSQL `production` | `products`, `parts`, `product_slots`, `jobs`, `units`, `unit_defects` | 제품 정의와 생산 실행·검사 결과 |
| PostgreSQL `control` | `assembly_requests` | MainServer와 AssemblySequencer 사이의 영속 command queue |
| [부품 데이터시트](../../MAIN_SERVER/data/semiconductor_assembly_quality_datasheet_2026-08-18.xlsx) | 부품 후보, 단가, 검사항목 | `part_catalog`을 대신하는 읽기 전용 XLSX |
| `MAIN_SERVER/reports/defects/*.xlsx` | 불량대책서 | `defect_report`를 대신하는 자동 생성 파일 |

`part_catalog`과 `defect_report` 스키마는 제거했다. 기준 DDL은
[production_schema.sql](../../DATA_STATION/DB/production_schema.sql) 하나다.

## 스키마

![production 6개 테이블 스키마](./images/production-schema.png)

문서용 이미지는 현재 DDL의 테이블과 열을 기준으로 렌더했다. 편집 가능한 기존
ERD 원본은 [db-erd-guide.drawio](./db-erd-guide.drawio)다.

### 테이블 역할

| 테이블 | 기본 키 | 주요 열 | 관계 |
|---|---|---|---|
| `products` | `product_id` | `product_code`, `product_name`, `product_version`, `is_selectable` | 제품 정의 |
| `parts` | `part_id` | `part_name`, `part_category`, `stock_quantity` | 생산에 사용하는 부품과 재고 |
| `product_slots` | `product_slot_id` | `product_id`, `slot_code`, `part_id` | 제품의 슬롯별 부품 배치 |
| `jobs` | `job_id` | `product_id`, `requested_quantity`, `recipe_version`, `job_status` | 생산 요청과 실행 기간 |
| `units` | `unit_id` | `job_id`, `unit_sequence_in_job`, `unit_status`, `inspection_result` | Job에서 생산한 개별 Unit |
| `unit_defects` | `unit_defect_id` | `unit_id`, `product_slot_id`, `defect_type` | FAIL Unit의 슬롯 단위 불량 |
| `control.assembly_requests` | `request_id` | `runtime_mode`, `payload`, `request_status`, `job_id`, `unit_id` | 영속 요청과 production 실행 연결 |

관계는 다음 두 흐름으로 읽는다.

```text
products ──< product_slots >── parts
products ──< jobs ──< units ──< unit_defects >── product_slots
control.assembly_requests ── job_id/unit_id ──> jobs/units
```

### DB가 보장하는 규칙

- 제품 코드와 버전 조합은 유일하다.
- 한 제품에서 같은 `slot_code`를 중복할 수 없다.
- 동시에 `PENDING` 또는 `RUNNING`인 Job은 최대 1개다.
- Job 상태는 `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`만 허용한다.
- Unit 검사는 `PENDING`, `PASS`, `FAIL`만 허용하고, 완료 시각과 검사 시각의 순서를 검사한다.
- 불량 유형은 `MISSING`, `POSITION_ERROR`, `ORIENTATION_ERROR`, `CRACK`만 허용한다.
- 한 Unit의 같은 Product Slot에는 불량 레코드를 하나만 기록한다.
- command 상태는 `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`만 허용한다.
- `RUNNING` command는 최대 1개이며 Job·Unit과 claim 시각이 반드시 연결된다.

## 부품 데이터시트

부품 하나가 한 행이고, 같은 `부품 타입`이면 서로 대체 후보다. 보드당 수량과 슬롯
배치는 시트에 없다 — `production.product_slots`가 갖고 있다. 별도의 카탈로그 DB는
만들지 않고 [datasheet.py](../../MAIN_SERVER/datasheet.py)가 다음 시트를 직접 읽는다.

| 시트 | 헤더 행 | 사용 내용 |
|---|---:|---|
| `Components` | 4 | 부품 타입, MPN, 핵심 정격, 공급사, 단가, 기준 수량, 확인일 |
| `Checklist` | 3 | 부품 타입별 입고·조립·신뢰성 검사와 이상 시 조치 |

두 축은 `part_category`로 만난다. DB가 보드당 수량을, 데이터시트가 단가를 갖고
있어 보드 원가는 둘을 곱해야 나온다.

```text
production.parts.part_category  ==  데이터시트 '부품 타입'
production.parts.part_name      ==  후보 3종 중 하나의 'MPN'   → unit_price_selected
```

현재 Production 부품 연결은 다음과 같다. 단가는 후보 3종의 폭이다.

| Part ID | 부품 타입 | Slot | 수량 | 선택 부품 | 단가 |
|---|---|---|---:|---|---|
| `HBM` | `HBM_MEMORY` | `HBM-01~08` | 8 | SK hynix HBM3E 12-Hi 36GB | $352.00 ($338~$361) |
| `PM` | `POWER_MODULE` | `PM-01~04` | 4 | Fabrikam FB-PM4424-15Q | $10.21 ($5.75~$11.90) |
| `GPU` | `GPU_MODULE` | `GPU-01` | 1 | NVIDIA GB200 GPU Module | $32,000 ($16,800~$32,000) |
| `CAP` | `MLCC` | `CAP-01~05` | 5 | Contoso CX-0603X7R104K100 | $0.15 ($0.09~$0.15) |
| `IND` | `POWER_INDUCTOR` | `IND-01~02` | 2 | Contoso CX-XL7030-152M | $4.07 ($3.62~$4.48) |
| `VRM` | `VOLTAGE_REGULATOR` | `VRM-01~05` | 5 | Fabrikam FB-VR546D24 | $12.26 ($9.45~$12.26) |

`GET /api/v1/products/{id}/requirements`가 이 둘을 합쳐 보드당 원가를 낸다. 주품목
기준 $34,927.03이고, 후보를 바꾸면 $19,581.94 ~ $35,006.61 사이에서 움직인다.

제조사명과 P/N은 MLCC·인덕터·파워모듈·VRM 4종이 문서용 가상 사명이다. HBM·GPU는
UI 스프라이트에 제조사 로고가 포함되어 있어 실존 제품명을 쓴다. 단가는 시뮬레이션용
근사값이지 발주 근거가 아니다.

## 불량대책서

![자동 생성 불량대책서 미리보기](./images/defect-report.png)

이미지는 테스트 DB의 Job 22에서 실제 생성한
`QA-J22-HBM-MISSING.xlsx` 값을 사용한 문서용 미리보기다.

[generate_defect_reports.py](../../MAIN_SERVER/generate_defect_reports.py)는 완료된
Job의 FAIL Unit을 읽고, Job·Part·불량 유형별로 묶어서
`MAIN_SERVER/reports/defects`에 파일을 만든다.

```text
production.jobs / units / unit_defects / product_slots / parts
                              +
semiconductor_assembly_quality_datasheet_2026-08-18.xlsx
                              ↓
QA-J{job_id}-{part_id}-{defect_type}.xlsx
```

생성 규칙은 다음과 같다.

- 파일명에 사용할 수 없는 문자는 `_`로 바꾼다.
- 기존 파일은 덮어쓰지 않아 담당자가 입력한 회신을 보호한다.
- 임시 파일을 완성한 뒤 원자적으로 이동한다.
- 데이터시트에 해당 부품 타입이 없으면 `데이터시트 연결 없음`으로 표시하되 보고서 생성은 계속한다.
- DB에는 보고서 상태나 회신을 다시 저장하지 않는다.

수동 생성 명령:

```bash
cd /home/codlab/Main_Unity
MAIN_SERVER_DB_DSN='dbname=main_unity_mock_test' \
  python3 MAIN_SERVER/generate_defect_reports.py
```

운영 자동 생성은 같은 명령을 1분마다 실행하며, `flock`으로 중복 실행을 막는다.

## 실행 흐름과 소유권

1. Unity가 MainServer HTTP API에 조립 command를 보낸다.
2. MainServer는 command를 `control.assembly_requests`에 저장하고 `production`은 조회만 한다.
3. AssemblySequencer가 command를 claim하면서 Job·Unit을 만들고 재고·검사 결과를 `production`에 기록한다.
4. 불량대책서 생성기가 완료된 FAIL 기록과 데이터시트를 결합해 XLSX를 발행한다.
5. Unity/Scenario는 DB나 파일을 직접 다루지 않고 주입된 로봇 인터페이스를 사용한다.

## 검증

Mock test DB의 schema 적용과 E2E에서 아래 7개 테이블을 확인했다.

```text
control.assembly_requests
production.jobs
production.parts
production.product_slots
production.products
production.unit_defects
production.units
```

검증용 SQL은 [003_smoke_test.sql](../../DATA_STATION/DB/003_smoke_test.sql),
조회 예시는 [002_query_samples.sql](../../DATA_STATION/DB/002_query_samples.sql)을
사용한다.
