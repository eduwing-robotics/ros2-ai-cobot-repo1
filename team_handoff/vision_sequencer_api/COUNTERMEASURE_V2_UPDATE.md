> **2026-09-11: 현재 전송은 ROS 2입니다. [새 ROS 계약](ROS_API.md)을 적용하세요. 아래 HTTP 설명은 이전 계약으로 보존합니다.**

# 2026-09-09 대책서 이미지·도착 콜백 보완

## 대책서 이미지

`불량대책서_샘플_종결본_v2.xlsx` 확인: 대책서 첫 장 그림이 약212×168px이며,
전체 검사 화면의 오른쪽 보드 부분을 srcRect로 잘라 배치합니다. 작은 SMD는
이 크기에서 판별하기 어렵습니다. 기존 전체 검사 PNG와 JSON은 유지합니다.

신규 검사 완료 응답에는 선택용 `data.image.countermeasure_views`가 추가됩니다.
각 항목: `slot_code`, `path`, `filename`, `sha256`, `size_bytes`, `rendering`.

```text
GET /api/v1/inspections/{inspection_id}/image
    기존 전체 검사 PNG — 변경 없음

GET /api/v1/inspections/{inspection_id}/image?view=countermeasure&slot=CAP-01
    해당 슬롯의 대책서 전용 PNG (1200×950)
```

두 요청 모두 기존 Bearer 인증을 사용합니다. Sequencer가 Vision에서 가져오고
MainServer는 Sequencer를 통해 받습니다. Vision→MainServer 업로드/DB 접근은 없습니다.
기존 완료 건은 불변이므로 새 이미지가 없으면404입니다. 신규 검사부터 자동 생성합니다.
지원 여부는 countermeasure_views와 countermeasure_status로 확인하세요.
이미지가 준비되지 않으면 기존 전체 PNG만 제공하며 판정을 변경하지 않습니다.

### XLSX 적용

- 첫 장 G15 영역에는 해당 불량/후보 slot_code의 전용 PNG를 넣습니다.
- **기존 srcRect(오른쪽 1/3 자르기)를 제거하고 전체 이미지 비율 유지로 삽입합니다.**
- `검사 근거` 시트에는 기존 `/image` 전체 PNG를 그대로 사용합니다.
- 보드 위치 안내 + 부품 확대 + 슬롯 번호 + 미확정/확정 문구가 들어 있습니다.
- 테두리는 검사 위치 표시이며 실제 크랙/핀 결손 마스크가 아닙니다.
- 원본 픽셀 확대일 뿐 새 디테일을 생성하지 않습니다. 열지도는 전체 검사 PNG에 유지합니다.
- 여러 슬롯이면 대책서 대상 슬롯에 맞춰 선택합니다. 첫 번째 그림을 모든 부품에 재사용하지 않습니다.
- UNKNOWN은 미확정 후보입니다. 문서 종결·원인·조치 완료를 Vision이 작성하지 않습니다.

### 제공 정보 대응

| 양식 | Vision 정보 |
|---|---|
| C6 대상 부품 | finding.part_name / product_code / manufacturer 및 basis |
| C7 발생 대상 | job_id / unit_id / finding.slot_code / finding_id |
| C8 검사 일시 | result.inspected_at (촬영 시각은 captured_at) |
| C9 유형 | primary_defect_name_ko / primary_defect_code |
| A15 확인 사실 | finding.details와 measurements; 원인 추정으로 바꾸지 않음 |
| C17 판정 근거 | decision / authority / confirmed_defect |
| G15 이미지 | 해당 countermeasure_views 항목 |

단가·대체품·구매 추적·원인·조치·효과확인·종결은 담당 부서/서버의 책임입니다.
샘플의 미확인 모델명과 가상 대체품을 실제 납품 정보로 확정하지 않습니다.

## 도착 콜백

기존 `/conveyor/state`와 서비스 이름/schema_version=1은 유지합니다.
이동 서비스 success는 수락이며 완료 콜백이 아닙니다.
`target_station`은 도착 시 기존대로 null입니다. 그것으로 도착 대상을 필터링하지 마세요.

