# 3스키마 통합 설계 — production · part_catalog · defect_report

## 왜 나누는가

조립 작업 기록, 부품 데이터시트, 불량 대책서는 모두 같은 부품을 다루지만 **소유자와 갱신
주기가 다르다.** 한 스키마에 몰면 조달 데이터가 작업 기록보다 커지고, 데이터시트를 갱신할
때마다 조립 기록 스키마를 건드리게 된다.

그렇다고 파일로 분리하면 대책서 한 장을 만들 때마다 22칼럼 엑셀을 파싱해야 한다.

그래서 **PostgreSQL 인스턴스 하나에 스키마 세 개**로 나눈다. 조인은 되고 소유권은 분리된다.

| 스키마 | 한 줄 정의 | 쓰는 주체 | 갱신 주기 |
|---|---|---|---|
| `production` | 조립·검사 실행 기록 | 로봇 제어, 검사 시스템 | 작업마다 |
| `part_catalog` | 부품 데이터시트 적재 | 조달·품질 배치 | 주·분기 |
| `defect_report` | 불량 판정 정책과 대책서 | 문서 발행 백엔드 | 임계 초과 시, 분기 |

## 배치

```text
PostgreSQL 인스턴스
├── production      parts · products · product_slots · jobs · units · unit_defects
├── part_catalog    part_groups · part_candidates · part_supply · sources
│                   quality_checklists · datasheet_loads
└── defect_report   thresholds · alerts · alert_evidence · alert_countermeasures
                    scan_runs
```

`production` 상세는 [DB.md](./DB.md)에, 이 스키마들에 데이터를 쓰는 시스템 계층 구조는
[Architecture.md](./Architecture.md)에, 레시피 파일 규격은 [Recipe.md](./Recipe.md)에 있다. 이 문서는 `part_catalog`, `defect_report`와 세 스키마의
연동만 다룬다.

## 스키마 간 계약

### 외래키를 걸지 않는다

스키마 경계를 넘는 참조는 **논리 조인**이다. 물리 외래키를 만들지 않는다.

| 조인 | 키 |
|---|---|
| `production.parts` ↔ `part_catalog.part_groups` | `part_catalog.part_group_links` 경유. `part_id`와 `group_id`는 값 공간이 다르다 |
| `defect_report.alerts` → `production.parts` | `part_id` |
| `defect_report.alert_evidence` → `production.units` | `unit_id`, `product_slot_id` |
| `defect_report.alert_countermeasures` → `production.jobs` | `recipe_version` |

외래키를 걸면 조달팀이 단종 부품을 데이터시트에서 지울 때 작업 기록 삭제가 막히고, 반대로
`part_catalog` 적재 배치가 `production` 락을 기다리게 된다. 각 스키마가 자기 무결성만 책임진다.

### 방향은 한쪽이다

```text
production  ──읽기──▶  defect_report  ──읽기──▶  part_catalog
   ▲                    │
   └────레시피 개정─────┘
```

`production`는 다른 스키마를 **읽지도 쓰지도 않는다.** 로봇과 검사 시스템은 대책서의 존재를
모른 채 동작한다. `defect_report`가 양쪽을 읽어 문서를 만들고, 대책의 결과는 사람이 레시피를
개정해 `production`로 돌아온다. 코드가 아니라 사람과 레시피를 거치는 것이 유일한 역방향이다.

### 스냅샷을 저장한다

`defect_report`는 발행 시점의 집계값과 부품 정보를 **자기 테이블에 복사해 둔다.** 나중에 데이터가
추가되거나 임계값이 바뀌어도 이미 발행된 문서의 숫자는 변하지 않아야 한다.

## part_catalog 스키마

데이터시트(`semiconductor_assembly_quality_datasheet_*.xlsx`)를 적재한다. 원본 시트 한 행이
테이블 한 행에 대응한다.

### part_groups

`Components` 시트의 Group ID 단위. `production.parts`와 1:1로 맞물린다.

