# 비전 캘리브레이션 작업 기록

## 현재 기준 상태

- 방식: FR5 말단 D435 Eye-in-Hand + 고정 ChArUco 보드.
- 변환 체인:
  `T_base_target = T_base_flange @ T_flange_camera @ T_camera_target`
- 적용 중인 Hand-Eye: 기존 40개, Euler `xyz`, DANIILIDIS.
- 독립 검증 5자세: 3D 오차 평균 `1.833 mm`, 최대 `2.981 mm`.
- Refinement 15개 결과는 독립 검증 최대 `30.062 mm`로 부적합해 미적용.
- 2026-08-12부터 동일 고정 마커의 멀티포즈 CSV 진단 기능을 사용해 관측
  자세 의존성을 먼저 측정한 뒤 재캘리브레이션 여부를 결정한다.
- 상세 좌표계 분석: `calibration/COORDINATE_DIAGNOSTIC.md`.

## 2026-08-12 — 동일 마커 10자세 멀티포즈 검증

- 대상: 고정 ChArUco 보드의 marker ID 8 중심.
- 입력 조건: RGB `1920x1080@15`, 모든 샘플에서 markers `17/17`, corners
  `24/24`; 이미지와 CameraInfo 해상도 일치.
- 사용 Hand-Eye: 기존 40개 결과, SHA-256 접두사 `f08dc2dd9a40`.
- 10자세 Base XYZ 평균: `[-316.010, -27.372, -13.883] mm`.
- 축별 표준편차: X `0.468 mm`, Y `0.303 mm`, Z `1.083 mm`.
- 축별 전체 범위: X `1.524 mm`, Y `0.939 mm`, Z `3.004 mm`.
- 평균점 기준 3D 오차: RMS `1.218 mm`, 최대 `2.172 mm`.
- 자세 내 프레임 jitter 최대는 샘플별 `0.030~0.053 mm`로 매우 작았다.
  따라서 관측 자세별 차이는 영상 프레임 흔들림보다 Hand-Eye/ChArUco pose의
  체계적 잔여 오차에 가깝다.
- reprojection median은 `0.240~0.783 px`, max는 `0.512~1.686 px`로 설정된
  허용 기준 안에 있었다. 샘플 5가 가장 높은 reprojection error였지만 검출
  마커와 코너는 모두 정상이다.
- 가장 큰 평균 대비 오차는 sample 3에서 `2.172 mm`였고, Tool RY 방향
  기울기 자세에서 Z 변화가 크게 나타났다. 단순 Pearson 상관계수는 RX
  `-0.106`, RY `-0.354`, RZ `0.090`이며 표본이 10개뿐이므로 진단 참고값이다.
- 판단: 기존 40개 Hand-Eye가 수 cm 단위로 잘못됐다는 증거는 없다. 현재
  결과는 일반 접근에는 사용할 수 있지만 실제 크기에 가까운 소형 칩의 정밀
  배치에는 1~3 mm 잔여 자세 의존 오차가 크므로 추가 개선이 필요하다.
- 원본 데이터:
  `calibration/data/handeye_multipose_validation.csv`.

### 10자세 기반 Hand-Eye 후보 계산 결과

- 고정 보드 제약으로 `T_flange_camera`와 고정 `T_base_board`를 함께 최적화해
  여러 translation/rotation 가중치의 후보를 오프라인 계산했다.
- 후보들은 기존 Camera-to-Flange에서 translation 약 `10~19 mm`, rotation
  약 `0.54~1.85 deg` 변화를 요구했다.
- 후보를 수집에 사용하지 않은 기존 독립 검증 5자세에 적용하면 3D 오차가
  평균 `4.640~5.010 mm`, 최대 `7.038~12.033 mm`로 기존
  `1.833/2.981 mm`보다 악화됐다.
- 따라서 10자세에만 맞춘 후보는 과적합 또는 특정 자세의 planar pose bias를
  흡수한 것으로 판단하며 저장된 `handeye_result.json`에는 적용하지 않았다.
