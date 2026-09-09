# 컨베이어 + Vision 서버 통합 실행

기존 서버 코드는 그대로 두고 **한 터미널에서 두 프로세스를 관리**합니다.
ROS 정지 제어와 HTTP 촬영/검사 처리를 같은 실행 스레드로 합치지 않습니다.
팀원은 기존 서비스/API 그대로 사용합니다. 토큰도 재발급하지 않습니다.

## 기존 연결 유지

- 이미 개별 서버가 켜져 있다면 그대로 사용하세요. 새 실행기는 기존 프로세스,
  검사 잠금, HTTP 포트 또는 ROS 컨베이어 서비스가 발견되면 **시작을 거절**합니다.
  기존 서버를 종료·인수·재시작하지 않습니다.
- 통합 실행기로 전환은 **검사 요청이 없고 컨베이어가 정지한 때**, 팀원과 확인 후
  기존 두 서버를 사용자가 종료하고 다음 실행부터 합니다. 무중단 인수 기능은 아닙니다.
- S22 카메라/정지선 화면은 현재 실행 방식을 유지합니다. 이 실행기는 카메라를
  재시작하지 않습니다. 카메라까지 시작하는 `run_s22_conveyor_auto_inspection.sh`와
  동시에 실행하면 검사 API가 중복되므로 함께 사용하지 마세요.

## 실행

사전 확인만(서버·촬영·모터 실행 없음):

```bash
~/KSMC/run_conveyor_vision_server.sh --check
```

팀원 API 연결 확인용(이동 요청 거절, 기본 모드):

```bash
~/KSMC/run_conveyor_vision_server.sh --monitor-only
```

실제 운전 가능 모드(작업구역 안전 확인 후):

```bash
~/KSMC/run_conveyor_vision_server.sh --execute --confirm-motion
```

시작 자체는 이동 명령이 아닙니다. 팀원 이동 요청과 기존 S22/FR5 안전 조건이 모두
충족되어야 움직입니다. `/cell/fr5_clear_for_conveyor` 신호 요구를 없애지 않습니다.
설비 비상정지는 계속 사용할 수 있어야 합니다.

기본 HTTP 바인딩은 `0.0.0.0:8766`이며 신뢰 LAN에서만 사용합니다. 기존 고정 토큰
파일 `config/private/vision_api.token`을 읽되 화면·로그·명령행에 토큰을 출력하지 않습니다.
IP/DDS 설정은 바꾸지 않으며 `config/ksmc.env`와 기존 환경(기본 ROS_DOMAIN_ID=5)을 따릅니다.
필요한 경우 `--host`, `--port`, `--timeout`만 동일하게 지정하세요.

## 팀원 계약 — 변경 없음

- ROS: `/conveyor/move_to_assembly`, `/conveyor/move_to_inspection`, `/conveyor/stop`,
  `/conveyor/reset` (`std_srvs/srv/Trigger`), `/conveyor/state`, `/conveyor/moving`.
- HTTP: `POST /api/v1/inspections`, `GET /api/v1/inspections/{id}`,
  `GET /api/v1/inspections/{id}/image`.
- 동일 Bearer 토큰, job_id/unit_id/inspection_id, 요청 중복 방지, JSON+PNG 방식 유지.
- **도착만으로 별도 검사하지 않습니다.** Sequencer 요청 + 최신 검사 위치 정지 상태
  확인 후 촬영합니다. 202 수락과 검사 완료를 구분하며 UNKNOWN을 PASS로 바꾸지 않습니다.
- MainServer 직접 업로드/DB 쓰기 추가 없음. 결과 저장 위치도 기존 그대로입니다.

`Servers listening`은 네 ROS 서비스와 TCP 포트를 확인했다는 뜻입니다.
카메라 영상 품질, 정지 위치, FR5 안전 신호, 실제 촬영 성공을 보증하지 않습니다.

## 종료·오류

Ctrl+C는 **이 실행기가 시작한 두 서버만** 종료합니다. 검사 자식 정리 및 컨베이어
안전정지는 기존 서버의 종료 경로를 사용하고, 응답이 없으면 해당 소유 프로세스 그룹만
단계적으로 종료합니다. 외부에서 실행한 카메라나 다른 서버는 종료하지 않습니다.
실행 중 한 서버가 죽으면 다른 소유 서버도 종료하고 오류를 알립니다. 자동 재시작,
자동 재촬영 또는 이동 재요청을 하지 않습니다.

전환 후 실제 팀원 측 요청/촬영 연동은 별도 확인해야 합니다. 기존 서버가 실행된 채로
강제 전환하거나 토큰/IP를 변경하는 명령은 제공하지 않습니다.
