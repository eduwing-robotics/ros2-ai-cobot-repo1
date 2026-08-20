# FR5 Eye-in-Hand 캘리브레이션 작업 기록

기록일: 2026-08-06

## 현재 상태

- RealSense 깊이 카메라는 FR5 그리퍼 쪽에 장착하여 Eye-in-Hand 방식으로 사용할 예정이다.
- 임시 거치대에서 카메라가 약 3 mm 빠져 장착 변환이 바뀌었으므로 기존 캘리브레이션은 무효 처리했다.
- 기존 보정 샘플 35개, 검증 샘플 5개, 이미지 및 계산 결과는 사용자 요청으로 삭제했다.
- 새 거치대가 제작되고 카메라가 단단히 고정될 때까지 캘리브레이션 작업을 중단한다.
- 로봇 자동 이동 및 파지에는 이전 계산값을 사용하지 않는다.

## 확정된 설정

- 방식: Eye-in-Hand
- 로봇 자세: `base -> flange`
- 고정 타깃: 카트 상판의 ChArUco 보드
- OpenCV 생성 규격: `squares_x=5`, `squares_y=7` (실물은 90° 돌려 가로 7칸 × 세로 5칸으로 설치됨)
- ArUco 사전: `DICT_5X5_50`
- A4 출력 배율: 체크선 100 mm가 96 mm로 출력되어 `96%` 균일 축소로 적용
- 실제 출력 체스 칸 한 변 길이: `0.0336 m` (3.36 cm)
- 실제 출력 내부 ArUco 마커 한 변 길이: `0.0168 m` (1.68 cm)
- 실제 출력 보드 전체 격자 크기: `0.2352 × 0.1680 m` (가로 방향 설치 기준)
- 기존 `DICT_4X4_50`, 단일 ID 0, 29 mm 설정은 폐기하며 재사용하지 않는다.
- 압축 컬러 영상: `/camera/camera/color/image_raw/compressed`
- 카메라 정보: `/camera/camera/color/camera_info`
- 로봇 상태: `/nonrt_state_data`

## 남겨둔 파일

- `~/KSMC/calibration/config/charuco_board.yaml`
- `~/KSMC/calibration/scripts/detect_aruco_id.py`
- `~/KSMC/calibration/scripts/capture_handeye_sample.py`
- `~/KSMC/calibration/scripts/solve_handeye.py`

## 새 거치대 설치 후 재개 절차

1. 카메라를 새 거치대에 완전히 삽입하고 나사 등으로 움직이지 않게 고정한다.
2. 케이블 장력이 카메라를 당기지 않는지 확인한다.
3. 캘리브레이션이 끝날 때까지 카메라, 거치대, 고정 마커를 건드리지 않는다.
4. RealSense와 FR5 ROS 노드를 실행한다.
5. ChArUco 보드 검출을 확인한다. 기존 단일 ArUco 검출/수집 스크립트는 ChArUco 전용으로 교체한 뒤 사용한다.

```bash
source /opt/ros/jazzy/setup.bash
source ~/KSMC/robot_ws/install/setup.bash
python3 ~/KSMC/calibration/scripts/detect_charuco_board.py
```

정상 출력 예시:

```text
Detected ChArUco board: DICT_5X5_50, corners: ...
```

6. 서로 다른 로봇 위치와 손목 각도에서 샘플을 수집한다.

```bash
python3 ~/KSMC/calibration/scripts/capture_charuco_handeye_sample.py
```

7. 권장 샘플 수는 25~30개이다. 위치뿐 아니라 J6 회전, 전후 기울기, 좌우 기울기를 다양하게 포함한다.
8. 모든 자세에서 로봇을 완전히 정지시키고 마커 전체와 검은 테두리가 보이게 한다.
9. 수집 후 계산한다.

```bash
python3 ~/KSMC/calibration/scripts/solve_handeye.py
```

10. 계산 결과를 로봇 동작에 바로 사용하지 말고, 별도 검증 샘플 5개로 고정 마커의 베이스 좌표 일관성을 먼저 확인한다.

