# KSMC 3-Camera Role Architecture

## 역할 확정

| 카메라 | 설치 | 주 역할 | 사용하지 않을 주 역할 |
|---|---|---|---|
| D435 | FR5 그리퍼 측면 Eye-in-Hand | Pick/Place 근접 정밀 보정, aligned depth 높이, 불확실 부위 재검사 | 전체 셀 감시, 단독 최종 전수검사 |
| Galaxy S22 | 조립 스테이션 수직 상부 고정 Eye-to-Hand | 기판 도착·정지, 기판/슬롯 Base XY·yaw, 조립 완료 전체 검사, PASS/FAIL | 단안 영상만으로 미지 높이 직접 측정 |
| GoPro HERO11 | 셀 상단 모서리 사선 | 전체 공정 녹화, 사각지대 보완, 사람/장애물 보조 감지 | 정밀 좌표, 정밀 불량 판정, 안전인증 기능 대체 |

## 권장 배치

### D435

- 현재처럼 그리퍼 브래킷에 강체 고정하고 Hand-Eye 결과를 유지한다.
- Pick 트레이와 조립 목표를 1차 관측한 뒤 안전 높이로 접근하고, 가까운
  inspection pose에서 다시 관측해 잔차를 보정한다.
- RGB와 aligned depth를 사용하되 실제 운용 거리에서 depth 유효률과 편차를
  recipe별로 검증한다.

### Galaxy S22

- 조립 중심 바로 위에 광축이 기판과 수직이 되도록 고정한다.
- 후면 기본 1x 카메라를 사용하고, 디지털 줌·초광각은 사용하지 않는다.
- 권장 시작 높이는 작업면에서 약 30~45 cm이며, 최종 기준은 기판과 컨베이어
  정지 ROI가 화면 안에 들어오면서 기판이 프레임의 60~75%를 차지하는 위치다.
- 무광 확산 조명을 좌우 대칭으로 배치하고 초점·노출·화이트밸런스를 가능하면
  고정한다.
- 컨베이어 영상에는 `pre-stop ROI`와 `assembly-stop ROI`를 둔다. 첫 ROI에서
  감속하고 두 번째 ROI에서 정지 명령을 보내 영상 지연에 의한 오버슈트를 줄인다.
- S22 intrinsic과 별도의 고정형 Eye-to-Hand extrinsic `T_base_camera_s22`를
  구하면 S22 검출점도 FR5 Base 좌표로 변환할 수 있다. D435의
  `T_flange_camera_d435`를 S22에 재사용하지 않는다.
- 평면 기판의 XY/yaw는 homography 또는 solvePnP로 계산하고, Z는 등록된 board
  plane/부품 recipe 또는 D435 aligned depth를 사용한다.

## S22와 D435 좌표 결합

```text
S22 fixed camera:
T_base_target_s22 = T_base_camera_s22 @ T_camera_s22_target

D435 eye-in-hand:
T_base_target_d435 = T_base_flange @ T_flange_camera_d435
                   @ T_camera_d435_target
```

두 결과를 같은 Base frame에서 비교한다. 단순 평균하지 않고 역할과 신뢰도를
나눈다.

- S22: board frame, slot XY/yaw, 컨베이어 위치의 전역 좌표
- D435: Pick 대상 3D 위치, aligned depth 높이, 근접 XY/Z 보정
- 두 결과 차이가 검증 임계값보다 크면 평균으로 숨기지 않고 이동을 정지한다.

D435는 TCP 자체를 영상으로 볼 필요가 없다. Hand-Eye와 FR5 TCP 설정이 Camera와
TCP의 관계를 제공한다. 다만 측면 장착 때문에 근접 시 목표가 FOV 밖으로 나가면
다음 순서를 사용한다.

1. S22가 기판/slot의 Base XY/yaw를 계속 제공한다.
2. D435가 목표가 보이는 마지막 검증 높이에서 위치와 depth를 갱신한다.
3. 두 Base 좌표가 허용 범위 안에서 일치하는지 검사한다.
4. 마지막 짧은 수직 하강은 갱신된 좌표와 board plane을 사용해 저속으로 수행한다.
5. 배치 후 로봇을 후퇴시키고 S22 전수검사 및 필요 시 D435 재검사를 수행한다.

S22의 최종 영상 좌표 정확도를 유지하려면 실제 스트림 해상도에서 intrinsic을
구하고, 후면 1x 렌즈·해상도·화면 방향·줌·손떨림 보정 설정을 고정해야 한다.
컨베이어와 로봇이 정지한 상태에서 좌표를 확정한다.

### GoPro HERO11

- 로봇 가동 범위 밖의 상단 모서리에 설치하고 35~50° 사선으로 로봇, 컨베이어,
  작업자 접근 영역 전체가 보이게 한다.
