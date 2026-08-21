# 남은 작업

현재 Mock MVP는 고정 레시피, 수량 1개, 동시 작업 1건과 callback 시각화까지만 구현한다.
아래 항목은 MVP에 넣지 않고 실제 요구가 생기는 순서대로 추가한다.

## RUN 하단 패널 — 조립 진행 표시 (진행 중)

옛 하단 8스텝 레일(`READY → DETECT → APPROACH → PICK → TRANSFER → PLACE → INSPECT → RETURN`)은
**범주 오류였다.** `Recipe.md`의 스텝 정의는 **1 스텝 = 부품 하나를 슬롯 하나에 올리는 것**이고
approach/insert/retract 는 그 한 스텝 **안**의 모션이다. 레일은 한 스텝의 속을 작업 전체의
진행으로 착각해 그린 그림이었다.

실제 구조는 **25 슬롯 / 6 부품 타입**이다 — HBM 8 · PM 4 · GPU 1 · CAP 5 · IND 2 · VRM 5.
`unit_defects` 가 슬롯 단위로 기록되므로 화면도 슬롯을 단위로 삼아야 검사·품질과 어휘가 맞는다.
`UI.md:341` 이 "SLOT PROGRESS 8칸을 스텝 레일과 중복이라 뺐다"고 적은 것은 **거꾸로 뺀 것이다.**
남길 것이 슬롯 진행이고 뺄 것이 8단계 레일이었다.

| 단계 | 내용 | 상태 |
|---|---|---|
| 0 | `AssemblyProgressFrame` + `AssemblyProgressManager` — Mock 피드백을 공용 상태로. `RobotStatusManager` 와 같은 자리·같은 모양. Real 도 같은 곳에 쓰도록 `IRobotModMatser.Initialize` 에 주입 인자 추가 | 코드 · 씬 부착 완료 · 실행 검증 남음 |
| 1 | slot_code 정합 가드 — `ApplyPlaced` 에서 씬 슬롯 이름과 피드백 `slot_code` 대조, 불일치 시 `LogError` | 코드 완료 · 실행 검증 남음 |
| 2 | **하단 패널: 8스텝 레일 → 부품 타입별 진행 막대 + 현재 부품 한 줄** (`HBM ■■■■■■■■ 8/8 … 12 / 25`) | 완료 |
| 3 | JOB 패널 유닛 틱 10개 → **기판 슬롯 맵** (슬롯 Transform 실좌표) | **보류** — 자리를 VISION 에 넘겼다. 넣으려면 배치부터 다시 |
| 4 | INSPECT · QUALITY 가 같은 슬롯 맵 컴포넌트 재사용 | 미착수 |

- [x] 0단계 — 씬에 `AssemblyProgressManager` 부착 후 씬 저장 (FR5 · FR5_Save 두 곳, `RequireComponent` 자동 부착)
- [ ] 0·1단계 — **Mock 조립 1회 실행** 실측. 25 스텝 동안 진행 프레임이 채워지는지, slot_code 가드가 조용한지. ROS 브리지(`mock_sim.py` · ROS-TCP-Endpoint)가 떠 있어야 한다 — 아직 못 함
- [x] 2단계 — `FR5Run.uxml` `progress-panel` + `FR5RunBinder.RefreshAssembly` 로 교체. JOB 패널의 phase · 슬롯 줄도 같은 프레임을 읽는다 (Play 모드에서 프레임 주입으로 검증)
- [x] JOB 패널 수량 픽션 제거 + VISION 확대 — 완료 수량 `6/10` · 유닛 틱 10칸 · 잔여·완료 예정 · OK/NG 를 뺐다(MVP 수량 1대라 채울 데이터가 없다). JOB 520→368, VISION 264→368, 프레임 338×254(4:3 정확히). 남은 72px 은 3D 우측이 가져간다
- [ ] 수량 2개 이상·작업 큐가 생기면 JOB 패널의 수량 표시를 되돌린다 (상단 바의 `6 / 10` 은 아직 샘플로 남아 있다)
- [ ] 3단계 — JOB 패널 `unit-ticks` 를 기판 슬롯 맵으로 교체 (**보류** — 좌측 ROBOT 패널의 빈 자리는 Mock 전용이고, JOB 자리는 VISION 이 가져갔다)
- [ ] 4단계 — 슬롯 맵을 INSPECT · QUALITY 에서 재사용

**왜 0단계가 먼저인가.** 2~4단계가 표시할 값이 전부 `MockAsyncPlay` 의 private 필드
(`expectedStepCount` · `lastPlacedStepOrder` · `heldPartId` · `heldSlotCode`) 안에 있다. 바인더가
Mock 구현을 직접 참조하는 지름길을 타면 Real 조립 노드가 붙는 날 UI를 다시 쓴다. 지금 SAFETY·REAL
블록이 "Mock 에서 죽은 화면"인 것과 정확히 대칭인 실수다.

```
RobotStatusMaster  ─ RobotStatusManager      ─ RobotStatusFrame      (관절 · TCP · 안전)
AssemblyMaster     ─ AssemblyProgressManager ─ AssemblyProgressFrame (조립 진행)
```

**폐기된 항목.** 원안의 "`ItemManger` 에 `slot_code` 필드를 추가해 관측에 실어 보낸다"는
`API.md:93`("Unity 는 `slot_code` 를 보내지 않는다")과 충돌한다. 현재 방식 — 슬롯 Transform 이름이
곧 `slot_code`, 배열 순서가 곧 YAML `order` — 이 계약 안에서 같은 목적을 이미 달성한다.
대신 ROS 는 `part_id` 만 검증하고 `slot_code` 는 검증하지 않으므로, 같은 타입 8개는 어떤 순열이든
통과한다. 1단계 가드가 그 정합성을 지키는 유일한 방어선이다.

