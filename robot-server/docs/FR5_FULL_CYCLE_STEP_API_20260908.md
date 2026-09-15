# 전체 25개 런처의 단계 API 연결 — 2026-09-08

`./run_fr5_cycle.sh --execute`는 이제 촬영 위치 이동과 모든 Pick/Place를
`/real/robot/command`로 요청하고 해당 동작의 `OPERATION_COMPLETED`를 기다린다.
일괄 `assembly.start`를 다시 활성화하지 않았다.

## 실행 범위와 순서

기존 아침 성공 범위인 **고정 기판의 부품 25개 조립**이다.
GPU1 → HBM8 → PM4 → VRM5 → IND2 → SMD(CAP)5 순서를 유지한다.
컨베이어, 생산 품질 PASS, 완성 PCB 파지/이송은 이 성공 기록에 없으며 포함하지 않는다.

1. 스택·단계 API 검사.
2. PlaceCamera 이동 API 완료 → 보드 촬영.
3. TrayHome 이동 API 완료 → 트레이 촬영, VRM 측정.
4. 일반 20개 계획과 IK 검사.
5. 부품마다 Pick API 완료 → Place API 완료. 총 40개 개별 요청.
6. SMDView 이동 API 완료 → 새 근접 측정 → SMD 계획·IK 검사.
7. SMD마다 Pick API 완료 → Place API 완료. 총 10개 개별 요청.
8. PlaceCamera 이동 API 완료 → 결과 사진 저장.

Pick은 합의대로 TrayHome 제거 검사까지 포함한다.
Place는 슬롯 위 100 mm 후퇴에서 종료한다. 요청 전 다음 부품을 실행하지 않는다.
기존 런처 경로에는 별도 Home/AssemblyReady 관절 이동이 없으므로 삽입하지 않았다.
Unity의 전체 설비 YAML(`sequencer_recipe.current.yaml`)은 별도 계약이며,
그 안의 Home 복사본 ready point와 PCB transfer를 준비 완료로 바꾸지 않았다.

## 명령

```bash
./run_fr5_cycle.sh --dry-run
./run_fr5_cycle.sh --check
./run_fr5_cycle.sh --execute
./run_fr5_cycle.sh --execute --profile PM
./run_fr5_cycle.sh --execute --profile SMD
```

`--execute`의 기존 전제: 빈 그리퍼, 빈 기판, 요청한 트레이 부품, 고정 지그와 작업 공간 준비.
전체/부품군 모두 같은 API 연결을 사용한다. Ctrl+C는 진행 중 API에 pause를 요청하고
종료 결과를 기다린다. 결과 불명확/보유 후보/오류가 남으면 다음 동작이나 자동 재시작을 하지 않는다.

## 기존 API의 연결 보완

- `robot.pick` / `robot.place`: 공개 필드 변경 없음.
- `robot.move_joint`의 명시적 point_name `PlaceCamera`, `TrayHome`, `SMDView`:
  요청한 카메라 종료 관절값을 검사하고, Backend에서 기존 safe-Z·중간점·수직 MoveL 경로를
  실행한다. 단일 직선 관절 이동으로 기존 수직 경로를 바꾸지 않는다.
  일반 joint point 동작은 기존 의미를 유지한다. endpoint branch가 다르면 거절한다.
- 각 실제 이동 직전에 기존 Ghost target/stage_target을 발행한다.
- 상태 서비스에 읽기 전용 진단 필드 추가:
  `api_capabilities_revision=step-cycle-20260908`, `robot_health_clear`,
  `active_operation`, `recovery_required`, `vision_plan_sha256`.
  런처는 마지막 필드로 준비 계획 수신을 확인한 뒤 Pick을 요청한다.
- 기존 launcher.lock은 전체 사이클 동안 유지한다. `step_api_owner.json`으로
  살아 있는 런처의 동일 Unit/job에만 개별 API 실행을 위임한다.
  다른 Job, 중복 런처, 소유 프로세스 재시작, 동시 동작은 거절한다.
- 일반 20개 Place 완료 후에만 같은 Unit에 SMD 측정 계획을 덧붙일 수 있다.
  미완료 일반 단계나 겹치는 슬롯의 좌표를 새 계획으로 바꿀 수 없다.
- 마지막 부품으로 트레이가 완전히 빈 경우: 모든 기준 셀이 제거된 기록,
  새 shared-section 등록(500 ms 이내), 동기 depth, 안정된 로봇 자세,
  원시/안정 검출 모두 0인 연속 새 3프레임을 요구한다.
  이는 빈 셀의 관측 근거이며 손 안의 부품이나 정밀 안착을 보증하지 않는다.

## 기록과 검증

각 실행 폴더의 `api_recipe.json`에는 실제 부품 순서와 현재 검토 YAML의 그리퍼 값을
고정한다. `non-smd_api`, `smd_api`, 각 `*Camera_api` 폴더에 요청·이벤트·완료를 기록한다.
기존 `*_run.json`, `cycle.json` 완료 대조도 유지한다.
API 자체의 `runtime/robot_operations`, `runtime/robot_step_evidence`도 유지한다.

2026-09-08: 회귀 테스트 **301개 통과**, API 빌드·유휴 재시작 완료.
25개/50요청 모의 통합 실행, 중간 GPU/HBM/SMD 실패 차단, 소유권 잠금,
카메라 기존 경로, 마지막 빈 트레이 검증을 포함한다.
실제 장비 `./run_fr5_cycle.sh --check` 통과: AUTO0/Tool1/User0, 정지1,
피드백 정상, 로봇 오류 없음, 준비점/TCP/D435 확인.
**새 연결을 통한 실물 25개 연속 실행은 아직 수행하지 않았다.**

이 문서는 이전 전달 문서의 “로컬 런처는 직접 진단 실행” 상태를 대체한다.
Unity가 생산 Sequencer에서 전체 설비 YAML을 실행하려면 해당 ready point,
컨베이어/검사 handler, 완성 PCB 이송은 별도로 검증해야 한다.
