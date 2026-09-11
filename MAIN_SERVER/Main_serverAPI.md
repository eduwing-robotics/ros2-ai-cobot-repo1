# MainServer HTTP API

이 문서는 `server.py`가 구현한 public HTTP API의 단일 registry입니다. Route를 변경할 때 코드와 이 문서를 같은 변경에서 갱신합니다. `test_server.py`는 method·path 순서와 중복을 검사합니다.

## Registry

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | DB 연결과 서버 상태 조회 |
| `GET` | `/api/v1/products` | 제품과 생산 가능 수량 조회 |
| `GET` | `/api/v1/products/{product_id}` | 제품과 슬롯·부품 구성 조회 |
| `GET` | `/api/v1/products/{product_id}/requirements?quantity={quantity}` | 목표 수량의 필요 부품·재고·부족량 조회 |
| `GET` | `/api/v1/parts/{part_id}` | 부품 정보와 재고 조회 |
| `GET` | `/api/v1/jobs?status={status}&limit={limit}` | 실행 queue와 최근 Job 조회 |
| `GET` | `/api/v1/jobs/{job_id}` | Job 진행 상태 조회 |
| `GET` | `/api/v1/jobs/{job_id}/units` | Unit·검사·불량 조회 |
| `GET` | `/api/v1/units/{unit_id}/inspection/image` | 보관된 검사 PNG 조회 |
| `DELETE` | `/api/v1/jobs/{job_id}` | `PENDING` Job 취소 |
| `GET` | `/api/v1/products/{product_id}/quality/slot-rates` | 슬롯별 누적 검사·불량률 조회 |
| `GET` | `/api/v1/products/{product_id}/quality/defect-reports?slot_code={slot_code}` | 확정 불량의 로컬 대책서 목록 |
| `GET` | `/api/v1/defect-reports/{unit_defect_id}/file` | 생성된 XLSX 다운로드 |
| `POST` | `/api/v1/assemblies` | 영속 production Job 등록 |
| `GET` | `/api/v1/assemblies/current` | Assembly Sequencer의 현재 또는 최근 실행 snapshot 조회 |

## 환경 일치 계약

health 외 모든 요청은 `X-Runtime-Mode: mock` 또는 `X-Runtime-Mode: real` 헤더 하나를
포함합니다. 시작 모드와 다르거나 누락·중복되면 DB 작업 전에
`409 runtime_mode_mismatch`로 거부합니다. health의 `data.runtime_mode`는 서버 모드이며
DB 환경 검증도 통과해야 정상 응답합니다. 시작 후 모드 변경은 금지합니다.
Sequencer 모드 불일치·누락은 `503 assembly_unavailable`, DB 환경 불일치·누락은
`503 database_unavailable`입니다. 시작 시 DB 검증 실패는 HTTP 수신 전에 종료합니다.

## 공통 응답

JSON 성공:

```json
{"data": {}}
```

실패:

```json
{"error": {"code": "invalid_request", "message": "..."}}
```

입력 형식이 잘못되면 `400`, 리소스가 없으면 `404`, 현재 상태와 충돌하면 `409`, DB나 조립 상태 제공자가 응답할 수 없으면 `503`, 분류되지 않은 서버 오류는 `500`을 반환합니다.

## 조회

`GET /api/v1/jobs`의 `limit`은 1~50이며 기본값은 12입니다. `status`를 생략하면 `RUNNING`, `PENDING`, 최근 terminal Job 순으로 반환합니다.

조회 endpoint는 production 상태를 전이하지 않습니다. `GET /api/v1/assemblies/current`만 Assembly Sequencer 상태 service를 조회하며 저장된 Job을 변경하지 않습니다.

## Job 등록

`POST /api/v1/assemblies` 요청:

```json
{
  "command": "start",
  "job_id": "12345678-1234-5678-1234-567812345678",
  "product_code": "HBM-ACCELERATOR-PACKAGE-BOARD",
  "product_version": "hbm-pkg-r1",
  "requested_quantity": 1,
  "requested_by": "홍길동",
  "recipe_version": "assembly-r1"
}
```

- `job_id`는 호출자가 만든 UUID이며 멱등성 key입니다.
- `requested_quantity`는 검사 PASS 목표 수량인 양의 정수입니다. `completed_quantity`와 진행률은 전체 workflow가 끝난 `COMPLETED`·`PASS` Unit만 집계합니다.
- 같은 `job_id`와 같은 내용은 기존 Job 상태를 반환합니다.
- 같은 `job_id`에 다른 내용을 사용하면 `409 duplicate_request`입니다.
- 좌표와 레시피 본문은 이 API가 받거나 저장하지 않습니다.

성공 응답은 `202`입니다.

```json
{
  "data": {
    "accepted": true,
    "job_id": "12345678-1234-5678-1234-567812345678",
    "status": "PENDING"
  }
}
```

`accepted=true`는 PostgreSQL에 Job이 영속화됐다는 뜻이며 Sequencer나 로봇의 실행 수락·완료가 아닙니다.

Mock에서 필요한 runtime 좌표는 이 HTTP API가 아니라 [Assembly Sequencer ROS API](../ASSEMBLY_SEQUENCER/API.md)로 같은 `job_id`와 함께 전달합니다.

