# 팀원 PC의 rqt 카메라 화면

**이 폴더를 영상을 보는 팀원 PC에 복사해서 실행합니다.** Endpoint나 카메라
서버를 실행·수정하는 도구가 아닙니다. ROS 2, `sensor_msgs`, `rqt_image_view`,
`python3-opencv`가 필요합니다. ROS_DOMAIN_ID 기본값은 5입니다.

```bash
bash run_viewer.sh conveyor
bash run_viewer.sh s22
bash run_viewer.sh gopro
bash run_viewer.sh assembly
```

각 명령은 하나씩 원하는 화면을 열 때 사용합니다. 직접 토픽도 지정할 수 있습니다.

```bash
bash run_viewer.sh /vision/assembly/image/compressed
```

이 도구는 먼저 BEST_EFFORT로 CompressedImage를 받아 디코딩합니다. 성공하면
해당 PC에서 `/ksmc/rqt_<PID>/image`에 bgr8 Image를 발행하고 그 화면으로 새 rqt를
엽니다. compressed 플러그인, 직접 입력한 토픽의 transport 오인, 이전 rqt 선택
설정에 의존하지 않습니다. 원본 JPEG/PNG나 서버 FPS/QoS는 바꾸지 않고 로컬
표시만 기본 15 FPS로 제한합니다. 새 뷰어를 닫으면 중계도 종료됩니다.
기본 8초 동안 입력이 끊기면 오래된 화면을 남기지 않고 새 뷰어를 닫습니다.
rqt 설정은 임시 디렉터리로 분리하므로 기존 rqt의 저장 설정도 보존합니다.
기존 rqt, Endpoint, 카메라, 컨베이어 프로세스는 종료하지 않습니다.

## 리스트만 보이고 프레임이 없는 경우

팀원 PC에서 먼저 GUI 없이 확인하세요.

```bash
bash run_viewer.sh s22 --check
bash run_viewer.sh gopro --check
bash run_viewer.sh conveyor --check
bash run_viewer.sh assembly --check
```

- `OK`, received/decoded 증가: 해당 PC까지 영상이 도착합니다. 일반 실행으로
  새 rqt를 열면 됩니다. `--check`는 발행/GUI 없이 구독만 합니다.
- `NO_PUBLISHER`: ROS domain, DDS discovery, 발행 노드 실행 여부를 확인합니다.
- `NO_FRAMES`: 발행자 발견과 데이터 수신은 별개입니다. 소스가 실제 발행 중인지,
  양쪽 DDS 인터페이스/방화벽/공유기 클라이언트 격리를 확인해야 합니다.
- `DECODE_FAILED`: 바이트는 도착했으나 이미지가 아닙니다. format/소스 로그를 확인합니다.

화면이 안 나오는 PC의 IP와 이 결과가 있어야 원격 수신 문제를 확정할 수 있습니다.
서버에서 실행한 `--check` 성공만으로 팀원 화면 복구를 보장하지 않습니다.
네트워크/방화벽은 이 도구에서 자동 변경하지 않습니다. 노트북 전용
`fastdds_laptop.xml`의 `wlo1`, `enp129s0` allowlist를 다른 PC에 그대로 쓰지 마세요.
기존 RMW/DDS 프로파일은 보존하므로 잘못 복사한 프로파일이 있다면 해당 PC에 맞게
별도 수정해야 합니다. 설정 경로는 도구 첫 줄에 표시됩니다.

일반 rqt 목록에서 선택할 때는 새로고침 후 목록의 압축 영상 항목을 선택합니다.
표시 이름은 `/.../compressed`여도 내부적으로 base topic + compressed transport를
사용합니다. 직접 입력/시작 시점에 따라 raw 타입으로 잘못 생성될 수 있어 위 도구는
로컬 raw 토픽을 사용합니다.
[rqt 공식 구현](https://github.com/ros-visualization/rqt_image_view/blob/rolling-devel/src/rqt_image_view/image_view.cpp).
