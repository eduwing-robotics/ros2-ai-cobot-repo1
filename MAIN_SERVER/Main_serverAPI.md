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
| `DELETE` | `/api/v1/jobs/{job_id}` | `PENDING` Job 취소 |
| `GET` | `/api/v1/products/{product_id}/quality/slot-rates` | 슬롯별 누적 검사·불량률 조회 |
| `POST` | `/api/v1/assemblies` | 영속 production Job 등록 |
| `GET` | `/api/v1/assemblies/current` | Assembly Sequencer의 현재 또는 최근 실행 snapshot 조회 |

## 공통 응답

성공:

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
  "recipe_version": "assembly-r1"
}
```

- `job_id`는 호출자가 만든 UUID이며 멱등성 key입니다.
- `requested_quantity`는 검사 PASS 목표 수량인 양의 정수입니다.
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

`DELETE /api/v1/jobs/{job_id}`는 아직 claim되지 않은 `PENDING` Job만 취소합니다. 이미 Sequencer가 claim한 Job은 `409 job_not_cancellable`을 반환합니다.

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
