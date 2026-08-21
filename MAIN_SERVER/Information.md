# MainServer 정보 소유 규격

MainServer가 직접 생성·변경하는 정보와 다른 시스템에서 읽기만 하는 정보를 구분한다.
HTTP 기능은 [README.md](./README.md), 프로세스 경계는 [Response.md](./Response.md), 설계 근거는
[Design.md](./Design.md)를 본다.

## 1. 소유의 의미

이 문서에서 **소유**는 정보의 생성, 검증, 상태 변경과 수명주기를 MainServer가 최종
책임진다는 뜻이다. 조회 결과를 HTTP로 반환하는 것은 원본 데이터의 소유가 아니다.

| 구분 | MainServer 권한 |
|---|---|
| 소유 정보 | 생성·검증·변경·삭제 |
| 참조 정보 | 조회와 응답 변환만 수행 |
| 비소유 정보 | 저장·해석·변경하지 않음 |

## 2. MainServer 소유 정보

### 2.1 대기 작업 요청

MVP는 아래 요청 한 건만 프로세스 메모리에 보관한다.

| 필드 | JSON 타입 | 규칙 |
|---|---|---|
| `request_id` | string | MainServer가 발급한 UUID. 접수와 셀 전달의 상관관계 ID |
| `product_code` | string | 공백이 아닌 제품 코드. 선택 가능한 제품이 정확히 한 건이어야 함 |
| `quantity` | integer | MVP는 `1`만 허용 |
| `recipe_version` | string | 공백이 아닌 버전 식별자. MainServer는 형식만 검증 |

수명주기: `POST /jobs` 접수 → 메모리에 1건 보관 → `GET /cell/next-job` 응답과 동시에 삭제.

- 이미 대기 요청이 있으면 새 요청은 `409`로 거부한다.
- 메모리 정보이므로 서버 재시작 시 사라진다.
- `request_id`는 `production.jobs.job_id`가 아니다.
- 레시피 본문과 실제 실행 가능 여부는 조립 노드가 검증한다.
- API와 셀 전달 계약에서는 수량 필드명을 `quantity`로 통일한다.

### 2.2 품질 판정과 대책서 상태

MainServer의 품질 스캐너가 `defect_report` 스키마의 쓰기를 소유한다. 실제 테이블 정의는
[001_schema.sql](../DATA_STATION/DB/001_schema.sql)을 원본으로 사용한다.

| 정보 | 테이블 | 소유 내용 |
|---|---|---|
| 임계 정책 | `defect_report.thresholds` | 대상 부품·불량 유형, 기준 불량률, 최소 검사량, 평가 기간과 활성 상태 |
| 품질 알림 | `defect_report.alerts` | 초과 시점 집계값, 적용 임계값, 상태, 담당자, 기한과 문서 경로 |
| 고정 근거 | `defect_report.alert_evidence` | 발행 당시 유닛·슬롯·불량 유형·검사 시각·이미지 경로 스냅샷 |
| 대책과 검증 | `defect_report.alert_countermeasures` | 원인 요약, 적용 레시피 버전과 개선 효과 판정 |
| 스캔 실행 | `defect_report.scan_runs` | 평가 구간, 시작·종료 시각, 발행 건수와 성공·실패 상태 |

공통 규칙:

- 비율은 퍼센트가 아닌 `0..1` 범위로 저장하고 반환한다.
- 기간은 `[period_start, period_end)`로 계산한다.
- `alerts`와 `alert_evidence`의 집계값·근거는 발행 시점 스냅샷이며 덮어쓰지 않는다.
- `(part_id, defect_type)`별 미종결 알림은 하나만 허용한다.
- 상태 문자열은 DB 제약에 정의된 값만 사용한다.

### 2.3 문서 산출물

| 정보 | 저장 위치 | 규칙 |
|---|---|---|
| 대책서 공식 양식 | `MAIN_SERVER/templates/불량대책서_표준양식.xlsx` | `{{token}}` 자리표시자를 스캐너가 치환한다. 셀↔컬럼 대응은 `불량대책서_필드매핑.md` |
| 생성된 대책서 | 배포 환경의 문서 저장 경로 | 위치를 `alerts.document_path`에 기록한다 |

메일 발송 대상과 승인 절차는 아직 MainServer 소유 정보로 정의하지 않는다.

## 3. 참조 정보

MainServer는 아래 정보를 `datastation_reader`로 조회하지만 원본을 소유하지 않는다.

| 원본 | 정보 | 소유자 |
|---|---|---|
| `production.products`, `product_slots`, `parts` | 제품, 슬롯 구성, 부품과 재고 | production 배포·assembly bridge 경계 |
| `production.jobs`, `units`, `unit_defects` | 작업 진행, 완성 수량, 검사와 불량 이력 | assembly bridge |
| `part_catalog.*` | 데이터시트, 공급 정보, 대체 후보와 검사 체크리스트 | 데이터시트 적재 경로 |
| `MAIN_SERVER/data/*.xlsx` | 미완성 데이터시트 참조 파일 | 원본 소유자 미확정; MainServer 소유 정보로 사용하지 않음 |

MainServer는 참조 정보에 `INSERT`, `UPDATE`, `DELETE`를 수행하지 않는다. 조회 결과 캐시도 현재
범위에는 두지 않는다.

## 4. 비소유 정보

MainServer는 다음 정보를 저장하거나 해석하지 않는다.

- Unity `GameObject`, `Transform`, `Pose`와 화면 상태
- Mock/Real 선택
- ROS 토픽·서비스·액션 이름과 메시지 본문
- 레시피 본문, 조립 순서, 좌표, 프레임, 툴과 모션 파라미터
- 비전 좌표 변환과 검사 알고리즘 내부 상태
- 컨베이어, 관절, TCP와 그리퍼 제어 명령
- 하드웨어 안전 조건과 실제 작업 완료 판정

## 5. 식별자와 이름

| 이름 | 소유자 | 의미 |
|---|---|---|
| `request_id` | MainServer | 접수된 대기 요청의 UUID |
| `job_id` | production 기록 경계 | DB에 생성된 생산 작업의 bigint PK |
| `product_code` | production 기준정보 | 제품 계열 코드 |
| `product_version` | production 기준정보 | 같은 제품 코드의 구조 버전 |
| `recipe_version` | 조립 노드의 레시피 저장소 | 실행 방법 버전 |
| `alert_id`, `alert_code` | MainServer | 품질 알림의 내부 PK와 외부 표시 코드 |

`request_id`와 `job_id`의 영속 연결 방식은 아직 정의되지 않았다. 연결 계약이 확정되기 전에는
두 값을 같은 ID로 취급하거나 한 값으로 다른 값을 추정하지 않는다.

## 6. 실행 설정과 비밀정보

DB 접속 문자열과 자격정보는 실행 환경에서 주입한다. 소스, 로그와 HTTP 오류 본문에 저장하지
않는다. 조회 자격과 `defect_report` 쓰기 자격은 분리하며, MainServer 실행 자격에는
`production` 쓰기 권한을 부여하지 않는다.

