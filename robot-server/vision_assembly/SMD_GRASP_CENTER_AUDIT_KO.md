# SMD 검출 중심과 실제 그리퍼 중심의 보정 진단

작업 기준은 FR5_robot_control이다. 별도 FR5_precision_assembly 폴더는 사용자 요청으로 삭제했다. 카메라 최대 해상도 실행 설정만 calibration/run_d435_high_quality.sh와 vision_assembly/config/camera_high_quality.json으로 옮겼다.

## 추가된 기능

capture_smd_close_target.py의 SMD 결과와 full_cycle_plan.py의 SMD 계획에 grasp_center_diagnostic을 추가했다. 기존 검출 좌표, 목표 좌표, 보정값, 로봇 이동 명령은 바꾸지 않는다.

- 검출 중심 Base XY
- 고정 Base 보정 X=-2.089/Y=+2.779mm
- 보정 후 예상 TCP XY
- 계획 좌표와 계산 좌표의 차이
- 실제 중심 잔차는 실측 전 null, physical_alignment_verified=false

기준 기록 [-626.338,-164.944]에 보정값을 더하면 [-628.427,-162.165]로 저장된 성공 파지 좌표와 일치한다. 이는 설정의 산술 일치이며 새로운 독립 정확도 측정이 아니다. 이미지 가운데 픽셀을 그리퍼 가운데로 가정하지 않는다.

## 실행

```bash
python3 vision_assembly/scripts/smd_grasp_center_audit.py \
  --output vision_assembly/data/smd_center_audit_new.json
```

파일 덮어쓰기는 거부한다. ROS 서비스, 로봇 이동, 그리퍼 명령 또는 recipe 수정은 하지 않는다.

## 실제 잔차 측정 입력

config/smd_alignment_observations.template.json을 별도 파일로 복사하여 calibration_id, view_id, tool_id와 실제 측정 sample을 채운다. samples가 빈 상태이면 실측 비교를 거부한다.

각 sample에는 다음이 필요하다.

- sample_id: 중복되지 않는 측정 식별자
- detected_part_base_xy_mm: 그 측정에서 검출한 부품 중심
- aligned_tcp_base_xy_mm: 같은 부품의 중심에 실제 정렬된 TCP XY
- aligned_tcp_abc_deg: 정렬 당시 TCP 자세
- alignment_confirmed: 실제 중심 정렬을 확인했을 때만 true

단순히 현재 로봇 위치를 정렬 완료 위치로 기록하면 안 된다. 서로 다른 교정·카메라 view·툴을 한 묶음으로 비교하지 않는다. 실제 측정 좌표와 새로운 보정값의 적용은 별도 검토한다.

```bash
python3 vision_assembly/scripts/smd_grasp_center_audit.py \
  --observations path/to/measured_alignment.json \
  --output vision_assembly/data/smd_center_measured_audit.json
```

remaining_correction_base_xy_mm는 `실제 정렬 TCP - 현재 보정으로 계산한 TCP`다. +X값은 추가로 Base +X 이동이 필요했다는 뜻이다. 결과는 관측 잔차이며 새 recipe로 자동 반영하지 않는다.

## 검증

중복 보정, 잔차 부호, 단위/좌표계 불일치, 교정/뷰/툴 혼합, 중복 측정, 미확인/빈/NaN 입력과 원본 불변성을 시험했다. 실행 계획 통합 검증에서는 기존 SMD 목표 좌표와 같은지 확인했다.

관련 테스트29개 통과. 함께 실행한 기존 test_safe_part_pick_recipe.py의 VRM·Inductor 테스트2개는 surface-relative Z offset을 기대하지만 현재 recipe는 fixed_fixture_absolute여서 실패했다. 이번 변경으로 해당 recipe나 loader는 수정하지 않았다. 이 두 항목은 별도 정리가 필요하다.
