# FR5 프로젝트 검토 및 개선 계획 — 2026-09-08

> 후속 상태: 사용자 승인 후 R1~R8 코드 수정을 진행했다. [수정·검증 보고서](PROJECT_REVIEW_FIXES_2026-09-08.md)를 현재 구현 기준으로 읽는다. 아래 내용과 행 번호·재현 결과는 수정 전 검토 기록이다.

## 검토 결론

현재 프로젝트는 **25개 부품의 촬영·계획·실기 실행을 연결하고, 여러 부품의 성공 조건을 실물로 검증한 조립 프로토타입**이다. 다음 완성도를 좌우하는 부분은 장애 상태의 정확한 기록, 센서 관측의 시간 일치, 조립 후 실물 품질 판정이다.

9월 6일 전체25개 성공에는 복구와 사용자 보조가 포함됐고, 9월 7일에는 최종 SMD 분리 높이의 실기 성공 수용이 있었다. 이를 최신 통합 런처의 장시간 무중단 성공률이나 전25개 정밀 안착 검사 완료로 확대하지 않는다. 어제 마지막 실행은 HBM-08 검사 자세에서 중단됐다. 조명 영향과 접촉 원인은 아직 미확정이다.

검토 기준은 [프로젝트 목표](PROJECT_GOAL.md), 현재 작업 트리의 실제 코드, 실행 원본 로그다. 과거 일지의 중간 상태보다 후속 기록과 현재 코드를 우선했다. 초안 [구조 문서](../references/FR5_ROBOT_CONTROL_ARCHITECTURE.md)의 다른 작업공간 진단을 현재 결함으로 옮기지 않았다.

**이번 검토에서는 아래 결함을 수정하거나 로봇을 움직이지 않았다.** 직전 별도 요청인 휴대폰 `view` 연동만 구현했다. 아래 완료 기준은 향후 검증 제안이며 이미 달성한 결과가 아니다.

## 이미 갖춘 기반과 유지할 조건

- 런처는 기판→트레이→VRM 정밀→일반20개→SMD 정밀→SMD5개의 13단계를 연결한다. 새 촬영, 재시도 제한, 전체 경로 IK, 완료 목록·계획 해시 확인과 중복 런처 잠금이 있다. [런처](../vision_assembly/scripts/assembly_cycle_launcher.py), [사용법](FR5_CYCLE_LAUNCHER_KO.md).
- 성공한 파지·배치 방향을 계획과 실행기 양쪽에서 검사한다. IK 편의를 위한 반대180도 파지로 바꾸지 않는다. [방향 기준](../vision_assembly/scripts/successful_gripper_directions.py).
- 일반 부품은 파지 후100mm 상승과 TrayHome 셀 제거 검사를 한다. 이는 원래 셀에서 사라졌다는 증거이며, 실제 보유·정상 안착과 구분한다. SMD는 별도 근접검출 흐름을 유지한다.
- SMD `source_image_v1` 축 계산과 구·신 관측 혼합 거부, 재측정의 부품 대응·이동·모델·손눈 일치 검사가 있다. 검출 임계값을 낮춰 해결하는 방향은 채택하지 않는다.
- 최신 SMD 배치Z 추가 보정은 CAP-01=-1.9mm, CAP-02~05=-2.4mm다. 성공 방향, 공통+0.3mm, 추가 종이 보정0, Tool1/Hand-Eye 조건을 유지한다.
- Unity Real API의 기본 DISARMED와 Ghost 미리보기 분리는 의도된 보호 기능이다. 하드웨어 활성화를 완성도 개선으로 간주하지 않는다.

## 우선 보완할 문제

P1은 해당 실행 경로의 다음 기능 변경·운용 확대 전에 우선 해결할 항목이다. R1~R4는 현재 조립 경로, R5~R7은 별도 검사·연동 경로에 해당한다. 별도 서버의 결함이 현재 조립 런처에서 실제 발생했다고 주장하지 않는다.

