# D435 그리퍼 카메라 다품종 접근/파지

이 기능은 ChArUco를 사용하지 않는다. GPU, HBM, VRM, Power Module, Inductor,
SMD Capacitor의 크기 프로파일과 RGB-D 형상을 사용해 **영상 중앙의 부품 한 개**를
선택한다. 팀원의 D435 노드가 이미 실행 중이면 카메라 노드를 다시 실행하지 않는다.

> 현재처럼 기본 대기 위치에서 트레이 전체가 보이는 화면으로 비-SMD 부품에 접근할
> 때는 중앙 단일부품 검출기가 아니라
> `vision_assembly/run_tray_part_hover_5cm.sh`를 사용한다. 이 통합 실행기는 현재
> 트레이 검출 결과를 새로 5프레임 확인하고, 그리퍼 축을 맞춘 뒤 50 mm 상공에서
> 정지한다. 이 문서의 `calibration` 경로는 카메라를 한 부품 가까이 옮긴 이후의
> 기존 상세 검출/파지 구현으로 보존한다.

필요한 토픽은 다음과 같다.

```text
/camera/camera/color/image_raw/compressed
/camera/camera/color/camera_info
/camera/camera/aligned_depth_to_color/image_raw
/nonrt_state_data
```

## 지원 프로파일 확인

```bash
cd ~/KSMC
./calibration/run_pick_part_with_gripper_camera.sh --list-parts
```

프로파일 원본은 `calibration/config/gripper_part_profiles.json`이다. GPU의
57 x 27 x 6 mm만 사용자 실측값이고, 나머지 다품종 규격은 Unity/OBJ CAD 후보라
캘리퍼 검증이 필요하다.

## 권장 첫 시험: 로봇을 움직이지 않는 검출/dry-run

집으려는 부품 전체가 영상 안에 보이고 그 중심이 영상 중앙에 오도록 시작 자세를
잡는다. 중앙 근처에 같은 크기의 부품이 두 개 있으면 선택 모호성 때문에 검출을
중단한다.

```bash
./calibration/run_part_approach_5cm.sh --part-type hbm
```

이 명령은 D435와 로봇 상태를 읽고 목표와 예정 경로만 계산한다. 로봇과 그리퍼는
움직이지 않는다.

## 5 cm 비접촉 접근

```bash
./calibration/run_part_approach_5cm.sh \
  --part-type hbm \
  --allow-unvalidated-part-profile \
  --execute \
  --confirm-approach-only
```

기본 속도는 수평 20%, 수직 15%, 회전 20%다. 두 번의 제한된 RGB-D 재검출/보정과
최종 도착 검증 후 부품 윗면 50 mm에서 멈춘다. 그리퍼, 파지 하강, 리프트, 복귀
명령은 보내지 않는다. 현재 다품종 검출은 실물 미검증 상태라 실제 접근에도
`--allow-unvalidated-part-profile`이 필요하며, 이는 감독하에 5 cm 검증 이동을
의도적으로 연다는 뜻일 뿐 정확도를 보증하지 않는다.

부품 이름은 다음 별칭도 허용한다.

```text
gpu / nvidia
hbm / sk_hynix
vrm / black_block
power_module / long_orange
inductor / marked_white
smd_capacitor / smd / right_white_brown
```

## 부품별 검출과 자세

- GPU/HBM/VRM: 어두운 외형 후보를 찾은 뒤 실제 높이와 주변 지지면 깊이를 검증한다.
- Power Module: 주황 HSV 후보를 찾은 뒤 같은 깊이 검증을 한다.
- Inductor: 경사 지지면에서 돌출된 깊이 형상을 직접 찾는다. 원형이므로 불안정한
  장축 각도를 만들지 않고 현재 TCP 자세를 유지한다.
- SMD Capacitor: 밝은 외형 후보와 깊이를 함께 사용하고 장축에 그리퍼 축을 맞춘다.

모든 프로파일은 윤곽 내부 깊이, 주변 지지 평면, 실제 돌출 높이, 프레임 간 Base
좌표 흔들림을 통과해야 target JSON을 갱신한다.

## 실제 접촉 파지 상태

다품종 전체 파지 경로는 구현되어 있지만 아직 부품별 실물 검증 전이라 기본 차단돼
있다. 다음 값이 부품마다 실측되어야 한다.

- 실제 길이/폭/높이
- 그리퍼가 안전하게 물 수 있는 폭, 힘, `--gripper-close-position`
- 부품 윗면 기준 TCP의 `--grasp-z-offset-mm`
- 현재 장착 상태의 Hand-Eye 정확도
- 핑거와 트레이 칸막이 사이 충돌 여유

검증을 완료한 작업자가 의도적으로 시험할 때만 다음 형태의 명령이 열린다.

```bash
./calibration/run_pick_part_with_gripper_camera.sh \
  --part-type hbm \
  --gripper-close-position <실측값> \
  --grasp-z-offset-mm <실측값> \
  --allow-unvalidated-part-profile \
  --allow-provisional-calibration \
  --execute \
  --confirm-full-cycle
```

`--allow-*`는 정확도나 안전을 보증하지 않는다. 활성 Hand-Eye 파일의 경고가 제거될
정도로 독립 검증한 뒤에는 `--allow-provisional-calibration`을 쓰지 않는다. 현재
전체 파지는 잡기, 50 mm 상승, 같은 위치에 다시 놓기, 후퇴까지만 수행하며 다른
PCB 슬롯으로 운반하지 않는다.

## 프로파일 보정

캘리퍼로 확인한 크기는 다음처럼 일회성으로 덮어쓸 수 있다.

```bash
./calibration/run_part_approach_5cm.sh \
  --part-type vrm \
  --part-length-mm 14.0 \
  --part-width-mm 11.0 \
  --part-height-mm 5.2
```

실측값이 확정되면 일회성 옵션보다 프로파일 JSON의 규격과 상태를 갱신하고 회귀
테스트를 다시 실행한다.
