# D435 기본 트레이 화면 기반 비-SMD 5 cm 상공 접근

이 실행기는 ChArUco를 사용하지 않는다. 이미 실행 중인 D435 트레이 검출기의
RGB-D 안정화 결과를 받아 GPU, HBM, VRM, Power Module, Inductor 중 한 개의 실제
표면 좌표를 고정한 뒤 TCP를 **Base +Z 방향으로 정확히 50 mm 위**까지만 보낸다.

이 경로에는 접촉 하강, 그리퍼 열기/닫기, 파지, 리프트, 배치가 없다. 기존
`calibration/run_pick_part_with_gripper_camera.sh`의 파지 구현은 보존되어 있지만 이
실행기에서는 호출하지 않는다. SMD Capacitor는 기존 SMD 전용 경로를 사용하며 이
비-SMD 실행기에서는 차단된다.

## 현재 실행 중이어야 하는 것

카메라 노드를 새로 실행하지 않는다. 팀원이 D435와 `tray_part_detector`를 이미
실행 중이라면 그대로 둔다. 다음 세 토픽이 갱신되어야 한다.

```text
/vision/tray/unity_state
/vision/tray/registration
/nonrt_state_data
```

`unity_state`에는 aligned D435 Depth로 계산한 Camera XYZ와 Hand-Eye로 변환한 Base
XYZ가 들어 있다. `registration`의 `TRACKING`과 `at_trayhome=true`도 동시에
확인한다. D435 영상 토픽만 있고 위 트레이 토픽이 없다면 카메라를 하나 더 띄우는
것이 아니라, 현재 팀의 `tray_part_detector`만 실행해야 한다.

## 로봇 미작동 dry-run

```bash
cd ~/KSMC
./vision_assembly/run_tray_part_hover_5cm.sh \
  --part-type gpu \
  --instance 1 \
  --dry-run
```

이 명령은 최신 상태 5개를 모아 위치 흔들림 2.0 mm 이하와 장축 흔들림 3.0° 이하를
확인하고 경로만 출력한다. 로봇과 그리퍼에는 명령을 보내지 않는다.

지원 이름은 다음과 같다.

```text
gpu / nvidia
hbm / sk_hynix
vrm / black_block
power_module / long_orange
inductor / marked_white
```

`--instance`는 현재 보이는 각 종류의 1부터 시작하는 번호다. 부품을 꺼내면 번호가
다시 정렬되므로 매 접근 직전에 이 통합 실행기로 새 목표를 받아야 한다.

## 실제 50 mm 상공 이동만 허용

먼저 dry-run 출력과 작업 공간을 사람이 확인한 다음에만 다음 두 확인 옵션을 함께
준다.

```bash
./vision_assembly/run_tray_part_hover_5cm.sh \
  --part-type vrm \
  --instance 1 \
  --execute \
  --confirm-hover-only
```

기본 속도는 수평 20%, 수직 15%, 회전 20%다. 경로는 현재 위치에서 안전 Z로 수직
상승, 안전 Z에서 장축 정렬, 수평 이동, 부품 표면 50 mm 위로 수직 접근 순서다.
GPU/HBM/VRM/Power Module은 `tool_y`를 검출 장축에 맞춘다. Inductor는 원형/정사각
형상이라 파지 축이 유일하지 않으므로 현재 TCP 각도를 유지한다.

## 자동 차단 조건

- 트레이 등록이 `TRACKING`이 아니거나 대기 위치가 아닌 경우
- RGB-D/Base 상태가 3.5초보다 오래되거나 5개 연속 상태가 안정적이지 않은 경우
- 목표 파일 생성 후 15초가 지난 경우
- 표면 좌표가 측정된 트레이 작업공간 밖인 경우
- Tool 1이 아니거나 로봇이 이동 중/에러/충돌/비상 상태인 경우
- 각 waypoint의 XYZ 1.5 mm·회전행렬 자세 1.0° 도착 검증이 실패한 경우
- 실제 이동에서 `--execute --confirm-hover-only` 둘 중 하나라도 빠진 경우
- 50 mm가 아닌 접근 높이, 30%를 넘는 속도, SMD 요청

## 2026-09-04 현재 화면 검증

현재 기본 대기 화면에서 실시간 `unity_state`는 VRM 5, Power Module 4, Inductor 2,
GPU 1, HBM 8개를 검출했다. 각 종류 1번의 5프레임 dry-run 결과는 다음과 같다.

| 부품 | 표면 Base XYZ (mm) | 50 mm 상공 Z (mm) | 최대 위치 흔들림 |
|---|---:|---:|---:|
| GPU | `[-517.075, -188.968, -41.705]` | `8.295` | `0.498 mm` |
| VRM | `[-748.318, -221.332, -47.236]` | `2.764` | `0.008 mm` |
| Power Module | `[-731.061, -68.837, -45.358]` | `4.642` | `0.016 mm` |
| Inductor | `[-622.520, -227.111, -45.211]` | `4.789` | `0.019 mm` |
| HBM | `[-593.687, -49.682, -47.798]` | `2.202` | `0.010 mm` |

장축 부품의 5프레임 각도 흔들림은 모두 `0.000°`로 출력됐다. 이 검증에서는
`--execute`를 사용하지 않았으므로 실제 로봇·그리퍼·컨베이어 명령은 없었다.

현재 보이는 20개 비-SMD 기준점으로 reference pixel→Base XY를 적합한 최대 잔차는
1.893 mm였다. 빈 슬롯까지 포함한 전체 비-SMD ROI 투영 범위는 X
`-786.945~-457.330`, Y `-258.050~121.221 mm`였으며, 작업공간 게이트는 이 전체
범위에 안전 여유를 둔 X `-805~-440`, Y `-275~140 mm`를 사용한다.

실제 로봇 이동과 실제 50 mm 간격의 자/게이지 측정은 아직 수행하지 않았다. 최초
실행은 비상정지 가능한 감독 상태에서 한 종류씩 진행해야 한다.
