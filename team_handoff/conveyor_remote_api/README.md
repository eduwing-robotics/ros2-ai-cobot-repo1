# KSMC 컨베이어 원격 API 팀 인수인계

기준일: 2026-09-03  
대상: Main/DB 서버 담당자, Unity Digital Twin 담당자

이 폴더는 KSMC의 S22 정지선 기반 컨베이어를 팀 시스템에 연결하기 위한 전달
패키지다. 원격 API는 HTTP가 아니라 ROS 2 Jazzy 토픽과 서비스로 제공된다.

2026-09-08: 서버 PC에서는 [통합 실행기](../../docs/CONVEYOR_VISION_SERVER.md)로
컨베이어 원격 서버와 Vision 검사 HTTP 서버를 한 터미널에서 관리할 수 있다.
이 폴더의 ROS 계약은 그대로이며 팀원 코드를 교체할 필요는 없다. 기존 서버 운영 중에는
그대로 두고, 정지·검사 완료를 확인한 뒤 다음 실행부터 전환한다.

## 폴더 구성

| 파일 | 용도 |
|---|---|
| `APPLY_GUIDE.md` | 서버 설치부터 Unity·DB 연동까지 적용 순서 |
| `API_CONTRACT.md` | 서비스, 토픽, 상태, 안전 조건 명세 |
| `assembly_recipe_r1.yaml` | NBSP를 제거한 공통 조립 레시피 |
| `unity/ConveyorRosClient.cs` | Unity ROS-TCP 구독·서비스 호출 예제 |
| `db/conveyor_event_subscriber.py` | DB 서버용 ROS 상태·이벤트 구독 예제 |
| `CHECKLIST.md` | 통합 시험 및 현장 적용 체크리스트 |

## 가장 중요한 규칙

1. Unity나 DB가 `/cmd_vel`을 직접 발행하면 안 된다.
2. 원격 서버 `conveyor_remote_server` 하나만 속도 권한을 가진다.
3. 이동 서비스의 `success=true`는 요청 수락이지 도착 완료가 아니다.
4. 조립·검사 도착 완료는 `/conveyor/state`의 `ASSEMBLY_STOP` 또는
   `INSPECTION_STOP`으로 확인한다.
5. `/cell/fr5_clear_for_conveyor=True` heartbeat가 없으면 이동은 거절된다.
6. 실제 장비 적용 전 `CHECKLIST.md`의 monitor-only 시험부터 수행한다.

상세 원본 계약은 저장소의 `docs/CONVEYOR_API_HANDOFF.md`에도 보관되어 있다.
검사 완료 후 JSON·PNG 자료를 Sequencer가 요청·조회하는 최신 계약은
`../vision_sequencer_api/`에 있다. Vision의 DB 직접 쓰기나 MainServer 업로드는 하지 않는다.
