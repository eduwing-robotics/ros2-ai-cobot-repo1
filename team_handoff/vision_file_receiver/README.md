# Vision 파일 수신 API 전달 패키지

> SUPERSEDED / 적용 금지 (2026-09-07): 직접 업로드 정책이 취소되었습니다.
> 새 계약은 ../vision_sequencer_api/README.md 를 사용하세요. 아래는 과거 기록입니다.

## 범위

기준 브랜치 `Main_Server&DT`, 커밋 `1c1c56519a294a0f15a044bc0629e3a1d823b9f2`.
`mainserver_file_receiver.patch`는 기존 `MAIN_SERVER/server.py`와
`MAIN_SERVER/Main_serverAPI.md`만 변경합니다. 원격 저장소에 push하지 않았습니다.
DB migration, DB 쓰기 권한, Sequencer 생산 상태, 대책서 자동 발행은 변경하지 않습니다.

## 팀원 적용

작업 중인 변경을 먼저 보존하고 저장소 루트에서 실행합니다. 최신 파일과 충돌하면
강제 적용하지 말고 두 파일을 검토하여 병합하세요.

```bash
git apply --check /전달폴더/mainserver_file_receiver.patch
git apply /전달폴더/mainserver_file_receiver.patch
```

기존 MainServer 실행 환경에 다음을 추가한 뒤 기존 방식으로 재실행합니다.

```bash
export VISION_INGEST_ROOT=/원하는/절대경로/vision_receipts
read -rs -p 'Vision API token: ' VISION_INGEST_TOKEN
export VISION_INGEST_TOKEN
```

토큰은 충분히 긴 임의 문자열로 정해 Vision 담당자에게 안전하게 전달합니다.
코드·Git·채팅 예제에 실제 토큰을 넣지 마세요. 기존 MainServer의 DB 환경 설정은
서버 시작에 여전히 필요하지만, 새 수신 핸들러는 DB에 접근하지 않습니다.
한 저장 경로는 MainServer 한 프로세스만 사용합니다.

수신 주소: `POST http(s)://서버주소:기존포트/api/v1/vision/inspections`
같은 프로세스의 기존 HTTP 서버에 경로 하나를 추가하며 별도 포트는 열지 않습니다.
외부 공개 금지. 신뢰할 수 있는 격리 LAN 또는 HTTPS reverse proxy를 사용하세요.
프록시에서 업로드 크기와 동시 요청 수를 제한하세요. 앱 본문 제한64MiB.

## 계약

- Bearer 인증, `Idempotency-Key`, multipart/form-data 사용.
- `metadata`, `raw_hybrid_report`, 각 `image_<role>` 파일 필드.
- Vision 기존 `ksmc.vision-inspection.v1` payload 사용, `unit_id`는 양의 정수/null.
- `job_id`는 UUID/null. ID는 저장만 하며 DB의 실제 Unit과 일치하는지 검증하지 않습니다.
- 이미지 역할·상대 경로·크기·SHA256·PNG/JPEG 시그니처 검사. 전체 이미지 디코딩 검증은 하지 않습니다.
- 동일 키·내용 재전송은 중복 성공, 같은 키·다른 내용409. 저장은 private 임시 폴더 후 rename.
- 200 응답 `data`: `stored=true`, `inspection_id`, `idempotency_key`,
  `duplicate`, `production_applied=false`, `binding_status=UNBOUND/UNVERIFIED`.
- UNKNOWN 그대로 저장. 후보가 있다는 이유로 불량대책서를 발행하지 않습니다.
- 저장 경로는 `<VISION_INGEST_ROOT>/<idempotency_key>/`.
  원본 JSON, 이미지, receipt.json을 보관합니다. Linux 파일/디렉터리 fsync 사용.
- 파일 보관기간·디스크 용량 경보는 서버 운영자가 관리해야 합니다.
  프로세스 강제 종료 후 `.receiving-*` 임시 폴더가 남으면 실행 중 업로드가 아닌지 확인 후 정리합니다.

## Vision PC 자동 흐름

현재 도착 트리거 -> 정지 후 대기 -> S22 촬영 -> 최신 하이브리드25슬롯 검사 ->
로컬 패키지 -> HTTP 파일 저장. 컨베이어 원격 서버는 이동 요청을 담당하고,
자동 검사 트리거는 `run_s22_conveyor_auto_inspection.sh`가 담당합니다.
원격 서버만 실행해서는 자동 촬영/검사/전송이 시작되지 않습니다.

우리 PC에 반영한 코드에서 전송은 기본 OFF입니다. 서버 준비 후:

```bash
export KSMC_VISION_EXPORT=1
export KSMC_VISION_ENDPOINT='http://팀원IP:포트/api/v1/vision/inspections'
read -rs -p 'Vision API token: ' KSMC_DB_API_TOKEN
export KSMC_DB_API_TOKEN
~/KSMC/run_s22_conveyor_auto_inspection.sh
```

기존 카메라/트리거와 중복 실행하지 마세요. 이 명령 자체는 컨베이어 이동 명령을 보내지 않습니다.
검사 위치 감지와 정지 안정성은 별도 실제 설비 검증이 필요합니다.
전송하지 않고 패키지만 만들려면 `KSMC_VISION_ENDPOINT`를 unset합니다.

Sequencer가 ID 전달을 구현하기 전에는 `KSMC_VISION_CONTEXT_FILE`을 설정하지 않습니다.
미연결 자료로 저장하는 것이 정상입니다. 향후 컨텍스트 JSON에 `job_id`, `unit_id`,
`board_id`, `production_cycle_id`를 공급하면 촬영 전에 스냅샷을 읽습니다.
생산 건별 갱신·수명·도착 이벤트 연계는 아직 구현되지 않았으므로, 정적 파일을 여러
생산 건에 재사용하면 안 됩니다. 서버는 어떤 ID도 생산 상태에 자동 반영하지 않습니다.

검사 결과와 전송 상태는 `runtime/inspection/auto_inspection_latest.json`에서 분리됩니다.
업로드 실패 시 판정을 바꾸지 않고 `delivery.status=PENDING_RETRY`로 기록합니다.
자동 네트워크 재시도 데몬은 없으며, 패키지는 `runtime/inspection/db_outbox`에 남습니다.
실패 당시 이벤트의 정확한 report 경로와 동일한 ID 인자로 exporter를 다시 실행해
동일 패키지를 재전송합니다. 재촬영하지 말고, latest가 다른 기판으로 바뀌었는지 주의하세요.

```bash
python3 ~/KSMC/vision_assembly/integration/export_inspection_result.py \
  --report /실패당시/정확한/hybrid_report.json \
  --endpoint "$KSMC_VISION_ENDPOINT"
```

ID를 지정했던 요청이면 `--job-id UUID --unit-id 정수` 등 원래 값도 동일하게 지정합니다.

## 검증 및 제한

`test_file_receiver.py`는 DB/ROS 모듈을 대체하여 수신부만 검사합니다.

```bash
MAIN_SERVER_SOURCE=MAIN_SERVER/server.py python3 -m pytest /전달폴더/test_file_receiver.py -q
```

인증, 저장, 중복/충돌, 경로 이탈, 해시 불일치, 동시 중복, 저장 실패 및
Vision 실제 multipart 송신 코드와 localhost 왕복을 확인했습니다.
팀원 DB·서버 실배포·Unity·Sequencer·실제 컨베이어 연동은 미검증입니다.
이 변경은 자료 보관 단계이며, 생산 결과 확정과 불량대책서 자동 입력/발행 연결은 후속 단계입니다.