## Architecture 목표 전환

- [ ] 장시간 작업, 취소 또는 Real 연동이 필요할 때 임시 Service/Topic 계약을 `AssemblyJob` Action으로 교체
- [ ] JSON 계약의 검증·버전 호환 문제가 실제로 생길 때만 typed feedback·상태 메시지 추가
- [ ] 수량 2개 이상과 작업 큐 지원
- [ ] 작업 취소와 안전 정지 정책 구현
- [ ] Unity 재접속용 현재 상태 조회 Service와 held/placed 부품 snapshot 복원
- [ ] 조립 노드 재시작 시 진행 중 Unit을 재개할지 `FAILED`로 정리할지 확정하고 구현
- [ ] `production` DB의 Job·Unit·재고 차감 트랜잭션 연결
- [ ] 검사 실행, 판정과 불량 슬롯 기록 연결
- [ ] `RealAyncPlay`에서 Real 조립 노드 통신과 실제 완료 판정 구현
- [ ] `mock-r1` Pose와 TCP→wrist offset을 SampleScene에 보정하고 callback 시각화 스냅 제거
- [ ] `Recipe.md`의 전체 스키마와 `tools.yaml`·`frames.yaml` 로드 검증
- [ ] 레시피 생성기와 생성 시 DB 슬롯 대조 검증 구현

> Unity는 이후 DB가 생겨도 레시피 본문이나 조립 순서를 직접 읽지 않는다. ROS2 조립 노드가
> 레시피와 DB 상태를 소유하고 Unity에는 작업 결과와 복구 상태만 제공한다.

## UI 샘플 데이터 제거 (2026-08-21)

DB 연결이 임박해 샘플을 전부 걷어냈다. 조회 경로가 없는 자리는 `Assets/UI/FR5EmptyState.cs` 가
`연결 없음` + 필요한 조회 이름을 적는다. 색은 `--c-warn` — 붉은색은 불량·비상정지에 남긴다.

- [x] RUN — 작업 id · 제품 · 레시피 · 상단 수량/사이클 · 이벤트 로그
- [x] REQUEST — 제품 목록 · 재고 · 슬롯 구성 · 예상 소요 · 초록 `VERSION MATCH` 칩(→ `노드가 판정`)
- [x] INSPECT — 판정 · 항목별 결과 · 불량 슬롯 · 유닛 목록 · 고정 검출 박스(`BOARD 98.4%`)
- [x] QUALITY — 슬롯·부품 불량률 · 레시피 A/B · 대책서 · 필터 기본값 · `샘플 데이터` 배지
- [x] REQUEST 인터록에서 `재고 충분` · `recipe_version 일치` 제거 — Unity 가 판정하지 못한다.
      안내 줄로 내리고 START 는 연결·유휴·MOCK 세 조건으로만 막는다
- [x] **레거시 HUD 삭제** — `FR5Hud.prefab` · `FR5Dashboard.uxml` · `FR5Dashboard.uss` ·
      `FR5DashboardBinder.cs` 와 씬의 `FR5 HUD` 오브젝트를 지웠다. `UxmlBindingEditor` 의
      전용 CustomEditor 도 같이 뺐다. `FR5DashboardPanelSettings.asset` 은 5페이지가 공유하므로 남긴다
- [ ] `VisionDetector` 는 레거시 오브젝트에만 붙어 있어 씬에서 사라졌다(스크립트는 남아 있다).
      비전 검출 연동을 시작할 때 살아 있는 오브젝트에 다시 붙인다 — 붙이는 순간 ROS 구독이 살아난다
- [ ] `FR5ViewControls.cs` 는 남겼지만 이제 씬에 인스턴스가 없다. RUN 트윈 창의 뷰 프리셋을
      만들 때 재사용한다 (조회 이름을 Inspector 로 받는 구조라 그대로 쓸 수 있다)
- [ ] `Assets/UI/FR5_Unity_HUD_Penpot_Mockup.svg` — 레거시 HUD 목업. 참조하는 곳이 없다. 남겨 뒀다

각 자리의 문구가 곧 남은 연동 목록이다. 조회가 붙는 순서대로 지워 나가면 된다.

## 문서 · 다이어그램

- [ ] `architecture.drawio` 신규 — 3계층 + ROS2 인터페이스(1p), 레시피의 DB 복사분/로봇 소유분(2p)
- [ ] `db-schema-overview.drawio` 원칙 3번(구조/방법 분리)에 `Recipe.md` 링크
- [ ] `DB.drawio` 소실 확인 — 의도치 않은 삭제면 복구 필요

## 데이터 구현

- [ ] `production` 스키마 DDL 작성 (`schema.dbml` 기준)
- [ ] `part_catalog` 적재 스크립트 (데이터시트 xlsx → 테이블)

## 결정 필요

- [ ] 분기 정기 발송 시 임계 초과 부품이 없을 때 처리 (미발송 / 이상없음 문서 / 요약본)
- [ ] 레시피 버전 append-only 보관 주체 확정 (Git 전제가 맞는지)
- [ ] `part_supply` 가격 이력 여부 (덮어쓰기면 `alerts`에 가격도 스냅샷)
- [ ] 조립 실패 슬롯을 `units`에 칼럼으로 남길지
