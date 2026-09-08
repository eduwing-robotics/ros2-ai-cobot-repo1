# 조립 촬영·실행 순서 — 2026-09-05 사용자 지정

1. PlaceCamera에서 기판을 촬영하고 25개 배치 위치를 한 번 계산·저장한다.
2. TrayHome에서 트레이를 촬영한다. 일반 부품 20개의 파지 좌표를 계산한다.
3. GPU → HBM 8개 → PM 4개 → VRM 5개 → 인덕터 2개 순서로 조립한다.
4. 파지 후 100mm 증명 상승 → TrayHome에서 해당 셀의 부품 제거를 확인한다.
   그 다음 TrayHome에서 안전 높이로 상승하여 기판으로 직접 이동한다.
   원래 파지 위치 100mm로 복귀하거나 거기서 다시 상승하지 않는다.
5. 일반 부품 완료 후 SMDView에서 마지막 SMD 5개의 위치와 미세각도를 측정한다.
   최종 XYZ와 각도 모두 SMDView 결과를 사용하고 기존 중심 보정은 한 번만 적용한다.
6. 저장한 기판 좌표를 사용해 SMD를 파지·배치한다.

## 단일 실행 명령 — 2026-09-07

프로젝트 루트에서 `./run_fr5_cycle.sh --execute`로 위 촬영 자세 이동·계산·일반20개·SMD5개를 연결한다. 일반20개는 매번 TrayHome 파지확인을 포함하며 SMD는 기존 순서다. 사진과 단계별 기록을 새 실행 폴더에 남긴다. [준비 조건·점검·실패 처리](../docs/FR5_CYCLE_LAUNCHER_KO.md)를 참고한다. 아래는 기존 개별 단계 사용법과 당시 검증 기록이다.

## 기존 원본 폴더에서 사용하는 단계별 명령

각 capture 명령은 해당 카메라 자세에 도착하여 생성된 유효 검출을 저장한다.
아래 촬영/계획 명령 자체는 카메라 자세로 로봇을 이동시키지 않는다.

```bash
bash vision_assembly/run_fixed_cycle_snapshot.sh board
bash vision_assembly/run_fixed_cycle_snapshot.sh tray
bash vision_assembly/run_full_cycle_plan.sh --phase non-smd --output vision_assembly/data/non_smd_plan.json
bash vision_assembly/run_full_cycle_execute.sh --plan-file vision_assembly/data/non_smd_plan.json --dry-run
```

non-smd 단계 실행기는 TrayHome 확인 경로를 자동 포함한다. 새 트레이 촬영에서
reference_center_pixel을 저장해 셀 제거를 검사한다. 기준 픽셀이 없는 과거 자료로
실제 실행하지 않는다. GPU 단독 파지 확인·재개에 관한 기존 실행 조건은 유지한다.
20개 부품의 물리 동작이 끝난 다음 SMDView로 이동하고 기존 close capture를 실행한다.
그 결과가 유효할 때 다음 명령으로 마지막 단계를 만든다.

```bash
bash vision_assembly/run_fixed_cycle_snapshot.sh smd-close
bash vision_assembly/run_full_cycle_plan.sh --phase smd --output vision_assembly/data/smd_plan.json
bash vision_assembly/run_full_cycle_execute.sh --plan-file vision_assembly/data/smd_plan.json --dry-run
```

SMD close 파일의 기존 시간·프레임·신뢰도·인스턴스·보정 전 좌표 검사를 유지한다.
기판/트레이가 움직이거나 접촉·파지 실패가 있으면 저장된 좌표를 그대로 재사용하지 않는다.
단계 간 촬영 자세 이동과 물리 완료 확인은 기존 실행 절차로 수행하며,
이 변경이 처음부터 끝까지 무인 자동 실행하는 새 상위 제어기를 추가한 것은 아니다.
TrayHome 빈 셀 관측은 부품 제거 증거이며, 그 자체로 실제 보유/기판 안착 증명은 아니다.

## 검증 및 저장

- HBM/PM/인덕터 방향 수정 기록: data/FULL_CYCLE_DIRECTION_CHECK_20260905.md
- 새 일반 부품 단계: data/non_smd_sequence_check_20260905.json
- TrayHome 포함 검증: data/non_smd_inspection_preflight_20260905.json
- 저장된 2026-09-02 자료로 일반 부품 20개, 428개 경유점 IK 검증 통과.
  최대 관절 변화94.646도, J6 [-14.476,167.216]도. 기존 제한 유지.
- 관련 회귀 검사72개 통과. 실제 로봇/그리퍼 이동 명령 없음.
- 위 결과는 관절 경로 검사이며 형상 충돌 검사나 현장 조립 성공을 뜻하지 않는다.