| 칼럼 | 역할 |
|---|---|
| `group_id` (PK) | `C-001` 등. `production.parts.part_id`와 같은 값이다 |
| `category_label` | `캐패시터` 등 사람이 읽는 범주명 |
| `role_summary` | 회로에서의 역할 요약 |

`production.parts.part_category`는 `MLCC` 같은 코드고, 여기의 `category_label`은 `캐패시터`다.
대책서는 둘을 합쳐 `캐패시터 (MLCC)`로 출력한다.

### part_group_links

`production.parts.part_id`와 `part_catalog.part_groups.group_id`를 잇는다.
두 값은 값 공간이 다르다(`CAP` vs `C-001`). 이 표가 없으면 대책서의 「대체품」과
「판단자료 D」가 성립하지 않는다.

| 칼럼 | 역할 |
|---|---|
| `part_id` (PK) | `production.parts.part_id`. 외래키는 걸지 않는다 |
| `group_id` (FK) | 소속 부품 그룹 |
| `image_path` | 부품 렌더 이미지. Unity `Assets/` 기준 상대 경로 (`UI/Icons/item-cap.png`) |
| `load_id` (FK) | 어느 적재본에서 왔는지 |

연결원은 데이터시트의 「HBM Package Board BOM」 시트 `Group ID` 열이다. 그 시트가 이미
`part_id` 한 행 단위라 grain이 같다. Components 시트는 후보 한 행 단위라 여기에 `part_id`를
넣으면 값이 중복된다.

**소유자는 `part_catalog`다.** `production`에 컬럼을 추가하면 셀의 ROS2 계층이 소유자가 되어
경계가 어긋난다. 데이터시트 로더가 쓰기를 소유하므로 여기에 둔다.

연결이 없는 부품은 대책서 「대체품」 시트를 `해당 데이터시트 없음`으로 비우고 발행한다.
**문서 발행이 이 연결에 막혀서는 안 된다.**

### part_candidates

한 행이 하나의 구매·검증 후보다. 주품목과 대체 후보를 같은 테이블에 둔다.

| 칼럼 | 역할 |
|---|---|
| `candidate_id` (PK) | 후보 식별자 |
| `group_id` (FK) | 소속 부품 그룹 |
| `candidate_role` | `PRIMARY` 또는 `ALTERNATE` |
| `alternate_code` | `ALT-01`. 주품목은 NULL |
| `manufacturer` | 제조사 |
| `manufacturer_part_number` | 제조사 P/N. 주품목 값은 `production.parts.part_name`과 같다 |
| `key_spec` | 핵심 사양·용도 |
| `lifecycle_status` | `Active`, `사양 후보` 등 수명주기 |
| `compatibility_status` | `승인 주품목`, `동급 후보`, `비핀호환 후보` |
| `revalidation_items` | 필수 재검증 항목 |
| `defect_relevance` | 특정 불량유형에 유리/불리한 소견. 사람이 채운다. 비면 대책서에 `미평가`로 인쇄된다 |
| `source_id` (FK) | 근거 출처 |
| `note` | 비고 |

`(group_id, manufacturer_part_number)`는 중복되지 않는다.
`(group_id, candidate_role='PRIMARY')`인 행은 그룹당 하나여야 한다.

**모든 `ALTERNATE`는 승인 전 사용 금지다.** 이 상태는 `compatibility_status`가 아니라
승인 절차가 결정하므로, 승인 이력이 필요해지면 별도 테이블을 추가한다.

### part_supply

가격과 재고는 사양보다 훨씬 자주 바뀌므로 분리한다.

| 칼럼 | 역할 |
|---|---|
| `supply_id` (PK) | 공급 조건 식별자 |
| `candidate_id` (FK) | 대상 후보 |
| `supplier`, `supplier_part_number` | 공급사와 공급사 P/N |
| `unit_price`, `currency`, `price_quantity_basis` | 단가와 기준 수량 |
| `moq`, `stock_status`, `lead_time` | 최소 주문 수량, 재고, 리드타임 |
| `price_checked_at` | 가격 확인일 |

