# KSMC Smart Manufacturing Cell

S22·GoPro 카메라, 컨베이어 제어, 기판 부품 검사를 위한 프로젝트입니다.
ROS 2 서비스로 이동 요청과 검사 요청을 받고 검사 결과를 제공합니다.

## 실행

```bash
cp config/ksmc.env.example config/ksmc.env
./scripts/setup_new_computer.sh
./scripts/doctor.sh
```

컴퓨터별 네트워크·카메라 설정은 `config/ksmc.env`에서 지정합니다.
통합 실행 방법은 [서버 실행 안내](docs/CONVEYOR_VISION_SERVER.md)를 따릅니다.
학습 가중치와 촬영 데이터는 로컬에서 관리하며 Git에 포함하지 않습니다.
검사 실행에는 기존 장비의 정상 기준 이미지
`runtime/inspection/reference/s22_package_legs_golden.png`와 학습 모델도 필요합니다.
저장소 병합만으로 장비별 모델·보정 환경이 설치되지는 않습니다.

## 구성

- `camera2_scrcpy/`, `gopro_camera3/`: 카메라 영상 수신·전송
- `ros2_ws/`: 컨베이어 및 비전 ROS 2 노드와 메시지
- `vision_assembly/`: 기판 검출, 부품 검사, 학습 및 검증 코드
- `calibration/`, `robot_ws/`: 보정 및 로봇 연동 도구
- `config/`, `scripts/`, `run_*.sh`: 환경 설정과 실행 도구
- `docs/`: 실행 안내, 검사 제한사항, 작업 기록

팀원이 운영하는 Unity ROS-TCP Endpoint 서버 소스는 포함하지 않습니다.
기존 ROS 서비스·토픽 연동 계약은 유지합니다.

검사 판정은 현재 임시 PASS/FAIL 정책을 사용합니다. 기존 엄격 판정과
검증 여부도 결과에 보존합니다. 적용 범위와 제한사항은
[검사 안내](vision_assembly/README.md) 및 [비전 작업 기록](docs/logs/vision.md)을 참조하세요.

영상 확인: `./scripts/camera_viewer/run_viewer.sh s22` (또는 `gopro`, `conveyor`).

로봇팔의 기존 파지·상승·놓기·티칭 복귀 코드는 `calibration/run_*.sh`,
트레이 파지 및 기판 배치 코드는 `vision_assembly/run_*hover*.sh`,
`run_full_pick_to_board_hover.sh`에 보존합니다. 보정값은 해당 장비 기준입니다.
