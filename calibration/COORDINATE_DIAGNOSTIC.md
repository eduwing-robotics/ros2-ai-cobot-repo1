# FR5 Eye-in-Hand 좌표계 진단

## 실제 좌표변환 체인

현재 ChArUco 런타임 계산은 다음 정의를 사용한다.

```text
T_base_flange   : FR5 Base에서 Flange로의 변환
T_flange_camera: Flange에서 D435 color optical frame으로의 변환
T_camera_board : D435 color optical frame에서 ChArUco board로의 변환

T_base_board = T_base_flange @ T_flange_camera @ T_camera_board
```

OpenCV `estimatePoseCharucoBoard()`의 `rvec/tvec`은 보드 물체 좌표를 카메라
좌표로 바꾸므로 프로젝트 표기상 `T_camera_board`다. 기존 샘플 JSON의
`target_to_camera`는 같은 내용을 담지만 이름이 모호하므로 새 진단 로그에서는
사용하지 않는다.

FR5 `/nonrt_state_data` 중 Hand-Eye 계산과 런타임 변환에는
`flange_*_cur_pos`를 사용한다. 실제 `MoveCart` 목표와 현재 TCP 확인에는
`cart_*_cur_pos`와 활성 `tool_num=1`을 사용한다. 따라서 `toolcoord1`의 TCP와
`T_flange_camera`는 서로 다른 값이며 TCP Z를 Hand-Eye 행렬에 더하지 않는다.

## 확인된 상태와 문제 후보

- 적용 중인 결과는 40개 샘플의 Euler `xyz`, OpenCV DANIILIDIS 결과다.
- 현재 변환 행렬의 방향 또는 inverse 중복은 발견되지 않았다.
- 카메라 pose는 RGB `CameraInfo`의 K/D를 실시간으로 사용한다.
- 기존 코드는 영상 실제 크기와 `CameraInfo.width/height`의 일치를 명시적으로
  검사하지 않았다. 멀티포즈 진단 노드는 불일치 시 샘플 저장을 중단한다.
- 기존 접근점은 보드 법선 방향으로 100 mm를 더했다. 수평 조립대 안전 접근은
  이제 기본적으로 Robot Base +Z 방향을 사용하며, 기존 동작은
  `--approach-frame board_normal`로 선택할 수 있다.
- 같은 고정점을 다른 자세에서 계산했을 때 약 3 mm 변화가 확인됐으므로
  Hand-Eye 회전 오차, ChArUco 자세 추정 오차, intrinsic 조건을 CSV로 함께
  진단한다. 현재 Hand-Eye 결과가 잘못됐다고 사전에 단정하지 않는다.

## 멀티포즈 검증 방법

보드를 완전히 고정하고 같은 마커 ID를 모든 자세에서 사용한다. 한 자세마다
다음 명령을 한 번 실행하면 안정 프레임 20개를 묶어 CSV 한 줄을 추가한다.

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_handeye_multipose_validation.sh \
  --marker-id 8 \
  --frames 20
```

이 노드는 로봇 이동 서비스 자체를 사용하지 않는다. 매번 출력되는 Base XYZ,
표준편차, 개별 3D 오차, 최대 오차, RMS 및 카메라 회전과 오차의 상관관계를
확인한다.

기본 CSV:

```text
/home/juchan-yoon/FR5_robot_control/calibration/data/handeye_multipose_validation.csv
```

다른 마커나 다른 Hand-Eye 결과는 같은 CSV에 섞지 못하도록 차단한다. 새 실험은
파일명을 명시한다.

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_handeye_multipose_validation.sh \
  --marker-id 11 \
  --frames 20 \
  --csv /home/juchan-yoon/FR5_robot_control/calibration/data/handeye_multipose_marker11.csv
```

## Base +Z 100 mm Dry-run

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_marker_target_dry_run.sh \
  --marker-id 8 \
  --approach-offset-mm 100 \
  --approach-frame base_z \
  --frames 20 \
  --dry-run
```

`base_z`에서는 target Base X/Y를 그대로 유지하고 Z에만 `+100 mm`를 적용한다.
검증 데이터가 충분히 모이기 전에는 `--execute --confirm-move`를 사용하지 않는다.

## 평면 PnP 비교

기본 `charuco` pose에서 특정 기울기 방향만 오차가 커지면 같은 코너에 평면
보드용 IPPE를 적용해 비교할 수 있다. 반드시 다른 CSV를 사용한다.

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_handeye_multipose_validation.sh \
  --marker-id 8 \
  --frames 20 \
  --pnp-method ippe \
  --csv /home/juchan-yoon/FR5_robot_control/calibration/data/handeye_ry_repeatability_ippe.csv
```

이 비교도 로봇을 움직이지 않는다. IPPE 결과가 독립된 여러 자세에서 기본
방식보다 일관될 때만 런타임 pose 방식 변경을 검토한다.