## Job 취소

`DELETE /api/v1/jobs/{job_id}`는 아직 claim되지 않은 `PENDING` Job만 취소합니다. 이는 요청 계층의 대기 요청 철회이며 Sequencer나 설비를 호출하지 않습니다. DB의 제한된 원자 연산이 Sequencer claim과의 경합에서 하나만 성공하게 하며, 이미 claim한 Job은 `409 job_not_cancellable`을 반환합니다.

## 오류 코드

| HTTP | Code | Meaning |
|---|---|---|
| `400` | `invalid_request` | 요청·경로·query 형식 오류 |
| `404` | `not_found` | 요청한 production 리소스 없음 |
| `409` | `duplicate_request` | 같은 Job UUID에 다른 요청 내용 사용 |
| `409` | `job_not_cancellable` | 취소할 수 없는 Job 상태 |
| `503` | `database_unavailable` | PostgreSQL 조회·기록 불가 |
| `503` | `datasheet_inconsistent` | DB 부품과 데이터시트 계약 불일치 |
| `503` | `assembly_unavailable` | Assembly Sequencer 상태 응답 불가 |
| `500` | `internal_error` | 분류되지 않은 서버 오류 |


## 보관 검사 결과

`GET /api/v1/jobs/{job_id}/units`는 기존 Unit 필드와 확정 `defects`를 유지합니다.
검사 전체 슬롯 행 중 `defect_type IS NOT NULL`만 확정 불량으로 반환하고 집계합니다.
`UNKNOWN`은 검사 완료·판정 보류이며 PASS 수량과 불량률 분모에서 제외합니다.

추가 응답 필드:
- `inspection`: 보관된 Vision `data` 객체. `result.slots`의 각 항목에 DB `unit_defect_id`가 포함됩니다.
  `result.findings`의 의심 항목과 확정 여부·authority는 원래 의미를 유지합니다.
- `inspection_error`: 자료 누락·UID 불일치 시 오류 설명. 정상 또는 기존 샘플 기록은 null입니다.
- `inspection_image_url`: 같은 MainServer의 `/api/v1/units/{unit_id}/inspection/image` 상대경로 또는 null입니다.

이미지 endpoint는 기존 `X-Runtime-Mode` 검증을 적용하며 `image/png` 바이너리를 반환합니다.
`Content-Length`, `X-Content-SHA256`, `Content-Disposition: inline; filename="02_annotated_report.png"`를 제공합니다.
검사 기록이 없으면 404, 파일 미준비·크기·해시·UID 불일치면 `409 inspection_unavailable`입니다.
클라이언트에서 임의 파일 경로나 Vision 인증 토큰을 전달받지 않습니다.


## 로컬 대책서 조회

대책서 목록은 제품의 확정 FAIL·`defect_type IS NOT NULL` 기록만 반환합니다.
선택적 `slot_code`는 한 번만 지정할 수 있으며 빈 값은 허용하지 않습니다.
각 항목은 `unit_defect_id`, `unit_id`, `job_id`, `inspected_at`, `slot_code`, `part_id`,
`defect_type`, `delivery_status`, `sent_at`, `report_ready`, `filename`, `file_url`을 포함합니다.
`report_ready`는 로컬 XLSX 존재 여부이며 이메일 상태와 독립적입니다.
로컬 생성은 이메일 발송 상태를 변경하지 않습니다. `file_url`은 준비된 문서에만 제공됩니다.

파일 endpoint는 `X-Runtime-Mode` 검증 후 XLSX 바이너리를 attachment로 반환합니다.
`Content-Length`와 `X-Content-SHA256`을 제공하며 최대 25 MiB입니다.
확정 불량이 없으면 404, 문서 미준비·허용 루트 이탈·잘못된 파일이면
`409 report_unavailable`입니다. 조회와 다운로드는 문서 생성·이메일 발송을 하지 않습니다.

### Job 요청자

Job 생성의 선택적 `requested_by`는 요청자 이름·식별자이며 관리자 인증 정보가 아닙니다.
지정할 때는 앞뒤 공백 제거 후 1~128자 문자열이어야 합니다. Job에 한 번 저장하고
상세·목록 조회에서도 반환하며, 같은 UUID로 다른 요청자를 제출하면 `409 duplicate_request`입니다.
미지정 자동 호출과 과거 Job은 `null`로 남기며 실제 요청자를 추정하지 않습니다.
Unity 작업 등록 화면은 요청자 입력을 필수로 받습니다. Unit에 요청자를 중복 저장하지 않습니다.

`GET /api/v1/jobs?status=PAUSED`는 검사 불량으로 다음 생산이 차단된 Job을 조회합니다.
해당 상태는 Sequencer가 소유하며 HTTP Job 등록이나 대기 Job 삭제 API로 재개하지 않습니다.
기존 Sequencer resume/cancel 제어를 사용합니다.

Unit 조회의 `defects[]`는 해당 불량의 `delivery_status`와 `sent_at`을 포함합니다. 발송 기록이 없으면 null이며, 성공으로 추정하지 않습니다.