- Leave-one-out 고정 보드 원점 예측에서 sample 3의 오차가 `5.640 mm`로 가장
  컸다. sample 3은 RY 기울기 한 방향이며, 정면 대비 marker 중심 차이도
  `2.980 mm`로 가장 컸다.
- 다음 진단은 정면 → RY -10 → 정면 → RY +10 → 정면처럼 기준 자세를
  사이에 반복해 기계적 복귀성/시간 드리프트와 각도 의존 pose bias를 분리한다.

## 2026-08-12 — 정면/기울기 반복성 분리 검증

- 순서: 정면 → 기울기 한 방향 → 정면 → 반대 기울기 → 정면, 총 5자세.
- 정면 3회의 Base marker 중심 평균:
  `[-315.994, -27.410, -14.716] mm`.
- 정면 3회 축별 전체 범위: X `0.102 mm`, Y `0.015 mm`, Z `0.015 mm`;
  평균 대비 최대 3D 차이 `0.053 mm`.
- 따라서 저장 자세 복귀성, 보드 고정 및 단시간 드리프트는 이번 측정에서
  주된 오차 원인이 아니다.
- 첫 기울기 자세의 정면 평균 대비 차이:
  `[+0.701, -0.336, +0.337] mm`, 3D `0.847 mm`, reprojection `0.391 px`.
- 반대 기울기 자세의 정면 평균 대비 차이:
  `[-0.437, +0.547, +2.313] mm`, 3D `2.417 mm`, reprojection `0.777 px`.
- 두 기울기 자세 사이 차이: 3D `2.446 mm`.
- 해석: 로봇의 같은 정면 자세 복귀는 0.1 mm 수준으로 안정적이지만 특정
  기울기 방향에서 Z 중심으로 비대칭 오차가 재현됐다. 해당 자세에서
  reprojection error도 함께 증가해 Hand-Eye 회전 잔차뿐 아니라 평면
  ChArUco pose 추정 bias/화질 조건을 함께 비교해야 한다.
- 원본 데이터: `calibration/data/handeye_ry_repeatability.csv`.

### 평면 IPPE pose 비교 중단

- 같은 ChArUco 코너에 평면용 `SOLVEPNP_IPPE`를 적용해 비교했다.
- 정면 sample 1은 저장됐지만 두 번째 기울기 자세에서는 reprojection median
  약 `1.195~1.268 px`, max 약 `3.597~3.681 px`가 반복됐다.
- 설정된 품질 기준 median `1.2 px`, max `3.0 px`를 특히 최대 오차에서
  지속적으로 초과해 프레임을 저장하지 않았다.
- 같은 명목 기울기의 기존 ChArUco 방식 reprojection은 약 `0.391 px`였으므로
  IPPE는 이번 카메라/보드 조건의 개선안이 아니다. 기준을 완화해 억지로
  저장하지 않고 시험을 중단했다.
- 부분 CSV `calibration/data/handeye_ry_repeatability_ippe.csv`는 실패 실험
  근거로 보존하며 런타임 pose 방식은 변경하지 않았다.

### SQPnP 비교와 해상도 조건 확인

- 동일 기울기에서 SQPnP는 reprojection median/max `0.397/0.936 px`로
  정상 통과했다.
- 기존 ChArUco 결과와 SQPnP의 Base marker 중심 차이는 `0.041 mm`뿐이어서
  solver 변경으로 기울기 오차가 해결되지는 않는다.
- FR5 API `GetActualToolFlangePose(0)`와 `/nonrt_state_data.flange_*`를 직접
  비교했으며 위치 약 `0.001 mm`, 각도 약 `0.0002 deg` 수준으로 일치했다.
  드라이버 문서상 A/B/C는 고정축 X/Y/Z 회전이므로 SciPy lowercase `xyz`
  해석과도 맞는다.