```bash
python3 ~/KSMC/calibration/scripts/capture_charuco_handeye_sample.py \
  --data-file ~/KSMC/calibration/data/validation_samples.json
```

## 품질 기준 및 주의사항

- 좋은 샘플 25~30개면 충분하며 비슷한 자세를 많이 반복하는 것은 도움이 적다.
- 카메라 장착 위치가 1~3 mm라도 움직이면 기존 Eye-in-Hand 결과를 재사용하지 않는다.
- 고정 마커의 베이스 좌표 위치 편차가 3 mm 이내인지 우선 확인한다.
- 3~5 mm는 큰 물체의 저속 시험 수준이며, 5 mm 이상이면 정밀 파지 전에 재보정한다.
- 검증이 끝나기 전에는 자동 접근, 하강, 그리퍼 파지를 수행하지 않는다.

## 이전 실패 기록

- 임시 거치대 상태에서 계산된 위치 잔차는 중앙값 약 8.08 mm, 최대 약 42.98 mm였다.
- 별도 5자세 검증에서도 위치 오차 중앙값 약 5.13 mm, 최대 약 17.33 mm였다.
- 카메라 이탈과 일부 이상치가 확인되어 해당 데이터는 모두 폐기했다.

---

## 2026-08-11 작업 기록

### 프로젝트 기준 확정

- 최종 목표를 `컨베이어 + 다중 카메라 비전 + FR5 정밀 조립 + 검사 +
  PASS/FAIL + UI/로그`가 통합된 반도체 패키지형 전자모듈 스마트 제조
  셀로 확정했다.
- 프로젝트 전체 설계 원칙은 `~/KSMC/PROJECT_GOAL.md`에 기록했다.
- 현재 단계는 D435 Eye-in-Hand Camera-to-Base 좌표 정확도 검증이며, 자동
  Pick/하강은 아직 구현하지 않는다.

### 현재 Hand-Eye 결과와 검증

- 사용 샘플: 40개
- OpenCV 방법: DANIILIDIS, Euler `xyz`
- 저장된 `T_flange_camera` translation:
  `[-31.949, -83.038, 59.783] mm`
- 독립 검증 5자세 Euclidean error:
  평균 `1.833 mm`, 중앙값 `1.804 mm`, 최대 `2.981 mm`
- 오프라인 검증 도구 추가:
  `calibration/scripts/validate_handeye_samples.py`

### 마커 목표 계산 개선

- 경험적으로 넣었던 Camera-to-TCP XY 보정을 모두 `0 mm`으로 제거했다.
- 로봇 플랜지가 1초 이상 정지한 뒤에만 영상 샘플을 사용한다.
- 수집 중 로봇 자세가 변하면 해당 프레임 묶음을 폐기한다.
- 최초 목표 계산 후 `TARGET LOCKED` 상태로 전환하여 이동 중 영상이
  목표 좌표 또는 결과 JSON을 덮어쓰지 못하게 했다.
- 마커 +Z를 고정 사용하지 않고 카메라를 향하는 보드 법선을 선택한다.
- 다음 행렬과 rvec/tvec을 터미널 및 JSON에 출력하도록 추가했다:
  `T_base_flange`, `T_flange_camera`, `T_camera_board`, `T_base_marker`,
  `T_base_target`.
- 명시적 실행 모드 `--dry-run`, `--execute --confirm-move`를 추가했다.

### 마커 8 반복성

- 100 mm dry-run marker center:
  `[-315.938, -28.053, -15.207] mm`
- 120 mm dry-run marker center:
  `[-315.757, -27.462, -14.865] mm`
- 두 측정 차이 약 `0.71 mm`; 120 mm 측정 프레임 jitter
  median/max `0.013/0.041 mm`.
- 종이 포인터는 Tool RZ 회전 시 원을 그려 실제 TCP 축과 정렬되지 않은
  것으로 판단했다. 종이 끝에서 측정한 XY 오차는 Hand-Eye 보정에 넣지
  않는다.