원본의 `확인 불가`는 문자열로 넣지 않고 **NULL**로 정규화한다. 값이 없는 것과 "없다고 확인한
것"을 구분해야 하면 별도 플래그를 둔다.

이 테이블은 `production.parts.stock_quantity`와 **무관하다.** 이쪽은 공급사 재고이고, 저쪽은
현장 보유 재고다.

### sources

| 칼럼 | 역할 |
|---|---|
| `source_id` (PK) | `S-01` 등 |
| `source_type` | `PRIMARY` 또는 `ALTERNATE` |
| `item_name` | 확인 대상 품목 |
| `verified_content` | 확인 내용 |
| `url` | 원문 URL |
| `checked_at` | 확인일 |

### quality_checklists

`Checklist` 시트. 대책서의 초동조치와 재검증 항목 초안을 여기서 가져온다.

| 칼럼 | 역할 |
|---|---|
| `checklist_id` (PK) | 식별자 |
| `category` | `공통`, `MLCC`, `Boost IC` 등 |
| `incoming_inspection` | 입고 검사 |
| `assembly_control` | 조립·보관 관리 |
| `reliability_test` | 기능·신뢰성 검사 |
| `action_on_anomaly` | 이상 시 조치 |

`action_on_anomaly`는 대부분 "의심 Lot 전량 격리"를 요구한다. **`production`는 Lot을 저장하지
않으므로** 대책서에서는 격리 대상을 Lot이 아니라 `job_id`·`unit_id` 범위로 치환해 출력한다.

## defect_report 스키마

### thresholds

임계값 정책. `production`에 두지 않는 이유는 이것이 작업 기록이 아니라 판정 기준이기 때문이다.

| 칼럼 | 역할 |
|---|---|
| `threshold_id` (PK) | 기준 식별자 |
| `part_id` | 대상 부품. NULL이면 전체 기본값 |
| `defect_type` | 대상 불량 유형. NULL이면 전 유형 합산 |
| `threshold_rate` | 기준 불량률. `0.003` |
| `min_inspected_quantity` | 판정에 필요한 최소 검사 건수. `1000` |
| `window_days` | 집계 구간 길이 |
| `evaluation_mode` | `ROLLING` 또는 `QUARTERLY` |
| `is_active` | 현재 적용 여부 |
| `effective_from` | 적용 시작 시각 |

부품·유형별 기준이 없으면 NULL 행의 기본값으로 내려간다. 가장 구체적인 행이 이긴다.

### alerts

발행된 대책서 한 건. **집계값을 스냅샷으로 저장한다.**

| 칼럼 | 역할 |
|---|---|
| `alert_id` (PK) | 내부 식별자 |
| `alert_code` | `QA-CAP-CRACK-20260819-001`. `QA-{part_id}-{defect_type}-{YYYYMMDD}-{NNN}`. 중복 불가 |
| `trigger_type` | `THRESHOLD` 또는 `QUARTERLY` |
| `part_id`, `defect_type` | 대상 부품과 불량 유형 |
| `threshold_id` (FK) | 적용된 기준 |
| `period_start`, `period_end` | 집계 구간 |
| `inspected_quantity` | 부품 장착 검사 건수 |
| `inspected_unit_quantity` | 검사 완료 완성품 대수 |
| `defective_quantity`, `defect_rate` | 불량 건수와 불량률 |
| `threshold_rate`, `min_inspected_quantity` | 발행 시점 기준값 스냅샷 |
| `first_exceeded_at` | 최초 임계 초과 시각 |
| `source_recipe_version` | 집계 대상 작업의 레시피 버전 |
| `alert_status` | `ISSUED`, `ASSIGNED`, `IN_PROGRESS`, `VERIFYING`, `CLOSED` |
| `assignee` | 담당자 |
| `issued_at`, `initial_action_due_at`, `final_action_due_at`, `closed_at` | 발송과 기한 |
| `document_path` | 발행된 xlsx 경로 |

`(part_id, defect_type)`에 대해 `alert_status`가 `CLOSED`가 아닌 행은 **하나만** 존재한다.
이 제약이 중복 발송을 막는다. 임계를 넘긴 상태는 담당자가 조치를 끝낼 때까지 계속 넘어간
상태로 남기 때문에, 이 제약이 없으면 스캐너를 돌릴 때마다 같은 문서가 재발행된다.

