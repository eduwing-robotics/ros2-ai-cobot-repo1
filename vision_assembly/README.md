# Vision Assembly

반도체 패키지 모형의 CAD/Unity 배치, 부품 recipe, 기판 인식 및 FR5 조립
기능을 단계적으로 모으는 디렉터리다.

## 현재 산출물

- `tools/extract_unity_board_layout.py`: Unity prefab과 OBJ에서 기판 중심 기준
  부품 중심·방향·크기 후보를 추출한다.
- `tools/import_unity_pick_coordinates.py`: Unity의 최신
  `Assets/RobotArm/PcbPickCoordinates.csv`를 읽고 139×110mm 실물 기판 중심
  좌표로 변환한다. 현재 좌표를 다시 생성할 때는 이 도구를 우선 사용한다.
- `config/board_layout_from_unity.json`: 전체 메타데이터와 안전 경고 포함.
- `config/board_layout_from_unity.csv`: 슬롯 좌표 검토용 표.
- `config/board_layout_from_unity.svg`: 평면 배치 검토 및 발표용 그림.
- `config/fixture_layout.json`: 전체 Unity 프로젝트 없이 로봇이 사용할 지그의
  기판 정렬, 4핀 위치, 손잡이 방향 및 검증 조건.
- `config/inspection_fusion_contract.json`: 팀원의 D435 학습 모델에 의존하지 않는
  S22 하이브리드 AOI 조합, 모델 교체 인터페이스와 fail-safe 최종 판정 규칙.

## S22 현재 화면 촬영 후 전체 25슬롯 검사

S22에 현재 보이는 기판을 새 3.5배 망원 사진으로 촬영하고, 보드 ROI를 만든 뒤
GPU 1, HBM 8, Power Module 4, VRM 5, Inductor 2, SMD Capacitor 5를 한 번에
검사한다.

```bash
~/KSMC/run_s22_live_hybrid_inspection.sh
```

기본 실행은 플래시를 끄고 새 사진인지 확인한 후 YOLO 보조 검출, 고정 슬롯
상태·방향 검사, 부품별 PatchCore를 모두 실행한다. 이전 ROI를 재사용하려면
진단 목적으로만 `--skip-capture`를 붙인다. 최신 결과는 다음 위치에 저장된다.