- 기존 적용 Hand-Eye 40개와 독립 검증 5개 원본은 모두 `640x480`, 새
  refinement 15개는 모두 `1920x1080`임을 확인했다.
- 640 원본으로 ChArUco intrinsic을 오프라인 재추정하면 해당 5자세에서 일부
  개선 가능성이 보였지만 640 intrinsic은 1920 입력에 사용할 수 없다.
- 1920 refinement 15개로 intrinsic을 재추정한 뒤 pose를 다시 계산하면
  Hand-Eye 내부 translation 잔차가 median `0.54~0.69 mm`, max
  `0.91~1.38 mm`로 개선되고 Camera-to-Flange 후보도 기존값 근처로 돌아왔다.
- 그러나 640 독립 검증과 해상도 조건이 달라 공정한 최종 판정이 아니다.
  다음 단계는 수집에 사용하지 않은 1920x1080 별도 5자세 이미지 검증이다.

### 1920 독립 검증 첫 시도 초기화

- `validation_1080_samples.json`에 4개를 저장한 뒤 5번째 자세가 3번째와
  중복으로 판정됐다.
- 조합 이동이 실제 Flange pose에서 중복될 수 있어 첫 시도 4개와 원본
  이미지를 삭제하지 않고
  `calibration/archive/validation_1080_restart_20260812_1101/`로 이동했다.
- 활성 `calibration/data/validation_1080_samples.json`과 이미지 폴더는 없는
  초기 상태로 확인했다. 기존 Hand-Eye/학습/refinement 데이터는 변경하지 않았다.
- 재수집은 조합 이동을 피하고 정면, Tool RY ±7°, Base X +40 mm,
  Base Y -40 mm의 명확히 구분되는 5자세를 사용한다.

### 1920 독립 검증 6자세와 후보 생성

- 재수집 결과 서로 다른 6개 Flange 자세가 저장됐고 모두 1920x1080,
  corners 24/24였다. reprojection median/max 범위는 각각
  `0.225~0.627 px` / `0.466~1.428 px`로 허용 기준 안이다.
- 현재 Hand-Eye + 공장 CameraInfo intrinsic으로 재처리한 독립 6자세 3D
  오차 평균/중앙/최대는 `2.035/1.429/6.345 mm`였다.
- 현재 Hand-Eye + refinement 15개로 추정한 1920 intrinsic은
  `0.636/0.605/0.961 mm`로 크게 개선됐다.
- 새 15개 DANIILIDIS Hand-Eye + 1920 intrinsic 후보는
  `0.572/0.615/0.753 mm`, 축별 전체 범위 X/Y/Z
  `1.096/1.122/0.660 mm`였다.
- 따라서 주요 개선 요인은 1920 해상도에 맞춘 intrinsic이며 새 Hand-Eye는
  추가적인 소폭 개선을 제공한다.
- 재현 스크립트 `calibration/scripts/build_1080_calibration_candidate.py`를
  추가하고 다음 비활성 후보를 생성했다:
  `camera_intrinsics_1920x1080_candidate.json`,
  `handeye_result_1080_candidate.json`.
- 활성 `handeye_result.json`은 변경하지 않았으며 백업과 SHA-256이 동일하다.
- 마커 dry-run과 멀티포즈 검증에 후보를 명시적으로만 로드하는
  `--result-file`, `--intrinsics-file` 옵션을 추가했다. 기본값은 기존 활성
  결과/CameraInfo를 계속 사용한다.

### 1080 후보 첫 dry-run

- marker ID 8, 현재 기울기 자세에서 후보 Hand-Eye/intrinsic을 명시적으로
  로드해 Base-Z 100 mm dry-run을 수행했다. 로봇 이동 명령은 없었다.
- Marker center Base: `[-314.539, -24.586, -12.563] mm`.
- Target TCP Base: `[-314.539, -24.586, 87.437] mm`로 X/Y는 동일하고 Z에
  정확히 `+100.000 mm`가 적용됐다.