### TCP 현재 주의 상태

- 기존 4-point 결과는 `toolcoord1 = [3.679, 8.900, 165, 0, 0, 0] mm/deg`였다.
- 사용자가 웹에서 시험 목적으로 `toolcoord1 = [0, 0, 160, 0, 0, 0]`으로
  변경했다.
- Tool RZ 회전에서는 중심 이동이 눈에 띄지 않았지만, RZ만으로 Z 길이는
  검증할 수 없다. RX/RY 회전 또는 4-point 재검증 전에는 정밀 조립용
  TCP로 확정하지 않는다.
- 이후 사용자가 `toolcoord1 = [-2, -2, 157, 0, 0, 0] mm/deg`로 조정했다.
- 이 설정에서 마커 중심 100 mm 위 목표로 이동한 다음 Tool 방향으로
  100 mm 수동 하강했을 때 실제 중심이 마커와 일치했다.
- 현재 가장 유력한 TCP 후보이지만 한 위치에서의 결과이므로, 다른 마커와
  다른 관측 자세에서 동일하게 맞는지 확인한 뒤 최종 TCP로 확정한다.
- 이후 같은 ChArUco 보드의 서로 다른 마커 약 5개를 시험했으며, 모두
  마커 중심의 동일한 목표 위치에 도착했다.
- 따라서 보드 내부 마커 중심 계산과 `toolcoord1 = [-2, -2, 157, 0, 0, 0]`
  조합의 평면 XY 정합은 현재 시험 범위에서 재현됐다. 다음 최종 검증은
  카메라 관측 자세를 바꾼 상태에서도 같은 고정 마커 Base 좌표와 실제
  도착점이 유지되는지 확인하는 것이다.

### D435 영상 중단 원인과 안정 모드

- `1920x1080x30 RGB + 848x480x30 Depth + align` 실행 중 RealSense 로그에서
  `Incomplete video frame detected`가 확인됐다. 정상 약 4.15 MB 프레임 중
  13~62%만 수신된 USB 프레임 손상이다.
- 이전에는 RealSense 노드 중복 실행으로 UVC probe 오류, USB disconnect,
  xHCI endpoint 경고도 발생했다. RealSense 노드는 항상 하나만 실행한다.
- 현재 ArUco/ChArUco 단계에서는 RGB만 필요하므로 다음 안정 모드로 전환했다:
  RGB `1920x1080x15`, Depth 비활성, align 비활성, reconnect 2초,
  시작 시 device reset.
- 안정 모드 확인 결과 RGB 압축 토픽 약 `14.99 fps`, ChArUco 주석 영상 약
  `14.98 fps`.
- 재실행 스크립트: `calibration/run_d435_rgb_stable.sh`

### 마커 접근 속도 조정

- WebApp 속도 슬라이더보다 스크립트의 `SetSpeed`/`MoveCart` 인자가 우선해
  웹에서만 속도를 올려도 마커 접근 속도가 증가하지 않는 원인을 확인했다.
- 검증된 안전 경로의 수평 이동 기본/최대 속도를 `30%`에서 `40%`로 올렸다.
- Tool 자세 정렬, 상승 및 목표 높이로의 수직 접근은 기존 기본/최대
  `15%`를 유지한다.

### 마커 8 관측 자세 의존성 검증

- 같은 관측 위치에서 정면, Tool RY 약 `-10°`, Tool RY 약 `+10°`의 세
  자세로 동일한 고정 마커 8을 각각 30프레임 dry-run 측정했다.
- Pose 1(정면): `[-316.092, -27.530, -15.139] mm`
- Pose 2(RY -9.998°): `[-316.686, -27.433, -12.871] mm`
- Pose 3(RY +10.004°): `[-315.183, -27.565, -12.361] mm`
- 축별 전체 범위: X `1.502 mm`, Y `0.132 mm`, Z `2.778 mm`
- Pose 1 기준 3D 차이: Pose 2 `2.347 mm`, Pose 3 `2.923 mm`
- 세 자세 최대 pairwise 차이: `2.923 mm`
- 각 자세 영상 내부 jitter 최대는 `0.036~0.045 mm`로 매우 안정적이므로
  프레임 흔들림이 아니라 Hand-Eye/자세 추정의 체계적 잔여 오차로 본다.