회신본 원본은 xlsx로 돌므로 `document_path`를 남긴다
(`production.units.inspection_image_path`와 같은 방식이다). 다만 ①②③⑥ **요약은 컬럼으로
받는다.** 재발 시 「판단자료 C」가 과거 대책서를 그대로 읽어야 하는데, 본문이 파일에만 있으면
그 표가 문서번호와 상태만 남고 비어 버린다. 루프를 닫는 것이 이 스키마의 목적이다.

### alert_evidence

집계 수치의 근거가 된 개별 불량 건. **발행 시점 스냅샷이다.**

| 칼럼 | 역할 |
|---|---|
| `evidence_id` (PK) | 식별자 |
| `alert_id` (FK) | 소속 대책서 |
| `unit_id`, `product_slot_id` | `production` 논리 참조 |
| `slot_code`, `defect_type` | 발행 시점 값 복사 |
| `inspected_at`, `inspection_image_path` | 검사 시각과 이미지 경로 |

`(alert_id, unit_id, product_slot_id)`는 중복되지 않는다.

기간과 부품으로 재계산하면 되는데 왜 복사하는가. 재계산 시점에는 데이터가 더 쌓여 있어
문서에 인쇄된 숫자와 달라지기 때문이다. 발행된 문서와 DB가 영구히 일치해야 한다.

### alert_countermeasures

대책과 효과 검증. **여기서 `production`로 루프가 닫힌다.**

| 칼럼 | 역할 |
|---|---|
| `countermeasure_id` (PK) | 식별자 |
| `alert_id` (FK) | 소속 대책서 |
| `containment_summary` | ① 초동 조치 — 격리·선별·출하보류 범위와 완료 시각 |
| `root_cause_summary` | ② 발생 원인. 확정된 근본 원인 요약 |
| `escape_cause_summary` | ③ 유출 원인 — 왜 검사에서 걸리지 않았는가 |
| `applied_recipe_version` | 대책 적용 후 실행한 레시피 버전 |
| `applied_at` | 적용 시각 |
| `verification_status` | `PENDING`, `EFFECTIVE`, `INEFFECTIVE` |
| `verified_inspected_quantity`, `verified_defective_quantity`, `verified_defect_rate` | 검증 집계 |
| `verified_at` | 검증 확정 시각 |
| `closure_note` | ⑥ 종결 의견. 잔여 위험과 승인 의견 |
| `closed_by` | 종결 처리자 |

`applied_recipe_version`은 `production.jobs.recipe_version`을 가리킨다. 이 값이 있어야
대책 적용 전후 불량률을 같은 제품 안에서 비교할 수 있다.

## 데이터 흐름

```text
① 사용자 요청        → production.jobs (product_id, requested_quantity, recipe_version)
② 조립·검사          → production.units, production.unit_defects
③ 주기 집계          → defect_report가 production을 읽어 부품·유형별 불량률 산출
④ 임계 판정          → defect_report.thresholds와 대조
⑤ 부품 정보 조회      → part_catalog에서 제조사·대체 후보·재검증 항목·출처
⑥ 대책서 발행        → defect_report.alerts + alert_evidence, xlsx 생성·발송
⑦ 담당자 원인 분석    → 레시피 개정
⑧ 새 레시피로 실행    → production.jobs.recipe_version 갱신 (①로 복귀)
⑨ 효과 검증          → defect_report.alert_countermeasures, 적용 전후 불량률 비교
⑩ 종결              → alert_status = CLOSED
```

③~⑥은 자동이고 ⑦은 사람이며 ⑧은 로봇이다. `production`가 다른 스키마를 모르는 이유가
여기 있다. 로봇은 레시피만 보고 돌면 되고, 그 레시피가 왜 바뀌었는지는 알 필요가 없다.

## 통합 조회

### 대책서 머리말 채우기

