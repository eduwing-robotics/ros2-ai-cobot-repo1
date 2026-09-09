# Vision request/pull API — 2026-09-07

**기본 전송 계약: JSON + `02_annotated_report.png` HTTP 개별 조회. ZIP 전송은 제거되었습니다. 대책서 전용 슬롯 확대 PNG는 선택 조회로 추가됩니다.**

이 계약은 기존 `vision_file_receiver` 직접 업로드 패치를 대체합니다. **기존 MainServer 수신 패치는 적용하지 마세요.**

Sequencer → Vision 요청/조회 → Sequencer 응답 → MainServer 보관.
Vision은 DB 쓰기, MainServer 업로드, 생산 상태 변경, 모터 명령을 하지 않습니다.
MainServer가 Sequencer에 조회할 API는 팀원 측 구현 범위입니다.

## 실행 및 준비 조건

S22 정지 감지 화면은 기존대로 실행 상태여야 합니다. 컨베이어 원격 서버와 검사 API는
기존 개별 실행 또는 [통합 실행기](../../docs/CONVEYOR_VISION_SERVER.md)를 사용할 수 있습니다.
통합 실행은 `~/KSMC/run_conveyor_vision_server.sh --monitor-only`이며, 실제 운전은
`--execute --confirm-motion`을 명시합니다. 두 방식은 동시에 실행하지 않습니다.
통합 실행기는 기존 서버가 있으면 건드리지 않고 중복 시작을 거절합니다.
팀원의 주소·토큰·ROS/HTTP 계약에는 변경이 없습니다.
이 노트북은 `config/private/vision_api.token`의 고정 토큰을 실행기가 자동으로 읽습니다.
파일은 Git 제외, 디렉터리700/파일600이며 기존 전달 토큰을 유지합니다.
매번 openssl로 새 토큰을 만들 필요가 없습니다. 다른 PC에는 토큰 파일을 별도로 안전하게
설치해야 합니다. 파일이 없을 때만 KSMC_VISION_API_TOKEN 환경변수를 사용합니다.

기존 개별 API 실행(컨베이어 원격 서버 별도 필요):

```bash
~/KSMC/vision_assembly/run_conveyor_inspection_trigger.sh --host 0.0.0.0 --port 8766
```

기본 주소는 localhost입니다. 외부 바인딩 시 신뢰 LAN/방화벽 또는 TLS 프록시를 사용하세요.
현재 LAN 주소192.168.11.4, 공유기192.168.11.1, wlo1 MAC40:D1:33:FA:16:A8.
**IP 고정은 아직 미완료**: 공유기 DHCP 예약에서 이 MAC에192.168.11.4를 예약해야 합니다.
GoPro 네트워크10.5.5.113은 변경하지 않았습니다.
ROS domain/DDS는 기존 환경 설정을 따릅니다. `/conveyor/moving=false`와
`/vision/conveyor/inspection/stop_trigger=true`가 1초 이내 새 신호이고 0.35초
연속 유지되어야 합니다. 이는 소프트웨어 상태 확인이지 물리 안전 센서 보증이 아닙니다.
도착 신호만으로 촬영하지 않습니다. 기존 도착 자동 촬영과 같은 잠금을 사용하므로
둘을 동시에 실행할 수 없습니다. 기존 방식은 명시적 `--legacy-arrival-trigger`만 허용합니다.

## API

모든 요청: `Authorization: Bearer <token>`.

`POST /api/v1/inspections`, JSON, `Idempotency-Key: <inspection_id>`:

```json
{"inspection_id":"69f7a921-b98d-4fc8-91ac-e23dbe91ac71","job_id":"12345678-1234-5678-1234-567812345678","unit_id":42}
```

UUID 두 개는 Sequencer 발급, unit_id는 양의 정수입니다. 202의 `data.status`는
ACCEPTED/RUNNING 또는 동일 요청의 기존 상태이며 완료를 뜻하지 않습니다.
같은 ID/같은 내용은 재촬영하지 않으며 다른 내용은409. 진행 중 다른 ID는409.
장비 준비 안 됨503, 입력400, 인증401, 없는 검사404.

