# KSMC 비전 검사 → DB 인수인계

기준일: 2026-09-04
검사 원본: S22 독립형 25슬롯 하이브리드 검사

비전 담당자는 검사 후 **JSON 1개와 증거 이미지 묶음만 전송**한다. DB 담당자는
판정을 새로 계산하지 않고 JSON을 저장하며, 확정 불량일 때만 불량 대책서에
연결한다.

## 비전 담당 실행

먼저 현재 기판을 촬영하고 검사한다.

```bash
~/KSMC/run_s22_live_hybrid_inspection.sh
```

그 결과를 DB 전달용 ZIP으로 만든다. 생산 사이클·작업·기판 ID는 DB/Main
Server가 사용하는 실제 값으로 넣는다.

```bash
~/KSMC/run_export_latest_inspection_for_db.sh \
  --production-cycle-id CYCLE-20260904-0001 \
  --job-id 22 \
  --board-id PCB-0001
```

생성물:

```text
runtime/inspection/db_outbox/inspection_result_latest.json
runtime/inspection/db_outbox/inspection_package_latest.zip
```

DB HTTP 주소가 정해지면 같은 실행기에 `--endpoint`만 붙인다.

```bash
export KSMC_DB_API_TOKEN='DB 담당자가 발급한 토큰'
~/KSMC/run_export_latest_inspection_for_db.sh \
  --production-cycle-id CYCLE-20260904-0001 \
  --job-id 22 \
  --board-id PCB-0001 \
  --endpoint http://DB_SERVER:PORT/api/v1/vision-inspections
```

전송 실패 시 ZIP과 폴더는 outbox에 그대로 남는다. 같은 결과의 중복 저장은 HTTP
`Idempotency-Key`와 JSON의 `idempotency_key`로 차단한다.

## 판정 취급

- 현재 검사 provider는 `ADVISORY_ONLY`다.
- `MISSING?`, `POSE?`, `DIR?` 등의 표시는 불량 후보이지 확정 불량이 아니다.
- 따라서 현재 JSON은 `overall.decision=UNKNOWN`, 각 후보는
  `confirmed_defect=false`로 전달된다.
- DB는 `formal_defect_report_allowed=false`인 결과로 불량 대책서를 자동 발행하면
  안 된다. 재촬영/보류 기록으로 저장한다.
- 향후 검증된 authoritative stage가 `FAIL`을 내고
  `formal_defect_report_allowed=true`가 된 결과만 자동 대책서 생성 대상으로 쓴다.

세부 HTTP 필드와 문서 매핑은 [API_CONTRACT.md](API_CONTRACT.md)를 따르고,
최소 예시는 `inspection_result.example.json`에서 확인한다.