| ID | 우선순위·확인 수준 | 문제와 영향 | 개선 및 완료 기준 |
|---|---|---|---|
| R1 | P1 · 모의 재현 | 상태 수신이 끊겨도 이전 TCP·정지·오류 값을 도착 검증에 사용할 수 있다. | 모든 이동 전/도착/검사 대기에 수신 나이와 순번 요구. 명령 이전의 일치 상태는 성공으로 처리하지 않음. |
| R2 | P1 · 모의 재현 및 실제 로그 불일치 | 닫기 도중 실패하면 보유 후보=false가 남고, 최근 검증 위치는 이전 슬롯 값으로 남을 수 있다. | 명령 의도를 먼저 저장하고 보유 상태 unknown을 지원. 매 경유점 검증 기록과 장애 관측을 분리. |
| R3 | P1 · 코드 확인 | 정지 RPC는 최대90초인데 런처는 SIGINT 후15초/추가5초에 종료를 강제한다. | 오류·정지 의도 먼저 저장. 정지 RPC와 종료 유예 계약 통일, 응답·실제 정지·강제 종료를 별도 기록. |
| R4 | P1 · 모의 재현 | RGB와 깊이 시각을 검사한 뒤, 추론은 교체된 최신 깊이를 읽을 수 있다. | RGB/depth/stamp/CameraInfo/pose를 묶어 고정. 계산 중 새 수신이 와도 관측 묶음 유지 또는 명시적 거부. |
| R5 | P1 · 모의 재현 | 일반 검사기가 같은 오래된 프레임의 반복 수신과 NaN 점수를 PASS로 받아들인다. | 원본 시각·중복·역전·유한 점수 검사. 서로 다른 유효 영상으로만 안정 창 구성. |
| R6 | P1 · 모의 재현 | 실행 중 같은 operation_id 재수신 시 FAILED/BUSY 후 COMPLETED가 같은 ID로 발생한다. | 활성 요청의 ID와 내용 확인. 동일 요청은 기존 실행에 합류하거나 진행 상태 반환, 최종 결과는 일관되게 전달. |
| R7 | P1 · 코드 확인 | 컨베이어 stopped=true가 발행자 단절 후에도 만료되지 않는다. | 시각·세션이 있는 정지 heartbeat와 유효시간 검사. 끊김/false/재시작 시 보정 허가 차단. |
| R8 | P1 · 실행 명령 확인 | 기본 test_all은 실제 조립/비전/스택/진행률 시험을 누락한다. | 전체 검사 명령에 실제 핵심 모듈 시험 포함. 카메라·ROS 서비스·GUI 연결 없는 회귀검사를 기본으로 보장. |
| R9 | P1 · Git 집계 | 실행 핵심 소스가 미추적 상태이며 빌드·캐시 파일은 다수 추적돼 있다. | 검토된 소스·설정·재현 fixture를 버전으로 고정하고 생성물은 분리. 깨끗한 checkout에서 설치·검사 재현. |

### R1 — 로봇 상태 최신성

[공통 실행기 spin_state](../vision_assembly/scripts/execute_cached_hbm_remaining.py) 198행은 `state is not None`만으로 반환하며, 같은 파일325행의 `wait_pose`도 상태 수신 나이와 명령 이후 순번을 요구하지 않는다. 현재 [실행 루프](../vision_assembly/scripts/execute_full_fixed_cycle.py) 612행 및 [트레이 검사](../vision_assembly/scripts/tray_home_gate.py) 169행에서 이 상태를 사용한다.

모의 노드의 수신을 멈추고 `state_sequence=1`을 유지했는데 일치하는 과거 TCP가 정상 반환됐다. 실제 통신 단절이 어제 사고를 일으켰다는 뜻은 아니다. 기존 XYZ/ABC/관절 오차·정지 검사와 그리퍼의 신선한 연속 피드백 검사는 유효하다. 후자의 수신 나이/순번 정책을 공통화하는 것이 작은 수정으로 효과가 크다.

완료 기준: 수신 단절, 중복 순번, 명령 전 일치값을 거부하고 명령 후 새 상태로만 도착을 승인한다. stale 상태에서는 다음 이동도 발행하지 않는다.

### R2 — 불확실한 보유 상태와 정확한 장애 기록

[execute_full_fixed_cycle.py](../vision_assembly/scripts/execute_full_fixed_cycle.py) 839행의 닫기 호출 뒤에야 보유 후보가 갱신된다. 모의 닫힘 수락 후 timeout을 주입하니 마지막 그리퍼65와 `part_held_candidate=false/held_slot=null`이 함께 남았다. 명령 발행 전 `grasp_requested`와 대상 슬롯을 저장하고 수락/피드백/보유 확인을 구분해야 한다. `false`가 실제 빈 그리퍼 확인을 뜻하도록 사용 범위를 명확히 해야 한다.

