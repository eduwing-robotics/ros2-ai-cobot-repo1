# FR5 Robot Control

FAIRINO FR5, PGEA-100-40 gripper, gripper-mounted RealSense D435 and ROS 2
Jazzy를 한 곳에서 개발하기 위한 통합 작업 폴더다.

이 프로젝트의 기준 구현은 이 디렉터리다. 원본
`ros2-ai-cobot-repo1`과 `FR5_AIR_DEMO_20260817`은 이관 근거로만 보존하며,
새 기능은 이 폴더에서 개발한다.

## 목표 제어 흐름

```text
D435 RGB + aligned depth + 현재 FR5 flange pose
  -> Camera 좌표의 부품/슬롯 관측
  -> Hand-Eye(T_flange_camera)로 Base 좌표 변환
  -> freshness/workspace/offset 검증
  -> dry-run pick/place plan
  -> 단일 motion executor를 통한 FR5 실행
  -> hover에서 재관측 후 제한된 폐루프 보정
```

카메라는 Eye-in-Hand 구조다. 영상 픽셀을 바로 로봇 명령으로 사용하지 않는다.
항상 다음 변환을 사용한다.

```text
T_base_target = T_base_flange @ T_flange_camera @ T_camera_target
```

## 디렉터리

- `robot_ws/`: FAIRINO 벤더 ROS 2 드라이버와 명령 서버
- `ros2_ws/src/vision_interfaces`: 비전 메시지 정의
- `ros2_ws/src/vision_server`: 카메라·검출·aligned depth 처리
- `ros2_ws/src/fr5_process_sequences`: 안전조건을 검사하는 dry-run 플래너
- `calibration/`: D435/ChArUco/Hand-Eye 코드와 활성 보정값
- `vision_assembly/`: 부품·기판·슬롯 검출 및 기존 단계별 이동 실험
- `teach_points/`: 공중 시험용 provisional 교시점
- `references/`: 로봇 제어 아키텍처와 commissioning 기준
- `docs/MIGRATION.md`: 두 원본에서 가져온 범위와 제외 항목

## 최초 설정과 빌드

```bash
cd /home/juchan-yoon/FR5_robot_control
cp config/ksmc.env.example config/ksmc.env
./scripts/build_all.sh
./scripts/doctor.sh
./scripts/test_all.sh
```

`config/ksmc.env`는 장비별 값이므로 Git에 넣지 않는다.

## 안전한 개발 순서

1. D435 RGB-D와 CameraInfo 토픽만 확인한다.
2. FR5 상태를 읽기 전용으로 확인한다.
3. 부품 검출과 Camera→Base 변환을 로봇 이동 없이 검증한다.
4. `fr5_process_sequences`로 전체 경로를 dry-run 검증한다.
5. 작업자가 확인한 뒤 10% 이하 속도로 관측 자세→hover만 시험한다.
6. hover 재관측의 반복성이 확인된 뒤 짧은 보정과 수직 하강을 별도 승인한다.

기존 `vision_assembly/scripts/full_pick_to_board_hover.py`는 실험 이력으로
포함되어 있지만 실제 실행 전용이며 기본 속도와 target freshness 정책이 최종
안전 기준에 맞지 않는다. 통합 motion executor가 완성되기 전 자동운전에
사용하지 않는다.

## 현재 상태

- D435 aligned depth 및 CameraInfo 처리: 이관 완료
- 활성 Eye-in-Hand 결과와 좌표변환 코드: 이관 완료
- 비전/보드/부품 검출 코드: 이관 완료
- FR5 벤더 드라이버와 상태/명령 서버: 이관 완료
- 안전 dry-run pick/place 플래너: 이관 완료
- 비전 목표와 플래너의 typed ROS 계약: 다음 구현 단계
- 단일 안전 motion executor와 hover 재관측 루프: 다음 구현 단계
- 실제 접촉·파지·배치 자동운전 승인: 미완료