신규 수락 응답과 상태의 `motion_id`를 연결하고, 상태가 ASSEMBLY_STOP/INSPECTION_STOP,
moving=false일 때 `arrival.station`, `arrival.motion_id`를 확인합니다.
완료 상태는 10Hz로 유지되며 동일 motion_id는 한 번만 처리합니다.
reset/fault/manual stop은 도착 성공이 아닙니다. 서버 재시작은 새 식별자를 사용합니다.
FAULT/MANUAL_STOP 또는 명시적인 안전 reason은 실패/보류 경로로 처리해야 하며,
도착 콜백만 무한 대기하지 마세요. 상태 수신 간격만으로 fault를 만들지 않고,
safety reason은 기존 상태 JSON에 남습니다.
이는 비전 트리거와 정지 명령 근거이며 엔코더 기반 실제 정지 확인은 아닙니다.

Unity 예제에는 AssemblyArrived / InspectionArrived 이벤트를 추가했습니다.
Python 예제도 상태 변화만이 아닌 motion_id로 중복을 제거합니다.
파일: `team_handoff/conveyor_remote_api/unity/ConveyorRosClient.cs`,
`team_handoff/conveyor_remote_api/db/conveyor_event_subscriber.py`.
받는 쪽은 자신의 대기 중 요청 motion_id와 일치하는지 검증해야 합니다.
재접속으로 오래된 정지 상태를 수신했다고 새 작업을 자동 시작하면 안 됩니다.

현장 확인: 도착 토픽은 보였지만 `/conveyor/state` 발행자와 `/conveyor/*` 서비스는
없었습니다. 컨베이어 원격 서버가 보이지 않는 상태에서는 완료 통지가 나올 수 없습니다.
코드만 수정했으며 서버 자동 시작/안전 인터록 해제/설비 이동은 하지 않았습니다.
# Whole-board overview update (2026-09-09)

For the countermeasure sheet, prefer `image.countermeasure_views` with
`slot_code: "ALL"`. Fetch its authenticated `path`:
`GET /api/v1/inspections/{inspection_id}/image?view=countermeasure&slot=ALL`.
This PNG shows the full registered board, numbered finding boxes, and a matching
slot/reason list. Red means authoritative confirmed defect; amber means advisory
candidate. Multiple reasons for the same slot are listed together. Normal slots
are not outlined. No heatmap is invented from a classifier decision.

The normal `/image` endpoint and per-slot zoom views remain unchanged. Older
completed records may lack ALL; fall back to the original `/image`. Only newly
prepared results get the new view. Use its returned checksum, fit the whole PNG
without the old spreadsheet crop, preserve its aspect ratio, and enlarge the
sheet's picture area if printed text is too small. MainServer still obtains
evidence through Sequencer. No API address, token, motion or verdict change.
# Current image format: panel-free worksheet evidence (2026-09-09)

This supersedes the numbered sidebar layout described below. Select the same
`slot_code: ALL` view. It is now a 1600x1266 **photo only**, with finding boxes
and numbers, without a header, side panel, legend or normal-slot annotations.
Preserve the v2 picture anchor and its exact extent `cx=2022282, cy=1600200` EMU
(approximately 212x168 screen pixels at 96 DPI); remove the previous `srcRect`
crop and fit the complete PNG. Its ratio matches the picture area within rounding.
Do not retain the old 2400x1500 overview layout or crop out the board.

Place legend/reasons in the worksheet's existing text fields, not in the image:
red = confirmed authoritative defect; amber = unverified candidate. Number-to-slot
and reason mapping is in the selected view's `rendering.findings`. No boxes does
not imply PASS; use result.decision. Small physical print size still limits fine
detail; the original full-resolution PNG and optional per-slot views remain available.
API routes, authentication and default `/image` are unchanged. New results use
this format after the inspection service loads the updated code; existing stored
results remain immutable. Send this file and README.md together.