같은 파일813행은 `move_preflighted`가 반환한 검증 TCP를 저장하지 않는다. 923행은 장애 후 snapshot을 `last_verified_tcp`에 덮어쓰고 snapshot 실패는 무시한다. 모의 검증에서도 마지막 위치 `[2,...]` 대신 이전 `[1,...]`이 남았다. 실제 [어제 로그](../runtime/assembly_cycles/20260907-194725-908616/assemble_non-smd.log) 431행은 HBM08 TrayHome인데 [JSON](../runtime/assembly_cycles/20260907-194725-908616/non-smd_run.json) 217행은 HBM07 배치 후 위치 부근이다.

권장 기록: `command_id`, `slot`, `waypoint`, `requested/accepted/verified`, 목표/검증TCP, 수신순번·나이, 보유상태·근거. `last_verified_waypoint`와 `stop_observation`은 별개로 보존한다. 닫기 수락 전/후 오류와 KeyboardInterrupt, 이동 도중 정지, snapshot 실패를 각각 검증한다. 기존 자동 복구 금지는 유지한다.

참고: 일지의18을 JSON의25로 정정하겠다고 한 대화 중 설명은 철회한다. HBM08 마지막 명령/정착 로그는18이며 JSON의25도 오래된 값이다. 오늘 실제 보유 여부는 둘 다 증명하지 않는다.

### R3 — 정지 처리와 프로세스 종료

[공통 서비스](../vision_assembly/scripts/execute_cached_hbm_remaining.py) 242행의 기본 제한은90초다. [런처](../vision_assembly/scripts/assembly_cycle_launcher.py) 163행은 SIGINT 후15초 대기, SIGTERM 후5초 대기, 이후 SIGKILL을 보낸다. [실행기](../vision_assembly/scripts/execute_full_fixed_cycle.py) 906행은 StopMotion 호출 종료 뒤 장애 결과를 저장한다.

StopMotion 응답이 지연되면 허용된 RPC 대기 중 프로세스와 기록이 끊길 수 있다. 이는 로봇이 실제로 멈추지 않았다는 실증은 아니다. 장애 기록을 먼저 저장하고 정지 전용 timeout과 종료 유예를 맞추며, 제어기 응답0과 새 피드백의 실제 정지를 분리해야 한다. 응답 없음·지연·재중단 모의 시험으로 기록 보존과 후속 단계 차단을 확인한다.

### R4 — 비전 관측 묶음 고정

[detect_tray_parts.py](../vision_assembly/scripts/detect_tray_parts.py) 664행에서 RGB/depth 시각을 비교하고595행의 별도 추론 스레드가 처리한다. 하지만387행은 인자로 전달한 깊이 대신 콜백161행이 교체하는 `self.depth`를 참조한다.

현재 함수의 합성 재현에서 전달한 깊이는500mm, 교체한 `self.depth`는900mm였고 결과는900mm였다. 검사한 프레임과 실제 계산 프레임이 다를 수 있다는 코드 증거다. 실물 오차의 빈도·크기와 HBM08 접촉 원인은 별도 계측이 필요하다. 한 관측 묶음을 고정한 뒤 추론 지연 중 새 depth 주입 시험을 추가한다.

### R5 — 일반 검사 PASS 입력 검증

[assembly_inspector.py](../ros2_ws/src/vision_server/vision_server/assembly_inspector.py) 47/81/96행은 수신 시각과 count signature로 안정성을 판단한다. 동일 원본 timestamp=1을 세 번 전달한 모의 입력이 PASS였다. [inspection_rules.py](../ros2_ws/src/vision_server/vision_server/inspection_rules.py) 43행의 점수는 유한성 검사가 없어 NaN도 PASS로 계수됐다.

원본 timestamp의 나이·미래·역전·중복과 점수 `finite && 0≤score≤1`을 검사해야 한다. 부적합 관측은 성공 창에 포함하지 않는다. 이 결과는 별도 일반 검사기의 결함이며 현재25개 런처의 최종 품질 검사가 구현됐다는 뜻이 아니다.