- 20프레임 center jitter median/max: `0.013/0.025 mm`.
- 행렬은 유한값이며 보드 법선과 목표 Tool 방향에도 비정상 반전은 없었다.
- 다음 확인은 로봇/보드를 움직이지 않은 같은 자세에서 기존 활성 결과로
  별도 dry-run해 두 계산값의 차이를 비교하는 것이다.

### 동일 로봇 자세 활성값/후보값 비교

- 비교 당시 로봇은 사용자가 저장한 정면 기준 자세가 아니라 검증 과정의 다른
  자세였지만, 후보/활성 dry-run 사이 Flange 위치 차이는 `0.0021 mm`로 같은
  자세 비교 조건을 충족했다.
- 활성 Marker center: `[-316.211, -26.854, -13.365] mm`.
- 후보 Marker center: `[-314.539, -24.586, -12.563] mm`.
- 후보-활성 차이: `[+1.673, +2.268, +0.802] mm`, 3D `2.930 mm`.
- jitter max는 활성/후보 각각 `0.028/0.025 mm`로 둘 다 안정적이다.
- 이 비교는 두 계산법 차이를 확인한 것이며 절대 정답을 물리적으로 확인한
  시험은 아니다. 실제 접근 검증 전에는 저장된 정면 기준 자세로 복귀해 후보
  dry-run을 다시 생성한다.

### 1080 후보 실제 접근의 물리 측정

- 후보 Hand-Eye/intrinsic으로 marker ID 8의 Base +Z 100 mm 접근 후 TCP
  정렬에 필요한 Tool 증분을 물리적으로 확인했다.
- 처음 보고된 `[+3, -2, 약 +2.5] mm`, `[-6, -0.5, +2] mm`는 육안 추정
  가능성이 있어 유효 정량 결과에서 제외하고 예비 관찰값으로만 남긴다.
- 첫 유효 측정 절차: 저장된 관측 좌표에서 후보 접근 → 데카르트 Tool 기준으로
  목표 근처까지 하강 → 1 mm와 0.5 mm 조그 단위로 XY 중심 정렬.
- 첫 유효 결과: Tool `[X -2.5, Y -2.5] mm`, XY 크기 약 `3.54 mm`.
- 하강량은 중심 확인을 위한 동작이므로 이 측정에서는 Z 오차로 사용하지 않는다.
- 한 자세 결과만으로 고정 offset을 적용하지 않고 동일 절차를 다른 관측 자세에서
  반복해 Tool XY 보정의 방향과 크기가 재현되는지 확인한다.
- 두 번째 유효 측정은 다른 관측 자세에서 Tool `[X -5.5, Y 0] mm`였다.
- 최근 목표 Tool 회전행렬로 환산하면 두 번째 보정은 Base에서 대략
  `[X 0.0, Y -5.5, Z +0.01] mm` 방향이다. 첫 측정 Tool
  `[-2.5,-2.5] mm`와 동일한 고정 Tool/Base offset이 아니다.
- 다음 분리 시험은 첫 측정에 사용한 동일 저장 관측 좌표로 정확히 복귀해
  같은 절차를 반복하는 것이다. 첫 값이 재현되면 자세 의존 오차, 재현되지
  않으면 물리 측정/TCP 포인터 절차의 반복성 문제로 판단한다.
- 첫 저장 관측 좌표로 복귀한 세 번째 측정에서 Tool
  `[X -2.5, Y -2.5] mm`가 다시 재현됐다.
- 결론: 동일 관측 자세의 물리 측정 반복성은 0.5 mm 조그 분해능 안에서
  확인됐고, 다른 관측 자세의 `[-5.5, 0] mm`와의 차이는 실제 자세 의존
  오차다. 고정 TCP/Tool correction 가설은 기각한다.
