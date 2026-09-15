# 프로젝트 검토 후 결함 수정 — 2026-09-08

[최초 검토](PROJECT_REVIEW_2026-09-08.md)의 R1~R8을 사용자 승인 후 수정했다. 원본 문제 재현과 수정 전 해시는 그대로 보존했다. 성공 파지·배치 방향, SMD 추가 높이, 레시피·손눈 보정값은 변경하지 않았다.

## 반영 내용

| 항목 | 변경 결과 | 검증 범위 |
|---|---|---|
| R1 상태 최신성 | 이동 전 새 피드백을 요구하고 도착 검증은 명령 이후 순번과 수신 나이 0.25초를 검사한다. 발행 직전 최종 표본으로 관절 기준 이탈·NaN도 검사한다. | 수신 단절, 명령 전 일치 상태, 중복 순번, 최종 표본 변경, 다음 이동 차단 모의 시험. |
| R2 보유·장애 기록 | 그리퍼 명령 의도를 먼저 저장하고 실패 중 보유 상태를 `unknown`으로 남긴다. 각 경유점의 검증 TCP와 장애 후 `stop_observation`을 구분한다. | 닫기 수락 전후 오류, timeout, 중단, 마지막 검증 위치 보존. |
| R3 정지·종료 | 장애·정지 의도를 RPC 전에 저장한다. 정지 응답 4초와 피드백 3초를 런처 SIGINT 유예 15초 안에 배치하고, 응답·정지 확인·프로세스 강제 종료를 별도로 기록한다. 실행기와 카메라 이동 단계가 정지 시도 후 ROS를 종료한다. | 정지 실패·지연, 기록 저장 실패, 반복 중단 및 가짜 자식 프로세스 종료. 실제 로컬 ROS context에 자기 SIGINT를 보내 통신 유지도 검증(로봇 서비스는 fake). |
| R4 관측 일치 | RGB 처리에 사용할 깊이·시각·내부 파라미터·로봇 자세·트레이 변환을 고정한다. 계산은 고정한 입력을 사용하고 게시 직전 최신 로봇 상태도 검사한다. | 추론 중 깊이 교체, 오래 걸리는 추론, 상태 단절, 로봇 이동 및 실제 카메라 입력. |
| R5 일반 검사 | 원본 영상 시각의 만료·중복·역전·미래 값을 거부한다. 점수는 유한한 0~1 값만 허용하고 잘못된 입력은 안정 창을 초기화한다. | 같은 프레임 반복 PASS와 NaN/Inf 점수 승인 차단. 전체25개 실물 품질 판정 시험은 아님. |
| R6 중복 요청 | 동일한 진행 중 요청은 기존 실행 결과를 기다린다. 예약·완료된 ID의 다른 내용은 비종료 이벤트 `REQUEST_REJECTED`로 거절해 원래 결과를 보존한다. | 동시 요청, 잘못된 내용, 완료 저장 후 결과 전달 전 경계에서도 client Future 결과 보존. |
| R7 컨베이어 정지 | 두 보정 API가 공통 heartbeat 유효시간·원본 시각·발행자 세션을 검사한다. 끊김·false·만료·발행자 변경은 진행 중 보정 허가도 무효화한다. | 시각·만료·세션 교체 모의 시험. 실제 컨베이어의 물리적 정지 검증은 아님. |
| R8 전체 검사 | `scripts/test_all.sh`에 조립·비전·스택·진행률 시험을 포함했다. 구문 검사는 바이트코드 파일을 쓰지 않는다. | 전체 결과와 실행 로그는 아래 검증 기록에 보존. |

## 운용 계약 변경

- 컨베이어 발행자는 `Bool`을 RELIABLE QoS로 지속 발행해야 한다. 기본 `pcb.conveyor_heartbeat_max_age_sec: 1.0`초이며 5Hz 발행을 권장한다. 같은 발행자의 서로 다른 새 `true` 두 개 이후 보정 허가가 생긴다. 한 번 보낸 `true`나 과거 latched 값만으로 허가하지 않는다. 호스트 시각 동기화가 필요하다. [Unity 보정 API](UNITY_BOARD_CALIBRATION_API_KO.md).
- `REQUEST_REJECTED`는 원래 operation의 최종 실패가 아니다. 기존 client는 이를 Future 완료 이벤트로 처리하지 않는다. 완료된 동일 요청의 결과 재전달은 유지한다. [Robot API](SEQUENCER_ROBOT_API_KO.md).
- `run_fr5_assembly_stack.sh view`는 D435 RQT와 USB 휴대폰 화면을 함께 연다. 휴대폰 화면이 이미 실행 중이면 재사용한다. `doctor.sh`도 현재 휴대폰 실행기를 확인한다.

## 검증 기록

검증 로그·보존 설정 해시·재시작 기록·실제 영상 표본은 [implementation 디렉터리](../runtime/project_review_20260908/implementation/)에 저장한다. 최종 전체 시험 결과는 [validation.json](../runtime/project_review_20260908/implementation/validation.json)과 [test_all.log](../runtime/project_review_20260908/implementation/test_all.log)를 기준으로 한다.

- 전체 오프라인 시험 **571개 통과**, Python 구문158개와 셸 구문 검사 통과. 스택 `preflight`도 통과했다.
- 런처 `--dry-run`의 13단계 구성이 정상이다. 실제 촬영·IK·조립은 수행하지 않는다.
- 트레이 검출기와 vision/robot/Unity calibration API를 개별 재시작했다. 관리9개 RUNNING, Robot API DISARMED 및 새 정지 피드백을 확인했다. driver·D435·보드 영상 프로세스는 유지했다. [재시작 후 스택](../runtime/project_review_20260908/implementation/stack_check_after.log), [API 상태](../runtime/project_review_20260908/implementation/status_after.json). 마지막 상태는 AUTO mode0, 그리퍼 피드백invalid, 오류·충돌0이다. 이 작업에서 모드 전환·그리퍼 활성화 명령은 보내지 않았다.
- 갱신한 트레이 검출기에서 서로 다른 새 관측 5개를 받았다. 모두 `TRACKING`, 검출/안정 표시25개, `VALID_COORDINATES_ONLY`, RGB/depth 시각 차이0~66.717ms다. 표시 개수는 전체 조립 승인이나 개별 품질 게이트 통과의 증거가 아니다. [관측 요약](../runtime/project_review_20260908/implementation/live_tray_validation.json).
- 검사 확대 중 발견한 오래된 레시피 시험 기대값은 이미 저장된 성공 기준에 맞게 갱신했다. 실제 레시피는 바꾸지 않았다. 보호 대상8개 파일의 전후 SHA-256 일치를 확인한다.

## 남은 작업과 범위

R9는 [소스·설정·시험 복원용 사본](../vision_assembly/checkpoints/review_fixes_20260908/README.md)과 해시를 남겼다. Git 정리 및 깨끗한 checkout 재현은 후속 작업으로 남긴다. 기존 작업 트리에는 여러 날의 수정·미추적 파일과 추적된 생성물이 섞여 있어 일괄 삭제나 임의 커밋을 하지 않았다.

야간 조명 가설과 HBM-08 접촉 원인은 여전히 미확정이다. 다음 실기에서는 빈 그리퍼·빈 기판·부품 배치·걸림 여부를 확인하고 조명 조건 및 실패 단계를 함께 기록해야 한다. 보드 이동에 따른 목표 재측정, 슬롯별25개 실물 검사, 장시간 반복 성공률은 별도 개선 과제다. 이번 수정·검증에서는 로봇·그리퍼·컨베이어 동작이나 오류 해제 명령을 보내지 않았다.