```sql
SELECT a.alert_code, a.issued_at, a.alert_status, a.assignee,
       a.part_id,
       pg.category_label || ' (' || p.part_category || ')' AS category_display,
       pc.manufacturer, pc.manufacturer_part_number,
       a.period_start, a.period_end, a.first_exceeded_at,
       a.inspected_quantity, a.defective_quantity, a.defect_rate,
       a.threshold_rate, a.defect_rate - a.threshold_rate AS excess_rate,
       a.min_inspected_quantity, a.defect_type
FROM defect_report.alerts a
JOIN production.parts p            ON p.part_id  = a.part_id
JOIN part_catalog.part_groups pg    ON pg.group_id = a.part_id
JOIN part_catalog.part_candidates pc ON pc.group_id = pg.group_id
                                 AND pc.candidate_role = 'PRIMARY'
WHERE a.alert_code = :alert_code;
```

세 스키마가 한 쿼리에 모인다. 이것이 파일 분리 대신 스키마 분리를 택한 이유다.

### 대체 후보 표 채우기

```sql
SELECT pc.alternate_code, pc.manufacturer, pc.manufacturer_part_number,
       pc.key_spec, pc.compatibility_status, pc.revalidation_items,
       pc.lifecycle_status, s.source_id, s.url,
       sup.supplier, sup.unit_price, sup.currency, sup.lead_time
FROM part_catalog.part_candidates pc
LEFT JOIN part_catalog.sources s     ON s.source_id = pc.source_id
LEFT JOIN part_catalog.part_supply sup ON sup.candidate_id = pc.candidate_id
WHERE pc.group_id = :part_id
  AND pc.candidate_role = 'ALTERNATE'
ORDER BY pc.alternate_code;
```

### 임계 초과 감지

분모와 분자를 따로 집계한다. 분모는 **부품 단위 검사 건수**이고 분자는 **부품·유형별 불량
건수**다. 하나의 `GROUP BY`로 두 값을 동시에 내려 하면 유형별 행의 분모가 그 유형의 불량
건수 자신이 되어 불량률이 항상 100%가 된다.

```sql
WITH inspected AS (
    SELECT p.part_id,
           COUNT(*) AS inspected_quantity,
           COUNT(DISTINCT u.unit_id) AS inspected_unit_quantity
    FROM production.jobs j
    JOIN production.units u          ON u.job_id = j.job_id
    JOIN production.product_slots ps ON ps.product_id = j.product_id
    JOIN production.parts p          ON p.part_id = ps.part_id
    WHERE u.inspection_result IN ('PASS','FAIL')
      AND u.inspected_at >= :period_start
      AND u.inspected_at <  :period_end
    GROUP BY p.part_id
),
defective AS (
    SELECT ps.part_id, ud.defect_type,
           COUNT(*) AS defective_quantity,
           MIN(u.inspected_at) AS first_defect_at
    FROM production.unit_defects ud
    JOIN production.units u          ON u.unit_id = ud.unit_id
    JOIN production.product_slots ps ON ps.product_slot_id = ud.product_slot_id
    WHERE u.inspection_result IN ('PASS','FAIL')
      AND u.inspected_at >= :period_start
      AND u.inspected_at <  :period_end
    GROUP BY ps.part_id, ud.defect_type
)
SELECT i.part_id, d.defect_type,
       i.inspected_quantity, i.inspected_unit_quantity,
       d.defective_quantity, d.first_defect_at,
       d.defective_quantity::numeric / i.inspected_quantity AS defect_rate,
       t.threshold_id, t.threshold_rate, t.min_inspected_quantity
FROM inspected i
JOIN defective d ON d.part_id = i.part_id
JOIN LATERAL (
    SELECT th.*
    FROM defect_report.thresholds th
    WHERE th.is_active
      AND th.evaluation_mode = :evaluation_mode
      AND (th.part_id     IS NULL OR th.part_id     = i.part_id)
      AND (th.defect_type IS NULL OR th.defect_type = d.defect_type)
    ORDER BY (th.part_id IS NOT NULL) DESC, (th.defect_type IS NOT NULL) DESC
    LIMIT 1
) t ON TRUE
WHERE i.inspected_quantity >= t.min_inspected_quantity
  AND d.defective_quantity::numeric / i.inspected_quantity > t.threshold_rate
  AND NOT EXISTS (
      SELECT 1 FROM defect_report.alerts a
      WHERE a.part_id     = i.part_id
        AND a.defect_type = d.defect_type
        AND a.alert_status <> 'CLOSED');
```

