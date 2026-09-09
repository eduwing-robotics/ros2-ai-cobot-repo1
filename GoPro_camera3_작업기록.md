# GoPro HERO11 camera3 작업 기록

- 작업일: 2026-08-06
- 작업 위치: `/home/hc/KSMC/gopro_camera3`
- 용도: 로봇팔 공정 전체 관제, 사각지대 보완, 안전 구역 보조 확인
- 카메라: GoPro HERO11 Black
- 시리얼 번호: `C3471327378198` (OpenGoPro 연결값: 마지막 3자리 `198`)

## 구성

GoPro HERO11은 Linux에서 일반 V4L2 `/dev/video*` 장치가 아니다. 현재는 Wi-Fi Preview를 주 운용 방식으로 사용하고 USB 네트워크(NCM) 기반 Webcam 스트림을 백업으로 남긴다.

영상 흐름:

```text
GoPro HERO11
  -> Wi-Fi Preview 또는 USB OpenGoPro Webcam (MPEG-TS/H.264 UDP)
  -> FFmpeg 저지연 디코딩
  -> ROS2 camera3 노드
  -> /camera3/image_raw/compressed (주 관제 토픽)
  -> /camera3/image_raw (저속 호환 토픽)
```

## 설치 및 생성 파일

- 실행 스크립트: `/home/hc/KSMC/gopro_camera3/run_gopro_camera3.sh`
- Wi-Fi 실행 스크립트: `/home/hc/KSMC/gopro_camera3/run_gopro_camera3_wifi.sh`
- ROS2 노드: `/home/hc/KSMC/gopro_camera3/notebooks/gopro_camera3_node.py`
- OpenGoPro 코드: `/home/hc/KSMC/gopro_camera3/third_party/open_gopro_multi_webcam`
- 카메라 정보: `/home/hc/KSMC/GoPro_카메라_정보.txt`
- ROS2 `v4l2_camera` 패키지는 설치되어 있으나 HERO11 USB 스트림 경로에서는 사용하지 않음.

## GoPro 설정

USB 케이블을 분리한 상태에서 다음을 설정한다.

```text
Preferences -> Connections -> USB Connection -> GoPro Connect
```

그 후 USB 데이터 케이블을 다시 연결한다.

## 실행

주 운용 방식은 Quik 앱으로 전원만 켠 뒤 미리보기 화면에서 나오고, USB Wi-Fi 어댑터를 `GP27378198`에 연결한 다음 실행한다. GoPro의 USB 단자는 노트북이 아니라 전용 충전기에 연결한다.

```bash
cd /home/hc/KSMC
./gopro_camera3/run_gopro_camera3_wifi.sh
```

USB 백업 실행:

```bash
cd /home/hc/KSMC
./gopro_camera3/run_gopro_camera3.sh
```

화면 확인:

```bash
source /opt/ros/jazzy/setup.bash
ros2 run rqt_image_view rqt_image_view
```

`rqt_image_view`에서는 `/camera3/image_raw/compressed`를 선택한다.

프레임 확인:

```bash
ros2 topic hz /camera3/image_raw/compressed
```

## 현재 영상 설정

- 카메라 입력 및 출력 해상도: 1280x720 (장시간 안정성과 발열 억제를 위해 네이티브 720p 사용)
- 목표 프레임: 30Hz
- 압축 품질: JPEG 75
- 화면 오른쪽 아래에 노트북 현지 날짜와 시간을 표시
- ROS QoS: Best Effort, Keep Last, depth 1
- 압축 토픽: `/camera3/image_raw/compressed` (최대 30Hz)
- 원본 토픽: `/camera3/image_raw` (구독자가 있을 때만 약 5Hz)
- FFmpeg 입력: MPEG-TS 강제 지정, H.264 비디오 스트림만 선택
- UDP FIFO: 저지연을 유지하는 범위에서 패킷 순간 변동을 흡수하도록 제한
- 5초 동안 완전한 프레임이 없으면 Wi-Fi Preview 또는 USB Webcam/FFmpeg 파이프라인 자동 재시작
- 5초마다 수신 FPS, 압축 발행 FPS, 재시작 횟수 출력
- HTTP 연결/응답 시간 제한을 적용해 케이블 분리 시 무한 대기 방지

## 수정 이력과 원인

1. ROS setup 전에 `set -u`가 적용돼 `AMENT_TRACE_SETUP_FILES: unbound variable` 발생
   - `/opt/ros/jazzy/setup.bash`를 먼저 source하도록 수정.
2. OpenCV UDP 디코딩에서 프레임 저하와 버퍼 지연 발생
   - FFmpeg 저지연 MPEG-TS/H.264 디코더로 교체.
3. 1280x720 RGB 원본을 30Hz로 ROS 발행해 약 83MB/s의 DDS 부하 발생
   - JPEG 압축 토픽을 주 관제 토픽으로 변경하고 QoS depth를 1로 제한.
4. FFmpeg가 스트림을 MP3로 오인해 `Output file does not contain any stream` 발생
   - 입력 형식을 `mpegts`로 강제하고 `0:v:0` 비디오만 선택.
5. UDP 버퍼를 지나치게 축소해 H.264 매크로블록/참조 프레임 오류 발생
   - UDP FIFO와 소켓 버퍼를 복구해 패킷 유실 방지.
6. Ctrl+C 종료 시 `rcl_shutdown already called` 발생
   - `rclpy.ok()`일 때만 shutdown하도록 수정.

## 참고 및 주의

- GoPro Webcam 스트림은 구조적으로 일정한 지연이 있으며 안전 센서가 아닌 보조 관제용으로만 사용한다.
- 실행 중 H.264 디코딩 오류가 반복되면 USB 링크나 UDP 패킷 손실을 확인한다.
- Ctrl+C 종료 시 FFmpeg의 `Immediate exit requested`가 잠깐 출력되는 것은 정상일 수 있다.
