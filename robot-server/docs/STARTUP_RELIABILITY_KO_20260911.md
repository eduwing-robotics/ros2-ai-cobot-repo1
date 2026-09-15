# 시작 단계 서비스·콜백 안정화 — 2026-09-11

## 문제

실행 0d970e36-e2cd-4cb4-9ee5-6397f26cf947은 /real/robot/status 발견 3초 제한, 후속 609ae4a4-0dca-43a1-bfeb-944f3c450c19는 응답 3초 제한으로 startup에서 실패했다. 둘 다 assembly_motion_started=false였다. 발견 대기만 늘리고 단독 상태 조회로 확인한 앞선 수정은 전체 시작 흐름 검증으로 충분하지 않았다.

API의 명령·피드백·상태 서비스가 같은 기본 callback group과 단일 executor를 사용했다. 기존 설치본에서 기본 콜백을 지연시키면 상태 응답이 막히는 현상이 격리 테스트로 재현됐고 수정본은 통과했다. 해당 실패 순간의 콜백 추적은 없어 당시 timeout의 유일 원인이 교착이었다고 단정하지 않는다.

## 변경

- real_robot_api: 4개 실행 스레드, 명령 기본 그룹 유지, 피드백/드라이버 RPC 응답 그룹과 상태 서비스 그룹 분리. 상태 콜백 소요 시간을 응답의 status_callback_elapsed_ms로 제공.
- startup_service_client.py: 공통 발견 예산 15초, 호출별 발견/응답 대기 각각 최대 3초, 읽기 전용 조회 최대 3회·총 15초 이내 및 전체 시작 예산에 종속.
- 재시도 허용 목록은 /real/robot/status, /fr_command_server/get_parameters, GetGripperActivateStatus()뿐이다. 의미상 실패 응답·로봇 오류를 재시도해 무시하지 않는다.
- ActGripper 및 다른 동작 호출은 1회만 전송. 서비스 발견 후 실제 전송 직전에 activation_outcome_unknown을 영속 기록한다. 응답을 잃으면 불명 상태를 보존한다.
- 시간 초과한 조회의 pending future를 제거·취소해 늦은 응답을 다음 시도의 성공으로 사용하지 않는다.
- 준비 단계 전체 RPC 예산 35초, 상위 준비 subprocess 제한 45초. 해제 준비 검사도 45초 제한으로 하위 예산과 일치시켰다.
- startup 로그에 서비스 이름, 시도 번호, 발견/송신/응답 단계, 경과 시간 및 시각을 남긴다.
- 250ms 이동 피드백 검사, 로봇 안전 상태, ID 중복 방지, 현장 확인, 실제 활성화·이동 재전송 금지는 유지한다.

## 검증 및 배포

- 생산 제어·복구·런처·신규 ROS 통합 테스트 포함 392개 통과. 테스트용 Sequencer는 로컬 fr5-main-dt-integration/ASSEMBLY_SEQUENCER/src/assembly_sequencer 경로를 사용했다.
- 별도 ROS domain 117에서 실제 API 노드의 명령 콜백을 지연시켜도 상태 응답·피드백 수신이 진행됨을 확인했다. 하드웨어 실행은 비활성이다.
- 실제 AssemblyCycleController의 subprocess 실행과 launcher.lock/step_operation.lock을 사용한 통합 테스트에서 첫 상태 응답을 3.4초 늦췄다. 읽기 조회가 재시도돼 준비를 완료했고 허용된 가짜 드라이버 요청은 GetGripperActivateStatus()뿐이었다. 동일 ID 재전송은 두 번째 프로세스를 만들지 않았다.
- colcon으로 패키지 반영, 설치 파일과 소스 바이트 일치 확인. 로봇 정지·worker 부재를 확인한 뒤 API만 재시작했다. Unity TCP 연결 유지.
- 실제 생산 환경의 두 실행 잠금 아래 새 subprocess의 check_step_api를 3회 실행: 3.424/4.157/6.669초, 모두 성공. 상태 콜백은 약 0.032~0.090ms. state_fresh=true, robot_motion_done=1, recovery_required=false, 드라이버 연속 이동 revision 일치.
- 원시 증거: runtime/startup_reliability_20260911/live_readiness.json, readiness_1.log~readiness_3.log, deployment.json.

이번 실제 장비 검증은 상태·파라미터 조회만 수행했다. 실제 조립 Start·그리퍼 활성화·이동은 보내지 않았으며 전체 물리 생산 사이클 성공을 보장하지 않는다. 새 실행은 현장 상태를 확인한 뒤 새 실행 ID로 시작한다.
