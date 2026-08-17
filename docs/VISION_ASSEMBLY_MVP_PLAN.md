# 반도체 패키지 모형 조립 Vision MVP 계획

## 일정 우선 결론

학습 데이터가 필요한 범용 AI segmentation은 MVP 이후로 미룬다. 먼저 고정된
공정 환경을 활용한 다음 조합으로 완성한다.

1. 기판: 기본은 CAD에 등록된 4개 이상의 체결 구멍/빨간 링 중심으로 board
   frame과 회전을 결정하며, ArUco는 개발용 fallback으로만 사용
2. 조립 위치: CAD 치수를 `board_layout.yaml`의 board-frame 좌표로 등록
3. 부품 트레이: 고대비 배경에서 OpenCV mask/contour로 부품 중심·각도 검출
4. 거리: aligned depth의 부품 mask 내부 중앙값으로 Camera XYZ 계산
5. 높이: 부품 recipe의 실제 출력 높이를 주값으로 사용하고 depth는 범위 검증
6. 로봇: Eye-in-Hand `T_base_flange @ T_flange_camera @ P_camera_part`
7. 파지: 안전 접근→근접 재검출→소폭 XY/Z 보정→하강→닫기→시험 상승
8. 배치: `T_base_board @ T_board_slot`으로 목표 생성→하강→열기→상승
9. 검사: 고정형 휴대폰 카메라의 원근 보정 영상에서 ROI별 존재·각도 판정

## 3D 출력 전에 반영할 사항

- 기판은 무광 재질로 출력하고 서로 멀리 떨어진 4개 이상의 체결 구멍/빨간 링
  중심을 vision datum으로 사용한다.
- 원형 기준점이 대칭이면 180° 방향이 모호하므로 한 링만 다른 색, 지름 또는
  작은 notch를 사용해 orientation key로 만든다.
- 검은 GPU/HBM을 검은 기판에서 직접 분할하지 않는다. Pick 트레이를 무광 흰색
  또는 밝은 회색으로 제작한다.
- GPU/HBM 상면에 작은 흰 점, 모서리 notch 또는 비대칭 표식을 넣어 180° 방향을
  구분한다. 렌더링의 HBM 흰 점은 유지하는 것이 좋다.
- 조립 자리에는 0.5~1 mm의 얕은 포켓 또는 외곽선을 넣으면 Place 성공률과
  육안 설명력이 높아진다.
- 작은 노란 수동소자는 기판에 붙은 상태로 일체 출력하며 로봇 조립 대상에서
  제외한다.
- 부품 종류별로 트레이 ROI 또는 색상/크기/종횡비가 확실히 구분되게 만든다.

## 확정 조립 대상 — 총 25개

| Recipe | 사진상 부품 | 수량 | 권장 검출 특징 |
|---|---|---:|---|
| `left_black_block` | 기판 왼쪽 검정 사각형 | 5 | 밝은 트레이 위 검정 contour, 크기/종횡비 |
| `right_white_brown` | 우측 흰색+갈색 소형 부품 | 5 | Lab/HSV 색상, contour, 긴 축 방향 |
| `right_white_black` | 우측 하단 흰색+검정 표시 부품 | 2 | 흰 몸체 contour + 검정 방향표시 |
| `long_orange` | 노랑/주황색 긴 직사각형 | 4 | HSV/Lab + minAreaRect |
| `gpu` | 중앙 GPU | 1 | 밝은 트레이 위 외곽 사각형 + 비대칭 표식 |
| `hbm` | GPU 양쪽 HBM | 8 | 밝은 트레이 위 검정 contour + 흰 점 방향 |

동일 recipe는 한 검출기와 한 파지 설정을 재사용하고, `board_layout.yaml`에
목표 슬롯 좌표만 수량만큼 등록한다. 따라서 구현 대상은 25개 개별 알고리즘이
아니라 검출 recipe 6개와 placement slot 25개다.

### 2026-08-12 전달 모델 점검

- `/home/hc/Downloads/Board_obj/ITEAM.prefab`과 OBJ를 해석한 결과 기판 외형은
  약 `140.00 × 110.34 mm`다.
- Unity X/Z 평면과 최상위 scale `0.01`을 반영해 기판 중심 기준 placement
  후보 좌표를 추출했다.
- 모델에는 GPU 1, HBM 8, 검정 블록 5, 긴 부품 4, 흰색+검정 2,
  흰색+갈색 4개로 총 24개만 독립 배치되어 있다.
- 사진과 공정 요구사항의 흰색+갈색 5개 중 1개가 Unity 조립 파일에서
  누락됐으므로 임의 좌표를 만들지 않는다. 수정 모델 또는 누락 부품의 정확한
  배치 좌표를 받은 뒤 25번째 slot을 추가한다.
- 추출 결과는 `vision_assembly/config/board_layout_from_unity.{json,csv,svg}`에
  있으며 실제 출력물 치수와 기판 기준점으로 검증하기 전에는 자동 이동에
  사용하지 않는다.