위치 계산의 기본 설정은 `config/s22_fixed_reference_pose_candidate.json`이다.
노란 CAD 좌표와 확인된 정상 사진의 고정 중심 보정을 사용하며, 검사 중인
부품들의 공통 중심 편차는 진단용으로만 남긴다. 학습 모델 입력 crop과
위치·각도 허용 오차는 유지한다. 기준 자료·CAD·검출 가중치의 해시가 맞지
않으면 해당 위치 검사를 `UNKNOWN`으로 보류한다. 이 기준은 개발용 보조
판정이며, 모든 소켓의 실제 안착이나 높이 검증을 대신하지 않는다.
검증 범위와 남은 문제는
[고정 위치 기준 수정 기록](../docs/logs/vision.md#2026-09-10-frozen-raw-position-reference-repair)를 참고한다.
기존 `full_board_inspection.json`을 명시적으로 지정하면 이전 위치 보정 방식이
실행되므로 두 설정의 결과를 같은 기준으로 비교하지 않는다.

```text
runtime/inspection/hybrid_fixed_slot/hybrid_report_latest.png
runtime/inspection/hybrid_fixed_slot/hybrid_report_latest.json
```

미검증 provider는 `ADVISORY_ONLY`이므로 색이 표시돼도 확정 불량이 아니며,
모든 필수 검사가 검증되기 전 최종 결과는 fail-safe `UNKNOWN`이다. 이 실행기는
S22 촬영과 검사만 수행하고 로봇·컨베이어 이동 명령은 보내지 않는다.
촬영 품질 경고, 내부 신호 및 실행 불가 검사 표시는
[진단 안내](../docs/INSPECTION_QUALITY_AND_DIAGNOSTICS.md)를 참고한다.
주요 기능의 장비 구동 없는 병렬 회귀 점검은
[소프트웨어 검증 안내](../docs/SOFTWARE_REGRESSION_CHECKS.md)를 참고한다.

### 검사 결과를 DB 담당자에게 전달

현재 계약은 Sequencer가 Vision에 요청한 뒤 **JSON과
`02_annotated_report.png`를 각각 조회**하는 방식이다. Sequencer를 거쳐
MainServer가 보관하며 Vision은 DB 쓰기나 MainServer 직접 업로드를 하지 않는다.
주소·인증·ID·조회 순서는 [최신 전달 계약](../team_handoff/vision_sequencer_api/README.md)을
따른다. 예전 수동 ZIP 내보내기는 운영 연동 방식이 아니다.
현재 후보는 `ADVISORY_ONLY`이므로 전송 과정에서도 확정 불량으로 승격하지 않는다.

### 비VRM 20슬롯 존재 데이터 수집

GPU/HBM/Power Module/Inductor/SMD가 모두 들어 있는 장면은 다음처럼 명시한다.

```bash
~/KSMC/vision_assembly/run_capture_component_presence.sh --all-present
```

빠진 부품이 있으면 정확한 슬롯 ID를 모두 지정한다.

```bash
~/KSMC/vision_assembly/run_capture_component_presence.sh \
  --empty hbm_01 power_module_04 inductor_02 smd_capacitor_05
```

명령은 플래시 OFF 새 사진을 촬영하고 VRM을 제외한 20개 고정 슬롯 crop과
manifest를 저장한다. 방향이나 외관이 잘못돼도 몸체가 슬롯에 있으면
`PRESENT`이며, 실제로 비어 있는 슬롯만 `--empty`에 넣는다.

## 다시 생성

```bash
python3 ~/KSMC/vision_assembly/tools/import_unity_pick_coordinates.py \
  --unity-csv "/home/hc/My project/Assets/RobotArm/PcbPickCoordinates.csv"
```

현재 Unity export에는 GPU 1, HBM 8, Power Module 4, VRM 5, Inductor 2,
SMD Capacitor 5로 총 25개가 포함되어 있다. 이전 24개 export에서 빠졌던
`SMD Capacitor 05`도 포함됐다.

이 레이아웃은 CAD-derived candidate다. 실제 출력물 크기, 기판 frame 방향,
부품 높이를 검증하기 전에는 FR5 실행 좌표로 사용하지 않는다. 배치 Z는 OBJ
bounds만 믿지 않고 검출된 기판 평면, aligned depth, 실측 recipe 높이로 만든다.

지그를 사용하는 경우 `fixture_layout.json`을 함께 확인한다. 지그는 기판
좌표계의 원점과 방향을 정하는 기준이며, 지그 좌표를 로봇 Base 좌표로 직접
사용하지 않는다. 실제 지그에 기판을 안착한 뒤 S22 또는 D435로 기판 pose를
검출하고, 그 pose에 board-relative 부품 좌표를 적용한다.

## S22 고정형 기판 Base 좌표

S22 영상의 기판 중심을 FR5 Base XY로 변환하는 평면 Homography 캘리브레이션과
실행 방법은 [S22_BOARD_LOCALIZATION.md](S22_BOARD_LOCALIZATION.md)에 정리했다.
기존 컨베이어 검출 외곽을 재사용하므로 동일 영상을 별도 노드에서 다시 디코딩하지
않는다. 현재는 좌표 발행 전용이며 로봇 이동 명령은 포함하지 않는다.

## 조립 위치 빈 기판의 25개 슬롯 좌표 캡처

S22 HQ 카메라와 컨베이어 기판 검출 노드가 실행 중이고 빈 기판이 조립 위치에
정지해 있을 때 다음을 실행한다. 이 도구는 영상과 기판 외곽만 읽으며 로봇과
컨베이어에 이동 명령을 보내지 않는다.

```bash
~/KSMC/vision_assembly/run_capture_assembly_slot_coordinates.sh
```

출력:

```text
vision_assembly/data/assembly_slot_coordinates.json
vision_assembly/data/assembly_slot_coordinates.csv
vision_assembly/data/assembly_slot_coordinates_overlay.png
runtime/assembly_coordinates/assembly_slot_coordinates_latest.*
```

Unity 좌표는 CAD 후보로만 사용하고, `physical_board.json`에 등록한 실제
Inductor/SMD 홈을 우선한다. 번호는 S1 가로, S2~S5 오른쪽 세로열 아래→위,
I1~I2 오른쪽 아래 원형 홈 위→아래다. S22 평면 캘리브레이션이 통과하기 전에는
board-mm와 image-pixel만 유효하며 FR5 Base XYZ로 사용하지 않는다. 자동 하강 전
각 슬롯을 TCP 상공에서 별도로 확인한다.
# Vision Assembly

## 빈 기판 좌표 dry-run

실물 기판 외곽 크기 `139 x 110 mm`를 사용해 D435 RGB 영상에서 기판 외곽을
검출하고, Hand-Eye 결과로 FR5 Base 좌표까지 계산한다. 이 명령은 로봇을
움직이지 않는다.

```bash
~/KSMC/vision_assembly/run_board_pose_dry_run.sh --frames 20
```

결과 파일:

- `data/board_pose_last.json`: Camera/Base 기판 중심과 변환 행렬
- `data/board_pose_debug.jpg`: 검출된 기판 외곽과 중심 표시

현재 외곽 사각형만으로는 180도 방향 모호성이 있으므로, 자동 부품 배치에는
금색 패드의 비대칭 배치 또는 기준 구멍 방향 판별을 추가한 뒤 사용한다.

## 실시간 기판 중심 화면

```bash
~/KSMC/vision_assembly/run_board_view.sh
```

rqt Image View에서 다음 토픽을 선택한다.

```text
/vision/board/image/compressed
```

표시 내용:

- 빈 기판 외곽: 초록색
- 기판 중심: 빨간 십자
- 기판 +X 축: 파란 화살표
- 기판 +Y 축: 노란 화살표
- 영상 기준 회전: `YAW(image)`
- 현재 기준 방향: `DIRECTION: canonical`
- FR5 Base 중심 좌표: `BASE XYZ mm`
- 함께 보이는 완성 기판: `ASSEMBLED/OTHER`로 제외

기준 방향은 큰 금색 패드 군집이 빈 기판의 오른쪽 위에 보이는 방향이다.
이 노드는 영상과 로봇 상태를 읽기만 하며 로봇 이동 명령을 보내지 않는다.

조립 허용 정책은 `canonical=READY`, `rotated_180_corrected=READY`,
`unknown=CHECK`이다. 평면상 180도 회전은 금색 패드 4분면 분포로 판별해 기판
+X/+Y를 canonical 방향으로 자동 보정한다. 앞뒤가 뒤집힌 기판은 보정 대상이
아니라 반송 또는 작업자 수정 대상으로 처리한다.

어두운 사각형 오검출을 줄이기 위해 외곽 비율뿐 아니라 외곽 직사각형 충실도와
네 모서리의 원형 체결 구멍을 함께 검사한다. 화면의 `holes`, `rect`, `dirErr`는
이 진단값이다.

기본 화면은 실물에서 측정한 `right_white_brown` 슬롯을 `P1~P5`로 표시한다.
첫 시험 대상 `P1`은 자주색 큰 십자, 나머지는 청록색 작은 십자로 표시한다.
다른 레시피나 슬롯은 다음처럼 선택한다.

```bash
~/KSMC/vision_assembly/run_board_view.sh \
  --show-recipe right_white_brown \
  --target-slot right_white_brown_01
```

최신 Unity 모델에는 SMD Capacitor 5개가 모두 있지만, 기존 D435 실물 측정값은
`physical_board.json`의 override로 별도 유지한다. Unity 재계산 결과로 자동
덮어쓰지 않으며, 정밀 자동 배치 전 각 슬롯의 TCP 상공 검증을 진행한다.

## D435 부품 트레이 등록·부품 검출 화면

### 원격 D435 전송 최적화

D435가 팀원 컴퓨터에 연결되고 YOLO가 다른 노트북에서 실행될 때는 원본
`image_raw/compressed`를 여러 노드가 직접 구독하지 않는다. 카메라가 물리적으로
연결된 컴퓨터에서 기존 RealSense 노드를 모두 종료한 뒤 다음 통합 실행기를 사용한다.

```bash
~/KSMC/vision_assembly/run_d435_optimized_camera_host.sh
```

이 명령 하나가 `1920×1080×15 RGB + aligned depth`와 원격 중계 노드를 함께
실행하며, `Ctrl+C` 시 두 프로세스를 모두 종료한다. 이미 팀원이 별도로 D435를
실행 중이고 종료할 수 없을 때만 다음 중계 노드만 추가 실행한다.

```bash
~/KSMC/vision_assembly/run_d435_ai_stream_camera_host.sh
```

이 노드는 로컬 raw RGB에서 최신 프레임만 15 FPS로 선택하고 JPEG 품질 92로 한 번만
압축해 다음 토픽으로 보낸다. 입력·출력 QoS 큐는 1장이므로 느린 구형 프레임이
쌓이지 않는다. 이 토픽은 원격 확인과 원격 AI의 예비 입력이며,
정밀 검사는 D435가 연결된 컴퓨터에서 raw RGB와 aligned depth를 직접 사용한다.

```text
/camera/camera/color/image_ai/compressed
```

AI 노트북의 통합 OBB는 위 토픽만 구독한다. AI 노트북에서는 원본 D435 토픽과
기존 `tray_part_detector`, `tray_section_viewer`를 동시에 실행하지 않는다. 화면은
`/vision/parts_obb/image/compressed` 하나만 본다. 팀원 카메라 PC에서 원본 화면이
필요하면 네트워크 compressed 토픽 대신 로컬 `image_raw`를 선택한다.

팀원 브랜치의 트레이 화면은 고정 reference image와 SIFT/RANSAC homography로
현재 카메라 화면을 등록한다. 카메라가 조금 이동하거나 트레이가 영상 안에서
위치가 바뀌어도 등록된 영역을 따라간다. 이 방식이 프로젝트의 **기본 트레이
방식**이며, 사용자 검토·조정한 6개 부품 영역은 `config/tray_layout.json`에 있다.

화면 실행:

```bash
~/KSMC/vision_assembly/run_tray_sections_view.sh
```

출력 토픽:

```text
/vision/tray/sections_image/compressed
```

부품 검출은 별도 dry-run으로 실행한다. 이 노드는 FR5 이동 명령을 보내지 않고,
aligned depth·Hand-Eye·로봇 flange 상태를 이용해 검출 결과와 Base 좌표를
계산한다.

```bash
~/KSMC/vision_assembly/run_tray_part_detection.sh
```

트레이를 볼 때마다 로봇이 저장한 동일한 `TrayView`/대기 자세로 복귀한다면,
흰 트레이의 SIFT 등록 흔들림을 피하기 위해 고정 시점 모드를 사용할 수 있다.
이 모드는 해당 자세에서만 사용한다.

```bash
~/KSMC/vision_assembly/run_tray_part_detection.sh \
  --registration-mode fixed_view
```

출력 토픽과 결과 파일:

```text
/vision/tray/detections_image/compressed
~/KSMC/vision_assembly/data/tray_detections_last.json
```

## 트레이 비-SMD 부품 50 mm 위 접근

현재 기본 트레이 대기 화면에서는 다음 통합 실행기를 사용한다. 이미 실행 중인
D435와 `tray_part_detector`의 aligned Depth/Base 좌표를 사용하며, 카메라 노드를
다시 실행하지 않는다. GPU, HBM, VRM, Power Module, Inductor를 지원하고 SMD는
기존 전용 경로로 분리한다.

먼저 로봇 미작동 dry-run을 실행한다.

```bash
~/KSMC/vision_assembly/run_tray_part_hover_5cm.sh \
  --part-type gpu --instance 1 --dry-run
```

최신 5개 상태의 좌표/각도 안정성과 출력 경로를 확인한 뒤 실제 50 mm 상공 이동만
명시적으로 연다.

```bash
~/KSMC/vision_assembly/run_tray_part_hover_5cm.sh \
  --part-type vrm --instance 1 \
  --execute --confirm-hover-only
```

기본 속도는 수평 20%, 수직 15%, 회전 20%다. 직사각형 부품은 그리퍼 `tool_y`를
장축에 맞추고, 원형/정사각형 Inductor는 현재 TCP 각도를 유지한다. 접촉 하강과
그리퍼 명령은 이 실행 경로에 존재하지 않는다. 좌표는 생성 후 15초가 지나면
거부되며, 접근 높이는 정확히 50 mm로 고정된다.

GPU #1 호환 단축 실행기도 같은 새 경로를 호출한다.

```bash
~/KSMC/vision_assembly/run_gpu1_center_hover.sh \
  --execute --confirm-hover-only
```

실측 결과, 안전 차단 조건 및 지원 별칭은 `TRAY_HOVER_5CM.md`를 따른다.

## GPU YOLO-OBB 데이터 준비

GPU의 정확한 회전 외곽은 색상 contour 대신 YOLO-OBB로 전환한다. 현재 단계는
데이터 수집·라벨링이며 로봇 이동 명령을 보내지 않는다.

```bash
~/KSMC/vision_assembly/run_capture_gpu_obb_images.sh --count 1
~/KSMC/vision_assembly/run_label_gpu_obb.sh
```

GPU 두 개의 위치와 각도를 바꿔가며 한 배치당 한 장을 촬영하고 각 GPU의 네 모서리를
라벨링한다. 같은 장면으로 이미 확보한 최초 10장에만 라벨러의 `P` 복사를 사용한다.
서로 다른 장면에서는 `S`로 장별 저장한다. 데이터 분할과 학습 방법은
`obb/README.md`에 정리되어 있다.

## SMD01 micro lip seating

SMD01 micro lip seating remains deferred/UNKNOWN. The September 10 gross-position
fallback was withdrawn after the user corrected the sample's physical condition.
An image-derived centre offset alone does not establish socket exit or height.
Existing independent position, missing and orientation checks remain in place.
Correction: [work record](../docs/logs/vision.md#2026-09-10-smd01-sample-truth-correction-and-fallback-withdrawal).
