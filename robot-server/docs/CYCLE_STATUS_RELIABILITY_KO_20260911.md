# 조립 단계 상태 조회 누락 수정 — 2026-09-11

실행 933385ab-4a5d-4b2f-b5d0-9595f2085acc는 TrayHome 도착, 촬영, 비SMD 계획과 preflight를 마친 뒤 assemble_non-smd의 StepApiSession.ready에서 API status timeout으로 종료됐다. 이전 startup 수정에서 실제 단계 전송 클래스의 5초 단발 조회가 남아 있었다.

## 적용 범위

| 경로 | 처리 |
|---|---|
| 그리퍼 startup, step API precheck | 기존 공통 읽기 전용 RPC 유지 |
| PlaceCamera, TrayHome, SMDView, after_photo | StepApiSession 공통 RPC 적용 |
| 비SMD·SMD 진입, 계획 수신 확인 | 동일 StepApiSession 적용 |
| 운영 CLI의 Start/Recover/Stop 전 상태 조회 | 공통 RPC 적용 |
| API 응답 | 로봇 상태·조립 상태·명령·피드백 콜백 그룹 분리 |

공통 조회는 최대 15초·3회이며 실패한 pending future를 정리한다. 계획 수신 확인은 전체 20초 기한 안에서 실행 ID와 계획 해시가 모두 같아야 통과한다. 계획 자체는 한 번만 발행한다. 건강 상태·정지·좌표계·그리퍼 피드백·파지 후보·복구 필요 상태를 공통 검증한다.

이동·Get·Set을 함께 처리하는 하드웨어 Executor는 기존 단발 전송과 90초 기본 응답 제한을 유지한다. 동작 재전송, 피드백 안전 기한 완화, 자동 복구는 추가하지 않았다. 카메라·인식·IK 검사도 유지한다.

## 검증 및 배포

- 관련 테스트 20개 및 전체 회귀 테스트 403개 통과.
- 격리 ROS에서 실제 StepApiSession의 PlaceCamera·비SMD·SMD 경로에 첫 응답 3.4초 지연을 주어 회복 확인. 계획 발행 1회, 로봇 명령 0개.
- 잘못된 실행 ID의 계획 승인 거부와 안전 상태 거부 확인.
- 생산 스크립트 상태 클라이언트 4곳을 AST 검사하여 공통 조회 누락과 직접 call_async를 검출한다. 동적 서비스 이름 등 모든 코딩 형태까지 검증하는 것은 아니다.
- 패키지 빌드 후 로봇 정지와 실행 작업 부재를 확인하고 API 서버 재시작 완료.
- 실제 실행 잠금 아래 StepApiSession 상태 조회 3회 성공: 4.254 / 0.001 / 0.001초. 첫 서비스 탐색 3초 실패 후 다음 시도에서 회복. 준비 상태 검증 통과, 동작 명령 0개.
- 운영 CLI 조회 성공. 기존 조립 실행은 recovery_required, 실패 단계 assemble_non-smd로 보존됨. 하위 로봇 ready와 조립 실행의 복구 필요 상태는 별개다.
- 증거: runtime/cycle_status_fix_20260911/live_status.json 및 assembly_status.json.

실제 전체 조립 Start는 수행하지 않았다. 상태 서비스 검증이며 물리 조립 전체 성공이나 모든 통신 지연 제거를 보장하지 않는다. 현장 확인을 거친 복구 후 새 실행 ID로 재시도해야 한다.