- 다음 개선은 Hand-Eye와 결합된 데이터에서 intrinsic을 동시에 추정하는 대신,
  1920x1080 전용 camera intrinsic을 보드가 영상 전체 영역과 다양한 기울기를
  차지하도록 별도 수집·검증한 후 그 intrinsic을 고정하고 Hand-Eye를 새로
  계산하는 방식이 적합하다.
## 2026-08-12 — 33장 내부 파라미터와 Hand-Eye 교차 검증

- 33장 전용 내부 파라미터를 고정하여 기존 15자세 Hand-Eye 이미지를 다시 계산했다.
- DANIILIDIS/xyz 후보의 Camera→Flange translation: `[-30.966, -88.386, 21.758] mm`.
- 독립 6자세 검증 오차: 평균 2.351 mm, 중앙값 2.601 mm, 최대 3.917 mm.
- 방법 비교 최선 ANDREFF/xyz도 평균 1.398 mm, 최대 2.838 mm였으며, zyx 해석은 44 mm 이상으로 명백히 부적합했다.
- 기존 15장 자체 추정 intrinsic에서 나온 0.57 mm 결과는 intrinsic과 Hand-Eye가 서로 오차를 보상했을 가능성이 있으므로 확정값으로 채택하지 않는다.
- 활성 `handeye_result.json`은 변경하지 않았다. 다음 단계는 33장 intrinsic을 고정하고 회전·거리·화면 위치 다양성이 충분한 Hand-Eye 표본을 25–30자세로 새로 수집하는 것이다.
- 후보 파일: `calibration/data/handeye_result_1080_intrinsic33_candidate.json`.
## 2026-08-12 — intrinsic33 고정 Hand-Eye 25자세 수집 완료

- 새 파일 `calibration/data/handeye_intrinsic33_samples.json`에 25자세 저장 완료.
- 전 이미지 1920×1080, marker 최소/중앙값 `14/17`, corner `18/24`.
- 저장 당시 reprojection median의 전체 중앙값/최대값은 `0.364/0.836 px`.
- Flange 위치 범위 X/Y/Z는 약 `113.3/103.7/100.0 mm`, 기준 자세 대비
  회전 변화는 각 축 약 `±12~14°`로 양방향 다양성을 확보했다.
- intrinsic33을 고정한 후보 비교에서 xyz 해석이 유효했고 zyx는 48 mm 이상의
  독립 검증 오차로 제외했다.
- 기존 독립 6자세 기준 ANDREFF/xyz가 평균/중앙값/최대
  `0.985/1.044/1.276 mm`로 가장 작았다. DANIILIDIS/xyz는
  `1.981/2.145/3.071 mm`였다.
- 다만 25개 학습 자세 자체의 Base board 일관성은 ANDREFF 기준 평균
  `2.143 mm`, 최대 `4.237 mm`로 남아 있다. 단일 저품질 검출만의 문제가
  아니라 자세 조합에 따른 Z 및 XY 편향이 섞여 있어 즉시 활성화하지 않는다.
- 다음 단계는 후보를 로봇 이동에 바로 적용하는 것이 아니라 별도의 신규
  멀티포즈 검증 데이터로 재현성을 확인하는 것이다.
## 2026-08-12 — intrinsic33 + Hand-Eye25 ANDREFF 후보 dry-run

- marker ID 8을 정면 기준 관측 자세에서 20프레임 계산했다.
- 후보 계산 Marker Base XYZ: `[-304.325, -22.007, -9.516] mm`.
- Base Z +100 mm 접근 목표 TCP: `[-304.325, -22.007, 90.484] mm`.
- 프레임 jitter 중앙값/최대: `0.013/0.028 mm`로 관측은 안정적이었다.
- Camera→Flange translation: `[-31.051, -71.981, 43.791] mm`.
- `--dry-run`으로 실행했으며 로봇 이동 명령은 전송하지 않았다.
- 출력: `calibration/data/marker_target_intrinsic33_handeye25_dryrun.json`.
## 2026-08-12 — RGB-PnP 스케일의 depth 독립 확인