- 광각 왜곡은 calibration 후 보정하거나 Linear view를 사용한다.
- 사람 검출과 위험 구역 polygon 진입은 보조 정지 신호로만 사용하며, FR5
  비상정지와 물리 안전장치를 대체하지 않는다.

## 불량 유형별 담당

| 불량 | 1차 판정 | 2차 확인 | 방법 |
|---|---|---|---|
| 부품 누락 | S22 | D435 | board-warp ROI 점유율, contour/template |
| 위치 오류 | S22 | D435 | CAD slot 대비 중심 X/Y 오차(mm) |
| 방향 오류 | S22 | D435 | 긴 축 yaw, notch/점/문자 등 비대칭 특징 |
| 잘못된 부품 | S22 | D435 | 색상, 크기, 종횡비, template/class |
| 들뜸·높이 오류 | D435 | S22 사선 영상 | board plane 대비 aligned depth 높이 |
| 깨짐·변형·표면 손상 | S22 고해상도 | D435 근접/사선 | 기준 영상 차이, contour 결손, anomaly score |
| 내부 전기 불량 | 카메라 판정 불가 | 별도 검사 필요 | 전기적 검사 장비 영역 |

## 권장 공정 순서

1. S22가 기판의 pre-stop ROI 진입을 검출해 컨베이어를 감속한다.
2. 기판 기준 패턴이 stop ROI에 들어오면 컨베이어를 정지한다.
3. S22가 기판 frame과 X/Y/yaw를 계산한다.
4. D435가 트레이 부품 RGB-D pose를 계산하고 FR5가 Pick한다.
5. D435가 목표 슬롯을 근접 재관측하고 FR5가 Place한다.
6. GPU/HBM 등 핵심 부품은 D435로 즉시 간단 검증한다.
7. 모든 배치 후 FR5를 지정된 camera-clear 검사 자세로 이동한다.
8. S22가 기판 전체를 board frame으로 정규화해 25개 slot을 전수검사한다.
9. 불확실하거나 FAIL인 ROI만 D435가 가까이 재검사한다.
10. 최종 PASS/FAIL과 slot별 수치를 저장하고 다음 기판을 이송한다.

## 빠른 조립 운용 모드 — S22 좌표 확정 후 무재관측 Place

다음 공정도 가능하며 프로젝트 일정상 권장 MVP 방식이다.

1. FR5는 모든 부품이 D435에 보이는 트레이 관측 대기 자세에 위치한다.
2. S22가 기판 도착을 검출하고 컨베이어를 감속·정지한다.
3. 컨베이어 완전 정지 후 S22가 `T_base_board`와 각
   `T_base_slot = T_base_board @ T_board_slot`을 한 번 계산해 공정 동안
   snapshot으로 고정한다.
4. D435가 트레이 부품을 보고 FR5가 Pick한다.
5. FR5는 기판을 D435로 다시 보지 않고 저장된 Base slot 좌표의 안전 높이로
   이동한 뒤 저속 수직 하강해 Place한다.
6. FR5가 후퇴하면 S22가 배치 성공 여부를 확인한다.

이 방식의 명칭은 S22 고정 카메라 기준으로 `Eye-to-Hand`, D435 기준으로
`Eye-in-Hand`이며 전체 시스템은 hybrid multi-camera 구조다. `Hand-in-Eye`가
아니다.

무재관측 Place가 성립하려면 다음 조건을 모두 만족해야 한다.

- S22의 `T_base_camera_s22`와 기판 검출 오차가 placement 허용오차보다 작다.
- 기판과 컨베이어가 snapshot 이후 움직이지 않는다.
- CAD `T_board_slot`, FR5 TCP/toolcoord, 부품 recipe 높이가 실제 출력물과 맞다.
- D435 Pick이 부품을 핑거 중앙과 예정된 yaw로 잡았는지 검증한다.
- 안전 높이 접근 후 수직 하강하며 큰 대각선 접근을 금지한다.
- S22는 로봇이 가려도 조립 전 board snapshot을 유지하고, 로봇 후퇴 후 결과를
  다시 검사한다.

초기 MVP에서는 GPU/HBM 한 종류로 반복 오차를 먼저 측정한다. 정확도가 부족하면
모든 Place에 재관측을 강제하기보다 D435가 목표를 볼 수 있는 별도 pre-place
inspection pose를 추가하거나, S22가 로봇 이동 중에도 보이는 slot만 연속 추적한다.

## 검사 결과 데이터

각 slot에 다음 값을 남긴다.

```text
slot_id, expected_part, detected_part, present,
x_error_mm, y_error_mm, yaw_error_deg, height_error_mm,
surface_score, confidence, result, image_path, timestamp
```

허용 오차는 한 값으로 하드코딩하지 않고 GPU/HBM/소형 칩 등 recipe별로 실제
출력물과 반복 시험 결과를 기반으로 정한다.