세 가지가 한 쿼리에서 끝난다.

- `JOIN LATERAL`의 `ORDER BY ... LIMIT 1`이 **가장 구체적인 기준을 고른다.** 부품·유형별
  기준이 있으면 그것을, 없으면 부품별을, 그것도 없으면 전체 기본값을 쓴다. 이 정렬이 없으면
  기본값 행과 구체 행이 함께 매칭되어 같은 부품에 대해 대책서가 두 장 발행된다.
- `min_inspected_quantity` 조건이 표본이 적을 때의 과민 반응을 막는다.
- 마지막 `NOT EXISTS`가 **중복 발송을 막는다.** 임계를 넘긴 상태는 담당자가 조치를 끝낼
  때까지 계속 넘어간 상태로 남으므로, 이 조건이 없으면 스캐너를 돌릴 때마다 같은 문서가
  재발행된다.

### 효과 검증

```sql
SELECT j.recipe_version,
       MIN(u.inspected_at) AS first_inspected_at,
       COUNT(*) AS inspected_quantity,
       COUNT(ud.unit_defect_id) AS defective_quantity,
       ROUND(100.0 * COUNT(ud.unit_defect_id) / NULLIF(COUNT(*), 0), 4) AS defect_rate_percent
FROM defect_report.alerts a
JOIN defect_report.alert_countermeasures cm ON cm.alert_id = a.alert_id
JOIN production.jobs j
  ON j.recipe_version IN (a.source_recipe_version, cm.applied_recipe_version)
JOIN production.units u          ON u.job_id = j.job_id
JOIN production.product_slots ps ON ps.product_id = j.product_id
                              AND ps.part_id = a.part_id
LEFT JOIN production.unit_defects ud
       ON ud.unit_id = u.unit_id
      AND ud.product_slot_id = ps.product_slot_id
      AND ud.defect_type = a.defect_type
WHERE a.alert_code = :alert_code
  AND u.inspection_result IN ('PASS','FAIL')
GROUP BY j.recipe_version
ORDER BY first_inspected_at;
```

두 행이 나온다. 위가 대책 전, 아래가 대책 후다.

## 최신성과 정합성

세 스키마는 쿼리로만 대화한다. `production`은 자기가 소비된다는 사실을 모르고,
`defect_report`가 주기적으로 읽어간다. 이 구조에서 최신성을 어떻게 보장하는지 정한다.

### dirty flag를 두지 않는다

`production.units`에 `is_processed` 같은 처리 표시 칼럼을 두는 방식은 쓰지 않는다. 두 가지가
깨진다.

**생산자가 소비자를 알게 된다.** 로봇과 검사 시스템이 "누군가 이 행을 소비한다"는 사실을
알아야 플래그를 관리할 수 있다. `production`은 다른 스키마를 모른다는 원칙이 무너지고,
소비자가 둘로 늘면 플래그도 둘이 된다.

**읽기 전용 권한과 충돌한다.** 대책서 백엔드는 `production`에 `SELECT`만 갖는다. 플래그를
끄려면 쓰기 권한이 필요해지므로 권한 설계가 통째로 무너진다.

### 워터마크는 소비자가 가진다

"어디까지 처리했다"를 소비자가 자기 스키마에 기록한다. 생산자는 아무것도 하지 않는다.

```text
defect_report.scan_runs
  run_id (PK)
  evaluation_mode            ROLLING / QUARTERLY
  window_start, window_end   처리한 inspected_at 구간
  max_recorded_at            처리한 쓰기 시각 상한
  scan_started_at, scan_finished_at
  alerts_issued
  run_status                 RUNNING / SUCCEEDED / FAILED
```