### R6·R7 — 연동 요청과 공정 전제의 수명

[real_backend.py](../ros2_ws/src/fr5_process_sequences/fr5_process_sequences/real_backend.py) 227행은 실행 잠금을 얻지 못하면 동일 활성 ID에도 FAILED/BUSY를 발행한다. [클라이언트](../ros2_ws/src/fr5_process_sequences/fr5_process_sequences/sequencer_robot_client.py) 95행은 이를 최종 실패로 처리하고 후속 완료는 무시한다. 가짜 로봇에서 같은 ID의 FAILED→COMPLETED가 재현됐다. 완료 후 중복 처리만으로 진행 중 재전송까지 해결되지 않는다. 동일 ID/동일 내용, 동일 ID/다른 내용, 다른 ID를 각각 구분해 시험한다.

[orchestration_action_server.py](../ros2_ws/src/vision_server/vision_server/orchestration_action_server.py) 147행과 [unity_calibration_server.py](../ros2_ws/src/vision_server/vision_server/unity_calibration_server.py) 56행은 컨베이어 정지 Bool을 보존하고 유효시간을 검사하지 않는다. 해당 API는 직접 로봇을 움직이지 않지만 보정 허가의 전제가 오래될 수 있다. 정지 heartbeat 중단·재시작·false 전환을 검증한다.

### R8·R9 — 검증과 성공 버전의 재현성

[scripts/test_all.sh](../scripts/test_all.sh) 7행은 ROS 패키지 두 곳만 pytest로 실행한다. 검토 시점 누락된 시험 모듈은 `vision_assembly/tests`25개, `scripts/tests`1개, `assembly_integration`1개다. compileall 통과가 이 기능 시험을 대신하지 못한다. 시스템 Python+ROS 환경과 비전 venv의 역할을 문서화한다. 실제로 비전 venv에는 pytest가 없어 이번 실행 시험은 기존 ROS 환경을 읽은 시스템 Python을 사용했다.

[소스 집계](../runtime/project_review_20260908/source_manifest.json) 기준 Git HEAD는 `713f6023`이다. 수정된 추적 항목79개, 미추적 항목320개였고, 생성물/캐시 파일1544개가 이미 추적돼 있었다. 수치는 검토 시점 값이며 디렉터리 표시를 포함한다. `assembly_cycle_launcher.py`, `execute_full_fixed_cycle.py`, `tray_home_gate.py`, `successful_gripper_directions.py`, `real_backend.py`는 미추적이었다.

사용자 변경을 지우지 않고 검토된 소스·설정·핵심 재현 fixture를 묶어 커밋할 수 있도록 정리한다. 모델·보정·성공 레시피에는 버전/해시와 복원 경로를 붙인다. 별도 checkout에서 설치·전체 오프라인 검사·런처 dry-run이 재현되는지를 완료 기준으로 삼는다. 이번에는 커밋·정리·파일 삭제를 수행하지 않았다.

## 목표 품질을 높이는 다음 작업

### 1. 어두움 가설을 비교 실험으로 확인

부품·위치·카메라·모델을 고정하고 밝은 조건/어두운 조건/보조 조명 조건을 비교한다. 우선 로봇을 움직이지 않는 촬영 실험으로 시작한다. 각 조건에서 동일한 수의 새 관측을 모으며 다음 항목을 함께 기록한다.

| 기록 | 확인하려는 점 |
|---|---|
| 원본 RGB·사용한 depth·프레임 시각·CameraInfo | 같은 관측을 다시 계산할 수 있는가 |
| 실제 노출·gain·white balance·구역별 밝기·포화율·선명도 | 조명과 자동 노출·반사의 영향을 구분할 수 있는가 |
| 부품별 confidence·선택 추론 크기·재시도 출처 | 어느 조건에서 어떤 검출이 개선되는가 |
| 중심/각도 편차·깊이 유효율·관측 지연 | confidence 상승이 좌표 재현성과 함께 개선되는가 |
| 첫 시도 통과율·재시도 수·검출 시간 | 실제 사이클 지연을 줄이는가 |