- `motherBoard.obj`의 각 placement 중심과 주변 표면 높이를 검사한 결과 개별
  부품 외곽을 따라 파인 포켓은 없다. GPU/HBM 중앙 영역은 외곽 기판보다 약
  `2 mm` 높은 넓은 단차이며, 사진에서 홈처럼 보이는 부분은 주로 재질/배선
  표현이다. 위치 유도 홈이 필요하면 출력 전 CAD에서 별도로 추가해야 한다.

## OpenCV 검출 파이프라인

```text
RGB image
  -> board/tray ROI
  -> HSV 또는 Lab threshold / 배경 차분
  -> morphology open + close
  -> contours
  -> 크기·종횡비·면적 필터
  -> minAreaRect: center (u,v), yaw, width, height
  -> mask erosion
  -> aligned depth median in inner mask
  -> Camera XYZ
```

검은 부품은 HSV 색상값보다 밝은 트레이와의 명암 차이를 사용한다. 여러 부품이
같은 색이면 실제 치수와 종횡비로 분류한다.

## ArUco 없는 기판 위치 인식

1. 빨간 링을 HSV/Lab으로 분할한다.
2. contour를 타원으로 fitting하여 각 링 중심 픽셀을 구한다.
3. 검출된 중심 패턴을 CAD의 hole 좌표와 매칭한다.
4. 고정형 상부 카메라는 `findHomography(..., RANSAC)`로 board plane을 정규화한다.
5. D435에서 3D board pose가 필요하면 CAD hole `(X,Y,0)`와 픽셀을
   `solvePnPRansac()`에 넣는다.
6. 모든 조립 목표는 `T_base_board @ T_board_slot`으로 계산한다.

최소 3개의 비공선 점으로 평면 X/Y/yaw를 정할 수 있지만, 일부 가림과 오검출에
대비해 4개 이상을 사용한다. 구멍 내부 depth는 기판 아래 바닥을 측정하므로 board
Z로 사용하지 않고, 구멍은 RGB 위치·회전 기준으로만 사용한다.

### 링/구멍 설계를 수정할 수 없는 경우

- 먼저 전체 구멍 중심 패턴을 CAD와 RANSAC 매칭한다. 패턴이 비대칭이면 이
  단계에서 방향까지 결정된다.
- 구멍 패턴이 180° 대칭이면 0°/180° 후보를 각각 board 정규 영상으로 warp한
  뒤, 기판에 일체 출력되는 노란 소자 군집·배선·외곽 형상을 CAD 렌더 또는
  기준 이미지와 template/feature matching하여 방향을 선택한다.
- 컨베이어가 기판을 항상 같은 방향으로 공급한다면 이전 frame과 이동 방향을
  orientation prior로 추가한다.
- 두 방향의 점수가 비슷하면 추측하지 않고 `BOARD_ORIENTATION_AMBIGUOUS`로
  공정을 정지한다.
- 구멍과 기판 일체 형상까지 완전 대칭이면 영상 정보만으로 0°와 180°를 구분할
  수 없으므로 공급 방향 고정 또는 기판 외부 carrier 기준점이 필요하다.

## 부품 Recipe 예시

```yaml
gpu:
  size_mm: [60, 60]
  height_mm: 10
  grasp_width_mm: 55
  approach_mm: 100
  pick_roi: gpu_tray
  target_slot: gpu_center

hbm:
  size_mm: [25, 35]
  height_mm: 8
  grasp_width_mm: 22
  approach_mm: 80
  orientation_mark: white_dot
```

## 단계별 완료 기준

### MVP-1

- 고대비 트레이의 단일 부품 중심과 yaw를 OpenCV로 검출
- mask 내부 depth 유효률과 Camera/Base XYZ 출력
- dry-run과 안전 접근

### MVP-2

- 한 종류의 부품 자동 Pick
- Fiducial 기반 board slot 한 곳에 자동 Place
- 파지/배치 결과 로그

### MVP-3

- 6개 recipe, 총 25개 부품 순차 조립
- 스마트폰 고정 카메라 ROI 검사
- 누락, 위치, 방향 PASS/FAIL

### 후순위

- 색상과 배경이 계속 바뀌거나 겹친 부품이 필요할 때만 YOLO instance
  segmentation을 추가한다.

## 권장 조립 순서

1. 중앙 GPU
2. GPU 양쪽 HBM 8개
3. 왼쪽 검정 블록 5개
4. 우측 흰색+갈색 5개
5. 우측 하단 흰색+검정 표시 2개
6. 가장자리의 긴 노랑/주황 부품 4개

긴 가장자리 부품은 먼저 놓으면 내부 부품 접근과 카메라 시야를 방해할 수 있어
마지막에 배치한다. GPU/HBM 순서는 실제 출력물의 높이와 핑거 충돌 여유를 CAD
또는 저속 dry-run으로 확인한 뒤 필요하면 서로 바꾼다.
