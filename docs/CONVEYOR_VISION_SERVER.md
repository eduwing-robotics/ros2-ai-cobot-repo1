# 컨베이어 + Vision ROS 서버 통합 실행

컨베이어 제어와 촬영·검사 요청/결과/PNG 전송을 ROS 2로 제공합니다.
이동 제어와 검사 작업은 두 개의 독립 프로세스로 유지하며, GoPro도 함께 실행합니다.
이미 실행 중인 GoPro는 재사용합니다. 팀원이 실행하는 ROS-TCP Endpoint와 S22 실행은 변경하지 않습니다.

## 준비

새 서비스 타입을 서버와 클라이언트 PC에 빌드하세요.

```bash
source /opt/ros/jazzy/setup.bash
cd ~/KSMC/ros2_ws
colcon build --packages-select vision_interfaces
source install/setup.bash
```

S22 카메라/정지선 ROI는 기존 방식으로 실행되어 있어야 합니다. 통합 실행기는
S22나 Endpoint를 실행·종료하지 않습니다. 기존 개별 서버나 통합 서버가 있으면
중복 실행을 거절합니다. 전환 시 컨베이어가 정지하고 검사 작업이 끝난 뒤 기존
서버를 종료하고 새로 실행합니다. 실행 중인 프로세스를 자동 인수하지 않습니다.

## 실행

사전 확인만(서버·촬영·모터 시작 없음):

```bash
~/KSMC/run_conveyor_vision_server.sh --check
```

기본 모드(컨베이어 이동 요청 거절):

```bash
~/KSMC/run_conveyor_vision_server.sh --monitor-only
```

운전 가능 모드(시작 자체로 이동하지 않음):

```bash
~/KSMC/run_conveyor_vision_server.sh --execute --confirm-motion
```

monitor-only는 컨베이어 이동 허용 여부입니다. 검사 서버는 별도의 명시적 요청과
현재 검사 위치 정지 조건이 충족되면 촬영할 수 있습니다.
`--timeout 300`은 검사 실행 제한, `--startup-timeout 20`은 서비스 시작 대기입니다.
GoPro가 포함되면 `--gopro-startup-timeout 45`와의 큰 값을 전체 시작 대기로 사용합니다.
기본 GoPro 실행은 현재 연결 방식인 Wi-Fi입니다. USB라면 다음처럼 지정합니다.

```bash
~/KSMC/run_conveyor_vision_server.sh --monitor-only --gopro-transport usb
```

이미 GoPro 프로세스/잠금 또는 호환 ROS 발행자가 있으면 기존 스트림을 재사용하고
종료 시 그대로 둡니다. 새로 시작한 GoPro는 이 통합 실행기가 종료를 관리합니다.
별도 실행과 경쟁해서 GoPro 잠금을 놓친 경우에도 기존 프로세스를 재사용합니다.
카메라 없이 서버 두 개만 실행하려면 `--without-gopro`를 지정합니다.
GoPro 장치의 Wi-Fi preview/USB Webcam 제어는 기존 드라이버를 사용하며, 외부에
제공하는 영상은 `/camera3/image_raw/compressed` ROS 토픽입니다.
HTTP 포트/토큰은 사용하지 않으며 `--host/--port`는 지원하지 않습니다.
ROS 환경은 `config/ksmc.env`와 기존 DDS 설정, 기본 ROS_DOMAIN_ID=5를 따릅니다.

## 연동

- 이동/정지: 기존 `/conveyor/move_to_assembly`, `/conveyor/move_to_inspection`,
  `/conveyor/stop`, `/conveyor/reset` (`std_srvs/srv/Trigger`).
- 검사: `/vision/inspection/submit`, `/vision/inspection/get`,
  `/vision/inspection/get_image`, `/vision/inspection/health`.
- 상태: 기존 `/conveyor/state`, `/conveyor/moving` 및 `/vision/inspection/state`.

[검사 ROS 계약과 클라이언트 예제](../team_handoff/vision_sequencer_api/ROS_API.md)에
서비스 타입, ID 재시도 규칙, JSON 결과, PNG 조각/해시 검증을 정리했습니다.
Sequencer/MainServer 팀원은 이전 HTTP 호출을 이 서비스로 교체해야 합니다.
도착만으로 촬영하지 않으며, UNKNOWN 및 ADVISORY_ONLY의 판정 권한을 유지합니다.
Vision에서 MainServer 직접 업로드나 DB 쓰기는 하지 않습니다.

`ROS services ready`는 두 서버 노드의 서비스 이름/타입과, 활성화된 GoPro의
최근 프레임 수신을 확인했다는 뜻입니다. 토픽 이름이나 서비스 클라이언트만
존재하는 경우는 준비 완료로 보지 않습니다. 카메라 품질이나
물리 안전/실제 촬영 성공을 보증하는 메시지는 아닙니다.

Ctrl+C 또는 소유 서버 하나의 종료 시 이 실행기가 시작한 프로세스 그룹만 정리합니다.
검사 자식 프로세스 종료 및 컨베이어 안전정지 경로를 유지하며, 자동 재시작/재촬영/
이동 재요청을 하지 않습니다. 재사용 중인 GoPro·외부 S22·Endpoint·기존 서버를 종료하지 않습니다.
새로 시작한 GoPro가 종료되면 다른 소유 서버도 기존 안전종료 경로로 정리합니다.
재사용 GoPro는 외부 소유이므로 이 실행기가 재시작하지 않습니다.

팀원 rqt 화면 문제는 [수신 진단/뷰어 실행 도구](../team_handoff/rqt_camera/README.md)를
그 팀원 PC에서 사용해 확인할 수 있습니다.
