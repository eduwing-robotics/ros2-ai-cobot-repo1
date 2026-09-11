# KSMC 컨베이어 원격 API 팀 인수인계

2026-09-10 추가: [S22 현재 도착 확인과 같은 목적지 재요청 처리](CURRENT_ARRIVAL_UPDATE.md).
ROI/remote server 업데이트와 Sequencer 분기 적용이 필요합니다.
2026-09-11: ready/trigger 수신 시각 기반 heartbeat fault를 제거했습니다. 명시적인
not-ready/trigger와 유한 이동 timeout은 유지하고, 로봇 `/cmd_vel` 수신기 없는
상태의 이동 요청은 즉시 거절합니다.
2026-09-11: `run_conveyor_remote_server.sh --with-s22`로 컨베이어 서버와 S22/ROI를
한 번에 시작할 수 있습니다. Endpoint와 GoPro는 계속 별도 담당입니다. 로봇 유선
주소 추가 절차는 [ROBOT_ETHERNET_SETUP.md](ROBOT_ETHERNET_SETUP.md)에 있습니다.

기준일: 2026-09-03  
대상: Main/DB 서버 담당자, Unity Digital Twin 담당자

이 폴더는 KSMC의 S22 정지선 기반 컨베이어를 팀 시스템에 연결하기 위한 전달
패키지다. 원격 API는 HTTP가 아니라 ROS 2 Jazzy 토픽과 서비스로 제공된다.

2026-09-08: 서버 PC에서는 [통합 실행기](../../docs/CONVEYOR_VISION_SERVER.md)로
컨베이어 원격 서버와 Vision 검사 HTTP 서버를 한 터미널에서 관리할 수 있다.
이 폴더의 ROS 계약은 그대로이며 팀원 코드를 교체할 필요는 없다. 기존 서버 운영 중에는
그대로 두고, 정지·검사 완료를 확인한 뒤 다음 실행부터 전환한다. Unity 예제
`ConveyorRosClient.cs`를 사용하는 씬은 최신 파일로 교체해야 상태 수신 간격만으로
로컬 `FAULT`를 만들지 않는다. ROS-TCP Endpoint에는 2026-09-11부터 다중 Unity
클라이언트별 송신 큐, 토픽별 단일 구독, 최신 카메라 프레임 우선 처리가 포함됐다.
Endpoint 소스가 갱신된 PC는 기존 Endpoint를 종료한 뒤 `Ros2UnityEndopoint_PKG_0.2/
Ros2UnityEndopoint_PKG/run.sh`로 재시작해야 한다.

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
5. FR5 허가 입력은 제거되었다. 작업영역 이탈은 운용자/상위 시퀀서가 확인한다.
6. 실제 장비 적용 전 `CHECKLIST.md`의 monitor-only 시험부터 수행한다.

수동 텔레옵을 사용할 때는 원격 서버가 `IDLE`인지 확인한다. 이 상태의 서버는
`/cmd_vel`에 주기적인 0을 발행하지 않지만, 정지/FAULT 상태에서는 정지 0을
계속 유지한다. 텔레옵을 포함해 `/cmd_vel` publisher는 항상 하나만 실행한다.

2026-09-11 제어 상태 변경: ready/trigger의 주기적인 갱신 중단은 더 이상
heartbeat fault가 아니다. 명시적인 `ready=false`와 stop trigger는 그대로 정지
조건이며, 이동 요청은 호환되는 `/cmd_vel` 로봇 수신기가 있을 때만 접수된다.
수신기가 없으면 `robot command receiver is not connected on /cmd_vel` 사유로
즉시 거절된다.

상세 원본 계약은 저장소의 `docs/CONVEYOR_API_HANDOFF.md`에도 보관되어 있다.
검사 완료 후 JSON·PNG 자료를 Sequencer가 요청·조회하는 최신 계약은
`../vision_sequencer_api/`에 있다. Vision의 DB 직접 쓰기나 MainServer 업로드는 하지 않는다.
