# S22 DroidCam camera2

## 권장 USB 실행

S22를 USB로 연결하고 USB 디버깅을 허용한 뒤, 휴대폰에서 DroidCam 앱을 켠다.
컨베이어 정지선 화면까지 한 번에 실행하려면 다음 명령 하나만 사용한다.

```bash
./run_s22_conveyor.sh
```

카메라 토픽만 실행하려면 다음을 사용한다.

```bash
./camera2_droidcam/run_camera2_usb.sh
```

장비별 S22 serial은 `config/ksmc.env`에 저장한다. serial을 생략하고 ADB 장치가
하나만 연결되면 자동 선택한다. 기본 `/dev/video10`, `1920x1080`, JPEG 품질 95,
`ROS_DOMAIN_ID=5`를 사용한다. 실행 시 다음을 자동
처리한다.

- ADB 권한 및 S22 연결 확인
- S22 화면 깨우기와 DroidCam 앱 전면 실행
- 이전 Wi-Fi/USB DroidCam 및 camera2 프로세스 정리
- ADB 4747 forward 초기화
- 초기 연결 실패 시 최대 5회 재시도
- 실행 중 DroidCam 또는 ROS 노드 종료 시 자동 재연결
- `Ctrl+C` 시 관련 자식 프로세스 정리

RQT Image View에서 원본은 `/camera2/image_raw/compressed`, 컨베이어의 조립·검사
2중 정지선 화면은 `/vision/conveyor/stop_image/compressed`를 선택한다. 카메라
실행기는 영상만 제공하며 실제 `/cmd_vel`은 별도 컨베이어 제어기가 발행한다.

## 재부팅 후 가상 카메라 자동 생성

아래 프로젝트 설정 파일은 시스템에 한 번 설치하면 된다.

```bash
sudo install -m 0644 \
  ./camera2_droidcam/v4l2loopback-ksmc.modules \
  /etc/modules-load.d/ksmc-droidcam.conf

sudo install -m 0644 \
  ./camera2_droidcam/v4l2loopback-ksmc.conf \
  /etc/modprobe.d/ksmc-droidcam.conf
```

설치하지 않아도 실행 스크립트가 `/dev/video10`이 없을 때 `sudo modprobe`를
시도하지만, 자동 로드 설정을 설치하면 매 실행 시 sudo가 필요하지 않다.