- 활성 파이프라인의 공장 CameraInfo로 marker 8의 camera Z를 계산하고 aligned
  D435 depth와 독립 비교했다.
- RGB-PnP/depth Z는 `533.040/532.000 mm`로 약 `1.04 mm` 차이였다.
- 따라서 새 intrinsic 후보의 약 12 mm 깊이 증가는 보드 실거리 변화가 아니라
  평면 intrinsic 추정 과적합으로 판정한다.
- 운영 원칙: 공장 CameraInfo와 기존 활성 Hand-Eye를 유지하고, depth는 높이 및
  RGB pose 이상치 검증의 보조 계층으로 사용한다.
### FR5 ABC 회전 규약 및 기울기 PnP 재점검

- 공장 intrinsic + 새 25자세에 대해 `xyz`, `XYZ`, `zyx`, `ZYX`와 OpenCV
  Hand-Eye 5개 방법을 전수 비교했다.
- 기존 `xyz`가 가장 우수했으며 대문자/역순 규약은 독립 검증 오차가 최소
  약 29 mm 이상으로 부적합했다. 단순 Euler 규약 선택 오류는 아니다.
- RY ±10°에서 RGB-PnP Z와 aligned depth가 각각 약 0.28/0.37 mm 차이로
  일치했다. 남은 Base 좌표 자세 의존성은 Flange↔Camera extrinsic 회전과
  평면 보드 orientation 추정의 결합 문제로 범위를 좁혔다.
## 2026-08-12 — depth 기반 marker 8 Base 좌표 3자세 검증

- 기존 활성 Hand-Eye와 aligned depth를 사용해 정면, Tool RY +10°, RY -10°를
  각각 30프레임 측정했다.
- 정면 depth Base XYZ: `[-316.048, -27.451, -13.748] mm`.
- RY +10°: `[-315.279, -27.590, -11.773] mm`; 정면 대비
  `[+0.769, -0.139, +1.975] mm`, 3D 약 `2.12 mm`.
- RY -10°: `[-316.892, -27.559, -12.892] mm`; 정면 대비
  `[-0.844, -0.108, +0.856] mm`, 3D 약 `1.21 mm`.
- RGB-PnP 단독보다 depth가 Z 편차를 줄였지만, 자세에 따라 최대 약 2.1 mm가
  남으므로 depth만 단순 대체하는 것으로 정밀 조립 요구를 충족하지 못한다.
- 다음 단계는 여러 자세의 `T_base_flange + depth Camera XYZ`를 함께 저장하고
  고정 marker Base 점 제약으로 Flange↔Camera translation/rotation을 최적화하는
  depth point 기반 extrinsic refinement이다.
## 2026-08-12 — depth point extrinsic refinement 7자세

- marker 8 고정 상태에서 `RY -10, 정면, RY +10, RX +10, RX -10,
  RZ +10, RZ -10`의 7자세를 각각 30프레임 저장했다.
- 데이터: `calibration/data/depth_extrinsic_refinement_samples.json`.
- 기존 활성 extrinsic의 depth point 고정점 잔차는 평균/최대
  `1.214/2.131 mm`였다.
- 6DoF 미세 최적화 후보는 평균 `0.846 mm`로 감소했으나 최대가
  `2.193 mm`로 증가했고, translation 보정도 약 4–5 mm로 커서 활성화하지
  않았다.
- 후보 파일은 진단 근거로만 보존:
  `calibration/data/handeye_result_depth_refined_candidate.json`.
- 결론: 소수 고정점 depth 표본으로 extrinsic을 강제 수정하지 않고 기존 활성값을
  유지한다. 실제 파지는 단발 절대좌표 이동보다 `안전 접근 → 가까운 거리에서
  RGB-D 재검출 → 잔차 보정`의 폐루프 방식으로 구현한다.