이 방식이 성립하는 이유는 **감지 쿼리가 이미 멱등이기 때문이다.** `NOT EXISTS`로 종결되지
않은 대책서를 배제하므로 같은 구간을 두 번 스캔해도 문서가 두 장 발행되지 않는다. 스캐너가
죽으면 마지막 `SUCCEEDED` 워터마크부터 재개하고, 구간이 겹쳐도 안전하다.

dirty flag는 "정확히 한 번"을 노리다 실패하고, 워터마크는 "최소 한 번 + 멱등"으로 안전하다.

### 늦게 도착하는 쓰기

`units.inspected_at`은 **사건 시각**이지 쓰기 시각이 아니다. 이미 스캔한 구간에 속한 행이
나중에 INSERT되면 영원히 집계되지 않는다.

```text
09:00  [08-12 ~ 08-19) 구간 스캔 완료
09:05  08-18자 검사 결과가 재시도 끝에 뒤늦게 INSERT
       → 지나간 구간이라 집계되지 않음
```

MVP는 로봇 한 대와 활성 작업 한 건만 허용하므로 검사 결과가 검사 시점에 즉시 기록되고,
늦게 도착할 경로가 없다. **직전 구간을 겹쳐 스캔**하는 것으로 충분하다. 멱등하므로 겹침
비용은 없다.

로봇이 늘거나 오프라인 업로드가 생기면 `production.units`에 `recorded_at timestamptz NOT NULL
DEFAULT now()`를 추가하고 워터마크를 사건 시각이 아니라 쓰기 시각으로 건다. 이 칼럼은
`production` 자신의 사실이므로 경계를 깨지 않는다.

### 데이터시트 적재 이력

배치 적재는 실패하거나 건너뛰어도 조용히 낡은 값이 인쇄된다. 적재 자체를 기록한다.

```text
part_catalog.datasheet_loads
  load_id (PK)
  source_file        semiconductor_assembly_quality_datasheet_2026-08-18.xlsx
  source_dated_on    데이터시트 기준일
  loaded_at
  row_counts         시트별 적재 행 수
  load_status        SUCCEEDED / FAILED
```

`part_catalog`의 각 행에 `load_id`를 달아 어느 적재본에서 왔는지 추적한다. 대책서에는
**데이터시트 기준일을 인쇄한다.** 원본 xlsx도 기준일과 행별 `가격 확인일`을 갖고 있으므로,
읽는 사람이 낡은 정보인지 판단할 수 있어야 한다.

### 경계 정합성 점검

외래키를 포기했다는 것은 정합성이 **강제에서 탐지로 바뀌었다**는 뜻이다. 강제를 포기했으면
탐지를 넣어야 한다. 넣지 않으면 무결성을 그냥 버린 것이다. 스캔마다 아래 넷을 실행하고
결과가 비어 있지 않으면 경고를 올린다.

```sql
-- ① production에 있는데 데이터시트에 없는 부품. 대책서 조인이 실패한다
SELECT p.part_id, p.part_name
FROM production.parts p
LEFT JOIN part_catalog.part_groups g ON g.group_id = p.part_id
WHERE g.group_id IS NULL;

-- ② part_name = 주품목 MPN 계약 위반
SELECT p.part_id, p.part_name, c.manufacturer_part_number
FROM production.parts p
JOIN part_catalog.part_candidates c
  ON c.group_id = p.part_id AND c.candidate_role = 'PRIMARY'
WHERE p.part_name <> c.manufacturer_part_number;

-- ③ 근거가 사라진 대책서
SELECT e.alert_id, e.unit_id
FROM defect_report.alert_evidence e
LEFT JOIN production.units u ON u.unit_id = e.unit_id
WHERE u.unit_id IS NULL;

-- ④ 존재하지 않는 레시피를 가리키는 대책
SELECT cm.alert_id, cm.applied_recipe_version
FROM defect_report.alert_countermeasures cm
WHERE cm.applied_recipe_version IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM production.jobs j
                  WHERE j.recipe_version = cm.applied_recipe_version);
```