현재 입력 크기 재검출은 유용하지만 [안정화 결과](../vision_assembly/scripts/detect_tray_parts.py) 532행에는 선택된 입력 크기 등의 출처가 보존되지 않는다. 먼저 이 진단 정보를 남긴다. 실패 자료는 부품 종류뿐 아니라 위치·조명별로 묶고, 새 학습/설정은 별도 고정 평가 자료로 비교한다. 재학습·노출 고정·임계값 변경 중 무엇이 필요한지는 비교 결과로 결정한다.

### 2. 보드가 움직이면 목표를 무효화하고 다시 관측

[런처](../vision_assembly/scripts/assembly_cycle_launcher.py) 86행은 최초 기판 촬영 후 일반20개와 SMD를 진행한다. 보드1800초 유효시간은 접촉이나 작업자 개입으로 생긴 이동을 감지하지 못한다.

접촉 보고·중단·부품 재정리 시 기존 목표를 무효화하는 상태를 둔다. 추후 고정 카메라에서 보드 기준점의 유효한 이동을 감지하면 다음 하강 전에 차단한다. 가림/미검출은 이동 없음으로 해석하지 않는다. 재관측 후 이미 놓인 슬롯·남은 트레이·보유 상태를 대조해 새 계획을 만들고, 과거 절대 좌표를 재생하지 않는다.

### 3. 전25개 실물 검사와 PASS/FAIL/판정불가 연결

현재 실행기는 올바르게 `motion_complete_awaiting_physical_verification`으로 끝난다. 일반 검사기는 클래스·개수 중심이며 board_id와 slot 결과가 비어 있다. 휴대폰은 [part_inspector.py](/home/juchan-yoon/.local/share/fr5-phone/part_inspector.py:47)에서 CAP만 검사하고, [metric_geometry.py](/home/juchan-yoon/.local/share/fr5-phone/metric_geometry.py:24)의 mm 값은 잠정 평면 추정이다.

최종 촬영과 cycle/board/recipe ID를 연결하고 슬롯별 존재·종류·중심·각도·가림·판정 근거를 저장한다. 부품수는 같아도 다른 슬롯에 놓인 사례, 회전/이동, 일부 가림이 최종 PASS가 되지 않는지 시험한다. 실제 mm/각도 허용오차는 도면·실물 요구와 독립 계측을 기준으로 정한다. 화면이 안정돼 보이거나 재투영 오차가 작다는 이유만으로 mm 정확도를 승인하지 않는다.

### 4. 실물 간섭과 고정 높이의 적용 조건을 관리

현재 IK와 관절 제한 통과는 그리퍼·손가락·보유 부품의 전체 부피 간섭 검사가 아니다. HBM08의 direct MoveJ와 HBM07의 midpoint 차이는 이전 실행에도 있었으며 이번 감사만으로 경로 결함은 확정하지 못했다. 실제 접촉 대상·단계를 영상과 대조하고 손가락/브래킷/지그의 형상·여유를 기록해 경유점 변경을 검증해야 한다. 기존 성공 양끝 방향과 속도/관절 제한은 유지한다.

SMD [근접 계산](../vision_assembly/scripts/capture_smd_close_target.py) 143행은 Z=-47.291mm 고정 평면의 광선 교점이다. 결과에 `position_method`, 고정 평면값, 장착/캘리브레이션 ID를 명시하고 독립 기준점으로 적용 범위를 검증한다. 새 촬영 Z 실측으로 표기하지 않는다. 검토를 이유로 성공한 SMD 높이나 종이 보정을 바꾸지 않는다.

### 5. Unity 재연결과 공정 상태 통합

[진행률 발행](../assembly_integration/assembly_progress.py) 112행은 transient-local을 쓰지만1초 뒤 publisher가 종료된다. Unity는 초기 snapshot 조회 없이 구독하므로 뒤늦게 연결하면 DB 진행률을 놓칠 수 있다. 상시 snapshot publisher 또는 조회 API와 연결 시 재조회로 해결하고 지연 접속/재접속/노드 재시작을 검증한다.

전체 공정에는 하나의 cycle ID와 상태 모델을 공유하되, 당장 초안 구조 문서의 모든 패키지로 재작성할 필요는 없다. 기존 런처와 Real API의 공통 상태 검증·명령 기록·완료 의미부터 맞춘다. 컨베이어와 검사 handler가 외부 연계로 남아 있는 것은 명시된 확장 지점이며, 실제 연결 전에는 완성된 자동 셀로 표시하지 않는다.