- 현재 오차는 기존 독립 검증 최대 `2.981 mm`와 일치한다. 일반 접근
  시험에는 사용할 수 있지만 반도체 모형 정밀 배치를 위해서는 특히 Z와
  RY 연동 오차를 추가 개선해야 한다.
- 기존 40개 샘플에 robust 비선형 최적화를 오프라인 시험했으나 독립 검증
  평균/최대가 `1.833/2.981 mm`에서 `1.863/3.074 mm`로 악화됐다.
- 이 후보는 폐기했고 `handeye_result.json`은 변경하지 않았다. 다음 개선은
  정지 1초 대기와 자세 안정성 검사가 적용된 수집 코드로 회전 다양성이 큰
  새 샘플을 별도 파일에 수집한 뒤 기존 결과와 비교하는 방식으로 진행한다.
- 새 샘플 15개용 자세 계획을 `calibration/HANDEYE_REFINEMENT_POSES.md`에
  작성했다. 모든 자세는 저장된 정면 관측 자세에서 다시 시작하며, 위치
  변화는 Base XYZ, 카메라 기울기/화면 회전은 Tool RX/RY/RZ로 조작한다.
- Refinement 샘플 1~7 저장 완료: 정면, Tool RY ±10°, Tool RY ±15°,
  Tool RX ±10°. 모두 17/17 markers와 24/24 corners를 사용했다.
- 8번째 시도는 sample 4(RY +15°)와 동일한 로봇 자세여서 중복 방지 기능이
  저장을 거부했다. Pose 8은 정면 자세로 복귀한 뒤 Tool RX +15°로 다시
  수집해야 한다.
- Refinement 샘플은 최종 15개가 저장됐으며 기존 결과 파일에는 아직
  적용하지 않았다.
- 기존 정상 기준본을
  `calibration/archive/before_refinement_20260811/`에 추가 백업했다:
  `handeye_result.json`, 기존 40개 `handeye_samples.json`, 독립 검증
  `validation_samples.json`. 원본과 백업본의 SHA-256이 각각 일치함을
  확인했다.
- 카메라, FR5 서버, ChArUco 화면, 샘플 저장, 마커 dry-run/실행, 속도
  조절 및 검증 명령을 `calibration/RUN_COMMANDS.md`에 한 번에 복사해
  사용할 수 있도록 정리했다.

### Refinement 15개 적용 전 비교 결과

- 기존 40개 결과, 새 refinement 15개 단독 결과, 40+15 결합 결과를 같은
  독립 검증 5자세에 오프라인으로 비교했다. 로봇 이동 명령은 보내지 않았다.
- 기존 40개(DANIILIDIS): 독립 검증 3D 오차 평균/중앙/최대
  `1.833/1.804/2.981 mm`.
- 새 15개 단독(PARK): 독립 검증 3D 오차 평균/중앙/최대
  `14.517/14.909/30.062 mm`. 추정 Camera-to-Flange Z도 기존
  `59.783 mm`에서 `10.523 mm`로 크게 벗어나 부적합하다.
- 40+15 결합(HORAUD): 독립 검증 3D 오차 평균/중앙/최대
  `2.074/1.606/3.359 mm`로 기존보다 평균과 최대 오차가 악화됐다.
- 따라서 refinement 데이터는 현재 결과에 적용하지 않았고,
  `calibration/data/handeye_result.json`은 기존 정상 40개 결과를 유지한다.
- 새 15개는 삭제하지 않고 원인 분석용
  `calibration/data/handeye_refinement_samples.json`으로 보존한다.

### 2026-08-11 작업 종료 점검

