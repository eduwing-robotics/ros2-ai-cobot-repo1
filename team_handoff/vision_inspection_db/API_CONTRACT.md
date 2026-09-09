# Vision Inspection DB API Contract

## 요청

```text
POST /api/v1/vision-inspections
Content-Type: multipart/form-data
Idempotency-Key: <inspection_result.json의 idempotency_key>
X-KSMC-Schema: ksmc.vision-inspection.v1
Authorization: Bearer <token>    # 서버 정책에 따라 선택
```

multipart 항목:

| 필드 | 내용 |
|---|---|
| `metadata` | `inspection_result.json` |
| `image_source_roi` | 촬영된 원본 기판 ROI |
| `image_annotated_report` | 슬롯·오류 후보가 표시된 3단 비교 이미지 |
| `image_candidate_heatmap` | 후보 슬롯에 한정한 PatchCore 히트맵 |
| `image_candidate_heatmap_overlay` | 원본과 히트맵을 합친 이미지 |
| `image_registered_board` | 정합된 기판 원본(있을 때) |
| `image_slot_diagnostic` | 25슬롯 단계별 진단 이미지(있을 때) |
| `image_gpu_pin_debug` | GPU 핀 진단 이미지(있을 때) |
| `raw_hybrid_report` | 추적·감사용 원본 하이브리드 JSON |

성공 응답은 HTTP 2xx면 충분하다. 권장 응답은 다음과 같다.

```json
{
  "accepted": true,
  "inspection_id": "INSP-20260904-120000-123456789A",
  "db_record_id": 1234
}
```

## DB 저장 핵심 필드

- 검사 헤더: `inspection_id`, `production_cycle_id`, `job_id`, `board_id`,
  `recipe_version`, `captured_at`, `overall.decision`, `overall.route`
- 슬롯 결과: `slots[].slot_code`, `part_id`, `decision`, `reason`, `measurements`
- 불량/재검 후보: `findings[]`
- 이미지: 업로드된 파일을 DB 또는 object storage에 저장하고 생성된 URL을 검사
  레코드에 연결한다. `/home/hc/...` 같은 비전 PC 로컬 경로를 URL로 저장하지 않는다.

`inspection_id` 또는 `idempotency_key`에 unique constraint를 둔다. 재전송은 기존
레코드와 이미지에 연결하고 중복 불량 건을 만들지 않는다.

## 불량 대책서 매핑

| 대책서 항목 | JSON 소스 |
|---|---|
| 문서번호 | DB가 `finding_id`를 기준으로 발급 |
| 발행일시 | `captured_at` 또는 DB 접수 시각 |
| 대상 부품 | `findings[].part_name`, `product_code`, `slot_code` |
| 불량 유형 | `primary_defect_code`, `primary_defect_name_ko` |
| 발생 슬롯 | `slot_code` (예: `PM-01`) |
| 자동 분석 | `details`와 `measurements` |
| 검사 이미지 | `source_roi`, `annotated_report`, `candidate_heatmap_overlay` 저장 URL |
| 검사 수량 | 생산 cycle의 검사 건수는 DB가 집계 |
| 불량 수량 | `confirmed_defect=true`만 집계 |

현재 비전 결과는 후보 단계라 `confirmed_defect=false`다. DB 화면에는
`UNKNOWN/재검 필요`로 표시할 수 있지만, 이를 `불량 수량 1` 또는 자동 발행된
불량 대책서로 바꾸면 안 된다.

## 슬롯 코드

조립 레시피 `assembly-r1`과 동일하게 GPU-01, HBM-01~08, PM-01~04,
CAP-01~05, IND-01~02, VRM-01~05를 사용한다. 내부 비전 ID(`ai_gpu`,
`power_module_01`, `smd_capacitor_01` 등)도 함께 보내 추적성을 유지한다.

## 표준 불량 코드

| 비전 후보 | DB 불량 코드 | 한글명 |
|---|---|---|
| `MISSING?` | `COMPONENT_MISSING` | 부품 누락 |
| `POSE?` | `POSITION_ERROR` | 위치 오류 |
| `DIR?` | `DIRECTION_ERROR` | 방향 오류 |
| `SEATING?` | `SEATING_ERROR` | 안착 오류 |
| `PINS?` | `PIN_DEFECT` | 핀 누락 또는 손상 |
| `SURFACE?` | `SURFACE_ANOMALY` | 표면 이상 |

물음표가 붙은 원본 코드는 `ADVISORY_ONLY`임을 뜻한다. DB 표준 코드로 번역되더라도
`authority`, `decision`, `confirmed_defect`를 반드시 함께 확인한다.