②는 [DB.md](./DB.md)에 문서로만 적어둔 계약을 실행 가능한 점검으로 바꾼 것이다.

### 스냅샷이 어긋나는 것은 정상이다

`defect_report`의 스냅샷과 `production`의 현재 값이 달라지는 것은 버그가 아니다. 발행된
문서는 "그때 알려진 사실"의 기록이고 영구히 그래야 한다.

다만 그 차이를 신뢰하려면 `production`이 **검사 확정 후에는 추가만 하고 수정하지 않아야**
한다. `inspection_result`가 사후에 뒤집히면 차이가 시점 차이인지 정정인지 구분할 수 없다.
`product_slots`는 `definition_locked_at`으로 이미 잠겨 있고, `units`와 `unit_defects`에도
같은 불변성이 필요하다. 이 선언은 [DB.md](./DB.md)의 무결성 계약에 있다.

### 지연을 줄이는 선택지

폴링 주기가 길어 불만이면 `LISTEN/NOTIFY`를 얹을 수 있다. 두 가지 조건을 지킨다.

- **페이로드에 defect_report 개념을 넣지 않는다.** `NOTIFY unit_inspected, '8003'` 정도면
  충분하다. `production`은 누가 듣는지 모른다.
- **NOTIFY를 진실로 삼지 않는다.** 리스너가 죽어 있으면 알림은 유실된다. 워터마크가
  진실이고 NOTIFY는 깨우는 신호일 뿐이다.

Outbox 테이블도 방법이지만 `production` 안에 소비자용 테이블이 생겨 경계가 흐려진다. MVP에는
과하다.

## 권한

스키마를 나눈 실질적 이득 하나는 권한을 분리할 수 있다는 것이다.

| 역할 | `production` | `part_catalog` | `defect_report` |
|---|---|---|---|
| 로봇 제어·검사 시스템 | 읽기·쓰기 | 없음 | 없음 |
| 데이터시트 적재 배치 | 없음 | 읽기·쓰기 | 없음 |
| 대책서 발행 백엔드 | **읽기 전용** | 읽기 전용 | 읽기·쓰기 |
| 조회 대시보드 | 읽기 전용 | 읽기 전용 | 읽기 전용 |

대책서 백엔드에 `production` 쓰기 권한을 주지 않는 것이 핵심이다. 문서 발행이 작업 기록을
바꿀 수 없어야 집계 결과를 신뢰할 수 있다.

## 후속 조건

| 요구 | 그때 추가할 것 |
|---|---|
| 대체품 승인 이력 | `part_catalog.candidate_approvals` |
| 부품 Lot 추적과 Lot 단위 격리 | `production`에 재고 이동·Lot 테이블 |
| 대책서 본문을 DB에서 검색 | `defect_report.alert_sections` |
| 재검사·재작업 이력 | `production`에 검사 실행 테이블 |
| 불량 유형 확장 | `production.unit_defects`의 `CHECK` 변경 |
| 여러 로봇·동시 작업 | `production`에 재고 예약 |
| 늦게 도착하는 검사 결과 | `production.units.recorded_at` + 쓰기 시각 워터마크 |
| 알림 지연 단축 | `LISTEN/NOTIFY` 또는 outbox |

## 열려 있는 결정

1. **분기 정기 발송에서 임계 초과 부품이 없을 때** — 발송하지 않을지, "이상 없음" 문서를
   낼지, 전 부품 요약본을 낼지. 요약본을 택하면 `alerts`가 부품 단위이므로 별도 양식과
   테이블이 필요하다.
2. **레시피 버전 보관 주체** — 백엔드가 append-only로 보관하지 않으면 `recipe_version`이
   의미를 잃는다. 보장이 어려우면 `production`에 레시피 스냅샷 테이블을 추가한다.
3. **`part_supply` 갱신 주기** — 가격을 이력으로 쌓을지 현재값만 덮어쓸지. 대책서가 발행
   시점 가격을 인쇄하므로, 덮어쓰기로 가면 `alerts` 쪽에 가격도 스냅샷해야 한다.