- 오늘 변경 사항, 실행 명령, 속도 조절 방법, 백업 위치, TCP 주의 상태,
  D435 안정 모드, refinement 비교 결과가 기록돼 있는지 다시 확인했다.
- 기존 적용 결과와 백업본 `handeye_result.json`의 SHA-256이 동일하며,
  기존 정상 40개 결과가 유지되고 있다.
- refinement 15개 데이터는 별도 파일에 보존돼 있고 실제 보정값에는
  적용하지 않았다.
- 실행 중 프로세스를 점검한 결과 RealSense, ChArUco 표시 노드, rqt,
  FR5 ROS 명령 서버, 캘리브레이션/마커 이동 노드는 모두 이미 종료돼
  있었으며 ROS 노드 목록도 비어 있었다. 강제 종료한 프로세스는 없다.
- 다음 작업은 refinement 15개 자세 분포와 불량 샘플 원인을 분석한 뒤,
  필요한 자세만 재수집하여 기존 40개 결과와 독립 검증으로 비교하는 것이다.

---

## 2026-08-12 작업 기록

### 좌표계 진단 기능 착수

- 기존 코드를 다시 점검해 런타임 체인이
  `T_base_flange @ T_flange_camera @ T_camera_board`임을 확인했다.
- Hand-Eye에는 FR5 `flange_*_cur_pos`, 실제 TCP 이동/상태에는
  `cart_*_cur_pos`와 `tool_num`을 사용하므로 TCP와 카메라 extrinsic의
  중복 적용은 발견되지 않았다.
- OpenCV ChArUco `rvec/tvec`은 board object 좌표를 camera 좌표로 변환하는
  `T_camera_board`임을 확인했다.
- 기존 Hand-Eye 결과를 수정하지 않고 별도 무동작 멀티포즈 검증 노드
  `calibration/scripts/validate_handeye_multipose.py`를 추가했다.
- 한 자세당 안정 프레임을 묶어 동일 마커 중심의 Camera/Base XYZ, Flange와
  TCP pose, 코너 수, reprojection error, intrinsic/해상도, 사용 행렬과
  Hand-Eye 파일 해시를 CSV에 저장한다.
- 누적 CSV에서 Base XYZ 평균/표준편차, 자세별 오차, 3D 최대 오차, RMS 및
  카메라 Base 회전과 3D 오차의 Pearson 상관계수를 출력한다.
- 실제 영상 해상도와 `CameraInfo.width/height`가 다르면 저장을 차단한다.
- 기존 마커 접근 노드에 `--approach-frame base_z|board_normal`을 추가했고,
  기본값을 `base_z`로 설정했다. Base-Z 방식은 마커 Base X/Y를 유지하고
  Base Z에만 지정 안전 높이를 더한다.
- 실행 래퍼 `calibration/run_handeye_multipose_validation.sh`, 좌표계 분석
  문서 `calibration/COORDINATE_DIAGNOSTIC.md` 및 실행 명령을 추가했다.

### ChArUco 표시 깜빡임 원인 확인

- ROS Domain 5에서 실행 상태를 확인한 결과 D435가 RGB `640x480@30`이며
  Depth 스트림도 활성화된 일반 설정으로 실행 중이었다.
- 어제 검출이 안정적이었던 설정은 RGB `1920x1080@15`, Depth/align 비활성
  안정 모드다. 작은 16.8 mm 마커를 640x480 영상으로 보면 경계 픽셀 수가
  부족해 마커와 코너 검출이 프레임별로 깜빡일 수 있다.
- 카메라는 `calibration/run_d435_rgb_stable.sh`로 재시작하고 RealSense
  노드는 한 개만 유지해야 한다.

### 멀티포즈 검증 완료

- 동일 marker ID 8을 정면, RX/RY/RZ 및 Base XYZ 변화 총 10자세에서
  검증했다. 모든 샘플은 1920x1080, markers 17/17, corners 24/24였다.
- 결과와 해석은 중복 기록을 피하기 위해
  `docs/logs/calibration.md`의 2026-08-12 멀티포즈 항목에 정리했다.