`GET /api/v1/inspections/{inspection_id}` → `{ "data": {...} }`:
공통 세 ID와 status, 완료 시 result.decision(PASS/FAIL/UNKNOWN), inspected_at,
defects(확정 항목만), findings(오류 의심 포함), slots(25개 슬롯), summary,
image.ready/path/filename/mime_type/size_bytes/sha256.
findings에는 부품 이름·slot_code·primary_defect_name_ko·details와
authority·confirmed_defect가 포함됩니다. 의심 후보를 확정 불량으로 바꾸지 않습니다.
신규 결과에는 선택 필드 `result.diagnostics`가 추가됩니다. 촬영 품질
`capture_quality`, 내부 검사 신호 `evidence_audit`, 실행 불가 검사
`provider_health`, 위치 표시 진단 `pose_display_audit`를 제공합니다.
기존 저장 결과에 이 필드가 없으면 미평가이며 정상으로 해석하지 않습니다.
품질 경고는 UNKNOWN/재촬영 권고이지 확정 불량이나 자동 재촬영 명령이 아닙니다.
엄격한 JSON 파서를 사용한다면 선택 필드를 허용하세요. 주소·토큰·ID·PNG 조회 방식은
같습니다. [진단 필드와 제한사항](../../docs/INSPECTION_QUALITY_AND_DIAGNOSTICS.md).
COMPLETED+UNKNOWN은 검사 완료이지만 생산 합격/불량 확정이 아닙니다.
실행 오류는 FAILED. 결과 자료 준비 실패는 COMPLETED 및 image.ready=false,
result.details_ready=false로 구분합니다. 빈 defects만 보고 PASS로 해석하지 마세요.

`GET /api/v1/inspections/{inspection_id}/image` → image/png,
Content-Disposition: inline; filename="02_annotated_report.png".
Content-Length와 X-Content-SHA256을 제공합니다. 같은 Bearer 인증을 사용합니다.
미준비409, 보관 이미지 해시 불일치409. JSON의 image.path로 다운로드하여 크기·SHA256을
검증하고 JSON과 PNG를 같은 inspection_id로 저장하세요. 압축/해제나 multipart는 없습니다.

순서: POST 수락 → GET 상태 polling → COMPLETED JSON 저장 → image.ready=true일 때
image.path 다운로드 → Sequencer가 MainServer 조회에 JSON·PNG를 제공.
Vision은 MainServer에 직접 전송하지 않습니다.

원본 ROI·개별 히트맵·상세 raw JSON과 전체 metadata는 로컬 package 폴더에만 보관합니다.
새 API 검사에서는 ZIP을 생성하지 않습니다. 수동 오프라인 ZIP 내보내기 기능 및 과거 ZIP은
보존하지만 `/evidence` 경로는404이며 API로 제공하지 않습니다.
과거 ZIP 방식 완료 기록은 재촬영/자동 변환하지 않고 image.ready=false,
error=legacy_zip_record로 반환합니다.

## 재시도·보관·제한

- 결과 조회는 예를 들어 1초 간격으로 하고, HTTP timeout이면 같은 ID를 재조회합니다.
- 실제 재촬영은 새 inspection_id를 발급합니다. UNKNOWN 재촬영 횟수/보류 정책은 Sequencer 소유입니다.
- 실행 제한 기본300초(`--timeout`). 실측 보장 시간이 아닙니다.
- 재시작 시 중단된 요청은 FAILED로 보존하며 자동 재촬영하지 않습니다.
- API 취소 endpoint는 아직 없습니다. 서버 종료는 실행 자식 프로세스를 정리합니다.
- 자료는 로컬 runtime/inspection/api에 저장하고 자동 삭제하지 않습니다. 디스크 보관 정책은 추후 합의합니다.
- 별도 수동 촬영/검사를 동시에 실행하지 마세요. latest 기반 기존 검사기는 모든 수동 진입점과
  아직 통합 잠금을 공유하지 않으므로 운영 중 단독 소유가 필요합니다.
- 현재 모델의 ADVISORY/UNKNOWN 권한은 그대로입니다. 이 API로 확정 PASS 능력이 추가되지 않습니다.
- 실제 Sequencer/S22/ROS 통합과 재부팅·네트워크 장애 시험은 배포 전 필요합니다.
# 2026-09-09 보완 안내

대책서 전용 확대 PNG와 컨베이어 도착 콜백 추가 정보:
[COUNTERMEASURE_V2_UPDATE.md](COUNTERMEASURE_V2_UPDATE.md).
기존 JSON/전체 PNG 조회는 유지됩니다.
Countermeasure image update: prefer the optional `countermeasure_views` entry
whose `slot_code` is `ALL` (full board + numbered findings). Per-slot close-ups
and the default `/image` remain available. See [COUNTERMEASURE_V2_UPDATE.md](COUNTERMEASURE_V2_UPDATE.md).
Latest countermeasure format: `ALL` is now a panel-free 1600x1266 whole-board
evidence photo with numbered finding boxes. Keep reasons and red/amber legend
in the document text, using `rendering.findings`. The v2 picture extent is
2022282x1600200 EMU; remove old cropping and keep the full picture.