## 권장 진행 순서와 평가 지표

| 순서 | 산출물 | 완료 판단 |
|---|---|---|
| 1 | R1~R4 수정 및 실패 주입 fixture, 전체 테스트 진입점 정리 | 위 재현들이 명시적 거부/정확한 기록으로 바뀌고 기존 보호 기능 회귀시험 통과 |
| 2 | 동일 장면 조명 비교 보고와 HBM08 접촉 단계 확인 | 검출 품질·좌표 재현성·지연을 수치로 비교하고 접촉 미확정 항목 분리 |
| 3 | 보드 목표 무효화, 보유 상태 확인, 잔여 슬롯 재계획 절차 | 중단/보드이동/파지불확실 상태에서 임의 재파지·중복 배치가 발생하지 않음 |
| 4 | 슬롯별 조립 후 검사와 연동 결함 R5~R7 수정 | 잘못된 입력·오배치·가림을 PASS로 처리하지 않고 재전송/단절에도 상태 일관 |
| 5 | 성공 버전 복원, Unity 재접속, 반복 전체 사이클 평가 | 독립 실행마다 새 관측·기록 보존, 개입률과 실제 양품률을 함께 보고 |

첫 기준선으로 연속10사이클 평가를 제안한다. 이는 통계적 신뢰성 인증이나 현재 승인된 실기 명령이 아니다. 부품별 첫 파지 성공률, 실제25개 양품률, 사용자 개입 횟수, 검출 재시도 수, 중단 원인, 총시간·촬영/이동/검사 시간을 분리한다. 표본이 작을 때는 백분율과 함께 성공/전체 건수를 표시한다. 자료가 충분해지면 중앙값과 상위 지연도 관리한다. 속도·재시도·검사 빈도 최적화는 이 기준선 뒤에 진행한다.

[README](../README.md) 84행의 현재 상태와 [doctor](../scripts/doctor.sh) 38행의 DroidCam 안내는 최신 실행기·scrcpy 휴대폰 경로와 차이가 있다. 최신 상태 요약 하나를 두고 과거 일지는 이력으로 연결하면 인계 혼동을 줄일 수 있다.

## 이번 검증과 저장한 근거

- 실행/트레이검사/재시도/런처/피드백 기존 시험 **91개 통과**. [명령·결과](../runtime/project_review_20260908/execution_audit/tests.txt).
- 입력 크기 재검출/트레이 관측 기존 시험 **28개 통과**. 합계119개는 서로 다른 기존 시험이며 전체 프로젝트 시험을 모두 실행한 것은 아니다.
- 추가 하드웨어 없는 문제 재현7건: 오래된 상태 승인, 잘못된 보유 상태, 마지막 TCP 기록 누락, 깊이 입력 혼합, 진행 중 중복ID, NaN 검사점수, 같은 오래된 영상 반복 PASS.
- [실행기 재현](../runtime/project_review_20260908/execution_audit/reproducer.py), [출력](../runtime/project_review_20260908/execution_audit/reproducer_output.txt), [비전 재현](../runtime/project_review_20260908/vision_audit/depth_sync_reproducer.py), [비전 결과](../runtime/project_review_20260908/vision_audit/result.json), [연동 재현](../runtime/project_review_20260908/integration_audit/audit.py), [연동 결과](../runtime/project_review_20260908/integration_audit/results.json).
- [검토 시점 소스 해시·Git 상태 집계](../runtime/project_review_20260908/source_manifest.json). 이 문서는 커밋만이 아니라 해당 작업 트리 내용을 검토한 것이다.
- 별도 휴대폰 화면 변경은 기존 스택 시험11개·셸 문법·모의 동시/반복/실패 처리 통과. 실제 휴대폰3840×2160/약30fps 확인 및 기존 PID19346 재사용을 두 번 확인했다. [실시간 검증 기록](../runtime/assembly_stack/phone_view_integration_20260908.json).
- 이번 검토 중 로봇·그리퍼·컨베이어 이동, 오류 해제, 실제 조립, Unity Editor 빌드, 새 실물 계측은 하지 않았다. 현재 로봇 상태와 현장 준비는 실기 재개 시 다시 확인해야 한다.
