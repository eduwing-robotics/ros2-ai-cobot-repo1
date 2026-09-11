# 카메라 작업 기록

## 2026-09-11 — Make multi-PC ROS camera discovery explicit

- The live host still publishes `/camera2/image_stream/compressed` at about
  30 FPS and `/camera3/image_raw/compressed` at about 13 FPS. Both topics are
  `sensor_msgs/msg/CompressedImage` with depth-one `BEST_EFFORT`/`VOLATILE`
  QoS, and a local JPEG probe received valid `FF D8 FF E0` frames.
- The reported teammate rqt symptom was not a publisher stall: the live ROS
  graph had no rqt subscription on either camera topic. The only rqt process
  was subscribed to the local stop-image overlay. This means the remote viewer
  had either not created the compressed transport subscription or was running
  with a different ROS discovery scope/domain; a topic name alone does not
  prove that image data is being received.
- `scripts/ksmc_env.sh` now makes the intended cell-wide defaults explicit:
  `ROS_DOMAIN_ID=5`, `ROS_LOCALHOST_ONLY=0`, and
  `ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET`. The existing Fast DDS profile still
  allows the cell Wi-Fi and wired interface while excluding the GoPro-only
  WLAN. No camera resolution, JPEG setting, topic name or QoS was changed.
- This is a configuration/read-only verification change. No Endpoint process,
  robot, conveyor, Job or Sequencer command was started or restarted. The
  remote PCs must source the workspace environment (or set the same three
  values) before opening rqt and must choose each base topic with the
  `compressed` transport.

## 2026-09-11 — Protect S22 HQ lifecycle from duplicate launchers

- The S22 stream interruption at 11:56 KST occurred when the combined
  conveyor cell failed to recognise an already-running `bash
  ./run_s22_conveyor_hq.sh` and launched a second HQ. The second HQ's stale-ROI
  cleanup terminated the first ROI; the first HQ then released the shared
  scrcpy camera and the cell stopped its server. This was a launcher ownership
  race; no USB, resolution, JPEG, FPS or DDS transport setting caused it.
- HQ process matching now resolves the actual script argument in `/proc`, and
  the HQ launcher holds `runtime/s22_camera_control/hq_launcher.lock` before
  any cleanup. Repeated absolute/relative invocations therefore reuse one
  camera/ROI pair. The existing camera launcher and GoPro remain separate.
- A live monitor-only reuse test kept the original HQ, camera2 node and ROI
  alive for the full test window. The final integrated server was then started
  in a detached session without restarting that HQ; no camera command or
  physical motion was issued. Current stream settings and topic/QoS contracts
  are unchanged.

## 2026-09-11 — rqt compressed transport selection

- The teammate rqt report was reproducible as a transport/type selection
  error, not an absent camera frame. Passing a transport-specific
  `/compressed` name to `rqt_image_view` makes it create a
  `sensor_msgs/msg/Image` subscription on the
  `sensor_msgs/msg/CompressedImage` topic. The topic remains visible, but no
  image can be decoded. The official plugin source also represents compressed
  entries as a base topic plus a transport label and creates the compressed
  subscriber from that pair ([rqt_image_view source](https://github.com/ros-visualization/rqt_image_view/blob/rolling-devel/src/rqt_image_view/image_view.cpp#L327-L437)).
- The final camera transport remains `BEST_EFFORT/KEEP_LAST(1)/VOLATILE`, which
  is the rqt `SensorDataQoS` and the existing ROI/ROS-TCP Endpoint profile. The
  earlier temporary reliable-camera experiment was rolled back to avoid adding
  reliable retransmission to the high-rate viewer path. Topic names, frame
  sizes, JPEG settings, capture transports and latest-frame behavior are
  unchanged.
- In rqt, choose base `/camera2/image_stream`, `/camera3/image_raw`, or
  `/vision/conveyor/stop_image` and select the `compressed` transport entry
  (the plugin displays it as a base topic with a transport label). Use the full
  `/.../compressed` names only for `ros2 topic echo`, Unity and direct ROS
  subscribers. A read-only offscreen reproduction confirmed the bad direct
  selection; it was terminated without touching Endpoint or motion.
- After the camera nodes were restored, S22 remained about 29.6 FPS and GoPro
  about 13.6 FPS. Both compressed topics delivered JPEGs to best-effort
  subscribers; camera offline tests passed (`23 passed`). The ROS-TCP
  Endpoint/Unity process remains owned and started by the robot-arm teammate;
  it was not copied, started or restarted, and no robot, conveyor, Job or
  Sequencer command was issued.

## 2026-09-11 S22와 컨베이어 서버 원커맨드 실행

- `run_conveyor_remote_server.sh --with-s22`와 `run_conveyor_cell.sh`를 추가했다.
  컨베이어 서버가 `/cmd_vel` 소유권을 먼저 확보한 뒤 `run_s22_conveyor_hq.sh`를
  시작하거나 기존 HQ 런처를 재사용한다. 기존 서버 잠금이 있으면 S22를 건드리지
  않고 종료하며, 이 런처는 팀원이 관리하는 ROS-TCP Endpoint와 GoPro를 시작하지
  않는다.
- Wi-Fi SSH를 보존하기 위해 노트북의 `wlo1=192.168.11.4/24`와 기본 경로는
  그대로 두고, 유선 `enp129s0=10.77.5.1/30`은 별도 경로로 유지했다. 로봇
  `musk@192.168.11.101`에 대한 읽기 전용 SSH는 인증 거부로 끝났고 로봇 측
  인터페이스나 Wi-Fi 설정은 변경하지 않았다. 로봇에 `10.77.5.2/30`을 추가한
  뒤 사용할 수 있는 유선 전용 Fast DDS 프로파일을 별도로 제공했다.
- `bash -n`, XML 파싱, `--help` 검증을 통과했고 기존 서버 잠금 상태에서 실제
  `--monitor-only` 실행이 S22를 시작하지 않고 종료되는 것을 확인했다. 이 작업
  중 카메라·로봇·컨베이어·Endpoint 명령은 발행하지 않았다. 로봇 콘솔 또는
  인증된 SSH가 복구될 때까지 유선 ROS 전환은 미완료다.

## 2026-09-11 S22 delayed-frame handling

- No camera transport, resolution, JPEG quality, USB or lens setting changed.
  The conveyor ROI consumer now ignores a delayed source frame for a new
  stop/arrival decision without turning that delay into a ready-liveness fault.
  Explicit invalid/decode status still reports `ready=false`; the finite
  motion timeout remains in the controller.
- The existing 960x540/JPEG84 control stream and 1920x1080/JPEG95 analysis
  stream were not restarted or reconfigured for this change. No capture,
  robot or conveyor command was sent; the only live check was a guarded move
  request rejected before any nonzero `/cmd_vel` because the robot subscriber
  was absent.

## 2026-09-10 S22 Unity stop-screen delivery

- rqt continued to receive the S22 overlay, which isolates the remaining
  display failure to the Unity ROS topic path rather than USB capture. The
  stop-image publisher now offers depth-1 `RELIABLE` QoS so a Unity reliable
  subscription can match it; the raw/control camera stream remains
  best-effort sensor data with the existing resolution and JPEG settings.
- With the conveyor in `MANUAL_STOP/moving=false`, the existing S22 launcher was
  restarted without changing phone, lens, source resolution, or source FPS.
  Only the network/control stream changed to `960x540/JPEG84`; the
  `1920x1080/JPEG95` source and inspection path remain unchanged. A 20-second
  read-only probe received 590 control images (29.5 FPS), and the ROI emitted
  592 ready heartbeats (29.6 FPS). The team's ROS-TCP Endpoint registered its
  `CompressedImage` subscriber after the restart; its process remains team
  managed.
- A live frame decoded directly from `/vision/conveyor/stop_image/compressed`
  was `960x540` JPEG and visibly contained both calibrated stop lines and the
  dashboard. The ROS graph showed the Unity Endpoint subscriber on this
  stop-image topic, while `/camera2/image_stream/compressed` remained the
  unannotated source view with only the ROI subscriber. Seeing the source view
  in rqt therefore does not validate the Unity stop-screen callback. The
  remaining blank display is on the team-managed Endpoint/Unity rendering path;
  the Unity project source is not present in this repository.


## 2026-09-10 S22 heartbeat transport mitigation

- The interrupted move correlated with stale S22 control frames and missing ready heartbeats. The camera launcher now runs with the validated Fast DDS profile that excludes the GoPro-only WLAN and uses non-blocking UDP sends; camera settings and USB transport are unchanged. Matched post-change audit: 30 FPS capture, no stale image samples, and no false ready samples in the measured 30-second window. The physical Ethernet link is 1 Gb/s, but the robot endpoint is not yet configured on that link, so remote ROS traffic still uses robot Wi-Fi. Detailed evidence and limits: [grouped vision record](vision.md#2026-09-10-s22-heartbeat-latency-and-wired-transport-mitigation).

## 2026-09-10 S22 overview restoration during arrival deployment

- Restored the absent S22 stream launcher using existing stored camera/quality settings after confirming USB authorization and zero received images. Final ROI observations use fresh frames and vision readiness is true. Exit cause remains undetermined. Deployment evidence and limitations are recorded once in the [grouped vision record](vision.md#2026-09-10-current-s22-arrival-observation-and-completed-request-handling).

## 2026-09-08 flash pair experiment

- Existing capture script used once with OFF and once ON in separate flash_pair_20260908_trial1 folders; EXIF verifies actual flash firing for ON. Both optical7mm, 4000x3000. Managed overview restored. Default script/config remains OFF; Samsung Camera last capture UI was ON and normal launcher explicitly forces OFF on next default capture. No persistent stream settings, server restart or conveyor/robot commands changed. Findings and exposure values: [vision comparison](vision.md#2026-09-08-flash-off-on-physical-comparison).

## 2026-09-08 capture freshness and owned lifecycle cleanup

- S22 source-stamped fresh snapshots, GoPro recovery/shutdown serialization and owned optical-capture cleanup were hardened without changing quality/zoom/transport settings.65mocked tests passed; no capture/device commands or server restart. Full behavior, evidence and hardware limitations are recorded once in [parallel subsystem hardening](vision.md#2026-09-08-parallel-subsystem-hardening-and-offline-regression-runner).

## 2026-09-06 S22 AF/AE diagnostic for Inductor appearance drift

- Added opt-in S22_INSPECTION_FOCUS_LOCK=1 long-press and S22_INSPECTION_FOCUS_X_PERCENT/Y_PERCENT integer1..99 overrides. Legacy defaults50/38 and lock-off remain unchanged. Saved diagnostic screenshot under runtime/inspection/s22_focus_lock_diagnostic.png; visually verified padlock icon, first on background then on board with73/44 at the current physical view. These UI coordinates depend on placement and are not an automatic board focus detector. Per-shot AF/AE lock does not establish fixed ISO/WB across camera force-stops.
- Captures200835/201306 tested locking; board-focused I1 still0.494361, so this is not the false-positive fix and is not enabled by default. Subsequent201823/201955/202105 validation used the unchanged flash-off3.5x protocol. Each optical image4000x3000, focal7mm/69mm-equivalent verified by existing capture checks; managed overview restored. No motor commands or stop-line changes. Appearance model findings and limitations are recorded once in docs/logs/vision.md (2026-09-06 Inductor normal-appearance refresh and three fresh trials).

## 2026-08-21 — D435 트레이 부품 안전 접근 단계

- `vision_assembly/scripts/move_tray_part_approach.py`와 실행 스크립트를 추가했다.
- 이 단계는 최신 안정 트레이 검출과 유효한 Hand-Eye Base 변환이 있을 때만
  선택 부품의 `Base XYZ + [0, 0, 100 mm]`로 TCP를 이동시킨다.
- 접촉 하강, 그리퍼 동작, 과거 실험의 XY 보정값, 자동 손목 회전은 포함하지
  않는다. 실제 이동에는 `--execute --confirm-move`가 모두 필요하며, dry-run이
  먼저 3개 MoveCart 단계와 목표 좌표를 출력한다.
- 트레이 검출 JSON에 `timestamp_unix`를 기록해 오래된 검출 좌표를 안전하게
  차단하도록 했다.

### 반복 접근 좌표 안정화 보완

- 로봇 이동 직후 카메라 지연 프레임과 최종 flange 자세가 섞일 수 있던 구조를
  보완했다. 이동 감지 시 객체·homography 이력을 비우고, 1.5초 정지 후에만
  Hand-Eye Base 좌표를 유효 처리한다.
- `capture_tray_part_target.py`를 추가했다. 동일 부품의 연속 검출 20개가
  1 mm 이내일 때 중앙값을 고정 저장하며, 이후 접근은 이 파일을 사용해
  프레임마다 달라지는 검출 좌표를 따르지 않는다.
- 흰 트레이의 SIFT/RANSAC 등록이 고정 시점에서도 토글되는 문제를 분리하기 위해
  `--registration-mode fixed_view`를 추가했다. 저장된 트레이 관찰 자세로 복귀한
  경우에만 identity homography와 기준 ROI를 사용하며, 다른 시점에서는 사용하지
  않는다.

### GPU 검출 안정화 확인

- GPU ROI는 높이 조건만 사용했을 때 트레이 그림자/경계 후보로 전환되며 고정
  시점에서도 최대 약 9 mm의 목표점 점프가 발생했다.
- GPU는 흰 트레이 위의 큰 검은 부품이므로 depth 높이 조건에 grayscale `<85`
  외형 조건을 추가했다. GPU 이외 부품의 기존 조건은 변경하지 않았다.
- `fixed_view`에서 GPU 1번을 10회 고정 수집한 결과 Base 좌표 중앙값은
  `[-520.220, -183.713, -41.624] mm`, 최대 반복 편차는 `0.005 mm`였다.
- 결과 파일: `vision_assembly/data/gpu_01_target.json`. 이 파일을 입력으로
  접근하면 실행 중인 검출 노드의 프레임별 좌표 변경을 따르지 않는다.

### GPU 상단 영역 확장

- GPU 영역 상단을 normalized Y `0.695 → 0.681`로 위쪽 칸막이 바로 아래까지
  확장했다.
- 위쪽 Inductor/SMD 영역 하단선(`0.680`)과는 약 1 px에 해당하는 `0.001`
  normalized 여백만 남겨 영역선이 겹치지 않도록 했다.

### 전체 트레이 오검출 분리

- 전체 부품에 공통 depth·면적 규칙을 적용한 화면에서 칸막이 그림자와 빈
  공간이 부품으로 표시되는 오검출을 확인했다.
- GPU Pick 검증 중에는 `--only-part-type gpu`로 GPU ROI만 검출·표시하도록
  분리했다. 나머지 부품은 각 색상/마킹/형상에 맞춘 전용 검출을 구현한 뒤
  다시 통합해야 하며, 현재 전체 오버레이를 Pick 판단에 사용하지 않는다.

### 트레이 2세트 수량 반영

- 실제 트레이에 조립용 부품이 2세트 배치된 상태인데, 기존 설정이 1세트
  수량(GPU 1, HBM 8 등)으로 제한돼 두 번째 부품을 버리거나 프레임마다 다른
  하나를 선택하는 문제가 있었다.
- 기대 수량을 GPU 2, HBM 16, VRM 10, Power Module 8, Inductor 4,
  SMD Capacitor 10으로 변경했다. GPU는 같은 높이에서 왼쪽→오른쪽 순으로
  `gpu #1`, `gpu #2`가 된다.

### GPU 전체 윤곽 보강

- GPU 로고·반사 때문에 검은색 픽셀 윤곽이 조각나면, 반복성은 좋아도 실제
  중심이 편향될 수 있음을 확인했다.
- GPU만 grayscale 임계값을 `85 → 115`로 완화하고, 높이 조건을 유지한 채
  closing kernel을 `25 px`로 키워 로고로 나뉜 검은 영역을 하나의 부품으로
  연결한다.
- 화면에는 조각난 contour 대신 해당 마스크의 `minAreaRect` 전체 사각형을
  표시하도록 변경했다. 다른 부품 검출 규칙은 바꾸지 않았다.

### GPU 원시 윤곽 표시 제거 및 안정 추적 표시

- 프레임마다 변하는 원시 GPU contour를 화면에 그리면 사용자가 실제 목표가
  흔들린다고 판단하게 되므로, GPU는 원시 윤곽을 숨겼다.
- 4프레임 이상 연결된 GPU track의 중앙값 중심·크기·각도로 만든 `GPU #n stable`
  사각형만 표시한다. 목표 저장도 동일한 안정 track을 입력으로 사용한다.

### GPU 흰 점 방향 기준 도입

- 안정 사각형 재구성 방식은 실제 GPU 사각형과 맞지 않아 표시에서 제외했다.
- GPU의 검은 본체 사각형은 기존 보수적 dark/depth 조건으로 검출하고, 좌하단의
  작은 흰 점을 body 내부의 밝고 저채도인 작은 원형 후보로 찾아 표시한다.
- 흰 점은 GPU의 180° 회전 방향을 구분하는 기준이며, 이후 Pick 자세 정렬에서
  본체 장축과 함께 사용한다. 점이 불확실하면 중심 접근 좌표에는 사용하지 않는다.
- 확대 확인 결과 흰 점은 본체의 좌하단 경계에 있어, 초기 내부 erosion 범위에서
  제외되고 있었다. 점 탐색 영역은 body box 바깥으로 7 px씩 확장하고 밝기·채도
  조건은 점의 anti-aliasing을 포함하도록 완화했다. 본체 중심 검출은 변경하지
  않았다.
- NVIDIA 로고의 밝은 글자가 흰 점으로 잘못 후보화되는 것을 확인해, GPU 사각형
  네 꼭짓점에서 25 px 이내인 후보만 orientation dot으로 허용하도록 제한했다.

### GPU 사각형 시간 중앙값 재구성 수정

- 원시 GPU box 크기는 depth mask 변화에 따라 프레임별로 달라져 화면과 목표
  검증에 적합하지 않았다.
- OpenCV의 폭·높이 교환 시 각도도 90° 전환되는 표현을 긴 변/짧은 변/긴 변
  각도로 정규화했다.
- 안정 track의 중앙값 중심·크기·각도로만 GPU 사각형을 그리도록 변경했다.

### GPU 실측 치수 적용

- GPU 실물 출력물의 사용자 측정치 `27 × 57 × 6 mm`를 적용했다.
- 기존 Unity/CAD 후보 `29.7166 × 57.1065 × 6.63831 mm`는 GPU 검출의 예상
  면적과 높이 조건에서 더 이상 사용하지 않는다.

- 고정 목표 파일의 기본 유효 시간을 45초에서 180초로 조정했다. 트레이 또는
  부품이 바뀐 경우에는 시간과 무관하게 새로 고정 수집해야 한다.
- GPU 목표 고정 수집은 검출 처리 주기를 고려해 기본 20개에서 5개 연속 샘플로
  조정했다. 1 mm를 넘는 후보는 자동 폐기하고 처음부터 다시 모으므로, 단순히
  샘플 수를 줄여 불안정 좌표를 허용하는 방식은 아니다.

## 2026-08-12 — D435 ChArUco 검출 깜빡임

- 목적: 정면 기준 자세에서 ChArUco 17개 마커와 24개 코너의 안정 검출.
- 증상: 로봇과 보드가 정지해 있어도 주석 화면의 마커가 프레임마다 깜빡임.
- 확인 결과: D435 RGB가 `640x480@30`으로 실행됐고 Depth도 활성화돼 있었다.
- 원인 후보: 40 cm 부근에서 16.8 mm 마커를 640x480으로 촬영해 마커 경계의
  픽셀 수가 부족해진 것. 검출 알고리즘 문제가 아니라 입력 해상도 조건 차이다.
- 이전 안정 조건: RGB `1920x1080@15`, Depth/align 비활성, RealSense 노드 1개.
- 사용자가 요청한 최소 변경: 현재 일반 실행 구성에서 RGB 프로파일만
  `1920x1080x15`로 바꾸고 Depth 기본 설정은 유지한다. 변경 적용에는 카메라
  노드 재시작이 필요하다.
- 권장 정밀 캘리브레이션 조건: USB 대역폭과 프레임 손상을 줄이기 위해
  `calibration/run_d435_rgb_stable.sh`의 RGB-only 모드 사용.
- 검증 기준: `/camera/camera/color/camera_info`가 1920x1080인지 확인하고,
  주석 화면에서 `markers 17/17`, `corners 24/24`가 안정적으로 유지되는지 본다.
- 주의: RealSense 노드를 동시에 두 개 실행하지 않는다.

## 2026-08-12 — 캘리브레이션 해상도 이력

- 기존 적용 Hand-Eye 40개 및 기존 독립 검증 5개 원본: `640x480`.
- 새 refinement 15개 및 현재 멀티포즈 검증: `1920x1080`.
- Extrinsic은 물리적으로 해상도와 무관하지만 각 해상도의 intrinsic과 코너
  정밀도가 ChArUco pose에 영향을 주어 Hand-Eye 추정값에 편향이 들어갈 수 있다.
- 이후 정밀 캘리브레이션과 독립 검증은 `1920x1080@15`로 통일한다.

## 2026-08-12 — 1920 intrinsic 전용 수집 절차

- Hand-Eye 영상에서 intrinsic을 동시에 추정하는 실험 편향을 줄이기 위해
  intrinsic 전용 저장 코드와 25구도 계획을 추가했다.
- 화면 중앙/상하좌우/네 모서리, RX/RY/RZ 기울기, 가까움/멂을 분산해
  1920x1080 color lens의 전체 영상 영역을 제약한다.
- 저장 코드: `calibration/scripts/capture_charuco_intrinsic_image.py`.
- 계산 코드: `calibration/scripts/calibrate_charuco_intrinsics.py`.
- 자세 계획: `calibration/INTRINSIC_1920_CAPTURE_PLAN.md`.
- 출력은 비활성 후보이며 기존 CameraInfo와 Hand-Eye를 자동 변경하지 않는다.

### 첫 intrinsic 수집 16장 폐기 보관

- 1~16번까지 저장한 뒤 사용자가 구도 오류를 확인해 처음부터 재수집하기로 했다.
- 해당 JSON과 원본 16장은 삭제하지 않고
  `calibration/archive/intrinsic_1920_discarded_20260812_1323/`로 이동했다.
- 활성 `calibration/data/intrinsic_1920_images.json`과 이미지 폴더가 없는 초기
  상태임을 확인했다. 다음 저장은 자동으로 sample 1부터 시작한다.
- Hand-Eye, 독립 검증, 기존 intrinsic 후보에는 변경이 없다.

### 재수집 sample 14 개별 제거

- 재수집 중 `14_center_rx_minus10` 구도가 잘못 저장돼 활성 JSON에서 14번
  항목만 제거했다.
- 원본 이미지는 삭제하지 않고
  `calibration/archive/intrinsic_1920_removed_samples_20260812/`
  `sample_014_center_rx_minus10_wrong.jpg`로 이동했다.
- 활성 데이터는 13개이며 다음 촬영은 다시 sample 14로 저장된다.

### Intrinsic 재수집 25장 중간 품질 판정

- 25장 모두 1920x1080, markers 17/17, corners 24/24, 라벨 중복 없음.
- 선명도 범위는 약 `67.7~98.6`으로 검출 품질은 양호하다.
- 실제 코너 중심 분포는 화면 폭의 `38.4~59.7%`, 높이의 `39.3~75.4%`로
  좌우 렌즈 가장자리 영역이 부족했다. 보드 면적도 `3.76~7.06%`였다.
- 예비 intrinsic RMS는 `0.0981 px`로 낮지만 왜곡계수 `k2=1.223`,
  `k3=-4.878`처럼 크게 추정돼 중앙 집중 데이터의 과적합 가능성이 있다.
- 후보는 활성화하지 않고 화면 좌우/모서리 중심 약 18~82%를 겨냥한 8장
  보충 계획(26~33)을 추가했다.
## 2026-08-12 — D435 1920×1080 전용 내부 파라미터 촬영 완료

- ChArUco 내부 파라미터 이미지 33장 수집 완료 (`intrinsic_1920_images.json`).
- 전 이미지 1920×1080, marker 17/17, corner 24/24 검출.
- 보드 중심 분포: 영상 폭 18.7–83.1%, 높이 26.2–77.0%, 면적 3.07–16.86%.
- 33장 후보: RMS 0.1664 px, `fx=1379.742`, `fy=1383.632`, `cx=968.874`, `cy=572.415`.
- 중앙 영상만 사용한 후보는 가장자리 영상에서 큰 오차가 발생했지만, 33장 후보는 전체/가장자리 재투영 오차가 각각 약 0.162/0.176 px로 안정적이었다.
- 파일: `calibration/data/camera_intrinsics_1920x1080_33images_candidate.json` (아직 활성화하지 않음).
## 2026-08-12 — D435 aligned depth 기반 RGB-PnP 거리 검증

- 현재 depth profile은 `848x480x30`, color-depth align은 최초 비활성 상태였다.
- 런타임 파라미터 `align_depth.enable=true`를 적용하여
  `/camera/camera/aligned_depth_to_color/image_raw` 발행을 확인했다.
- marker ID 8 중심에서 30프레임 RGB ChArUco PnP와 aligned depth를 비교했다.
- PnP Z 중앙값 `533.040 mm`, depth Z 중앙값 `532.000 mm`, 차이
  `-1.040 mm`이며 최대 절대 차이는 `1.071 mm`였다.
- 공장 CameraInfo 기반 RGB 거리 스케일은 현재 정면 자세에서 약 1 mm 안으로
  depth와 일치한다. 33장 자체 추정 intrinsic이 만든 약 12 mm 거리 증가는
  실제 depth와 맞지 않으므로 해당 후보를 사용하지 않는다.
- 진단 스크립트: `calibration/scripts/check_charuco_depth_consistency.py`.
### 기울기 양방향 depth 교차 검증

- Tool RY +10°: PnP/depth Z `517.266/517.000 mm`, 중앙 차이 `-0.284 mm`,
  최대 절대 차이 `1.304 mm`.
- Tool RY -10°: PnP/depth Z `530.635/531.000 mm`, 중앙 차이 `+0.372 mm`,
  최대 절대 차이 `1.386 mm`.
- 정면과 RY 양방향 모두 RGB-PnP 깊이가 aligned depth와 약 1.4 mm 이내로
  일치하므로, 기존 멀티포즈 Base 좌표 편차의 주원인은 RGB 깊이 스케일이 아니다.

## 2026-08-12 — 제조 셀 3대 카메라 역할 확정

- D435는 Eye-in-Hand Pick/Place 정밀 보정, depth 높이, 불확실 ROI 근접 재검사
  전용으로 사용한다.
- Galaxy S22는 조립 스테이션 수직 상부 고정형 주 검사 카메라로 사용한다.
  기판 도착·정지, board X/Y/yaw, 조립 완료 후 누락·위치·방향·오부품·표면
  이상 PASS/FAIL을 담당한다.
- GoPro HERO11은 상단 모서리 사선의 전체 공정 기록 및 사람/장애물 보조 감시를
  담당하며 정밀 좌표와 최종 품질 판정에는 사용하지 않는다.
- S22 최종 검사 전 FR5를 camera-clear 자세로 이동하고, S22에서 불확실한
  slot만 D435가 근접 재검사하는 계층형 검사 방식을 채택했다.
- 세부 배치와 불량별 담당표: `docs/CAMERA_ROLE_ARCHITECTURE.md`.

### S22 고정형 좌표계 역할 보완

- S22도 intrinsic과 `T_base_camera_s22`를 별도로 보정하면 고정형 Eye-to-Hand
  카메라로 FR5 Base 좌표를 계산할 수 있다.
- S22는 평면 기판/slot의 Base XY와 yaw를 제공하고, 단안 영상에 부족한 Z/높이는
  board plane, part recipe, D435 aligned depth로 보완한다.
- D435 근접 시 측면 장착 오프셋으로 목표가 FOV에서 사라지는 문제는 S22 전역
  좌표 + D435 마지막 유효 근접 측정 + 저속 단거리 하강으로 대응한다.
- D435 화면에 TCP가 보일 필요는 없으며 Hand-Eye와 FR5 TCP가 Camera-TCP 관계를
  제공한다. 두 카메라 Base 결과는 단순 평균하지 않고 차이가 크면 이동을 막는다.

### S22 컨베이어 도착·정지 검출 역할

- S22 영상에서 pre-stop ROI와 assembly target line/pose를 검출해 ROS
  conveyor controller에 오차를 제공한다.
- 목표점 근처에서는 저속으로 전환하고, 여러 프레임 동안 위치 오차와 영상 속도가
  모두 기준 안일 때만 정지 완료와 `assembly/ready`를 발행한다.
- 영상 timeout이나 기판 재이동이 발생하면 ready를 취소하고 컨베이어 정지 및
  FR5 조립 금지를 유지한다.

## 2026-08-13 — 3대 카메라 연결 방식과 지연 관리 원칙

- D435는 RGB-D 대역폭과 지연 안정성을 위해 노트북의 USB 3.x 포트에 직접
  연결한다. 현장에서는 `lsusb -t`의 `5000M` 이상 표시로 SuperSpeed 연결을
  확인한다.
- S22는 5 GHz Wi-Fi의 압축 영상으로 시작한다. 조립 완료 후 검사는 기판이
  정지한 상태라 수백 ms 지연을 허용할 수 있지만, 컨베이어 정지는 지연만큼
  오버슈트가 생기므로 pre-stop 감속과 정지 후 board pose 재측정을 유지한다.
- S22 영상은 1920x1080@15 FPS를 초기 목표로 하고, board arrival ROI는 가능한
  전체 15 FPS를 사용한다. YOLO 수량 검사는 정지 후 수행하므로 현재 5 FPS
  처리 제한을 유지할 수 있다.
- 현재 `gopro_camera3`는 Wi-Fi가 아니라 USB-C 가상 네트워크의 UDP Webcam
  stream을 FFmpeg로 디코딩한다. GoPro를 Wi-Fi로 바꾸지 않고 현재 USB 연결을
  유지한다.
- 영상 토픽은 compressed, QoS는 BEST_EFFORT/KEEP_LAST 1, 처리기는 항상 최신
  프레임 우선으로 구성해 오래된 프레임이 queue에 쌓이지 않게 한다.
- GoPro는 관제·기록용이며 네트워크 영상 기반 사람 검출은 보조 정지 계층일
  뿐 물리 비상정지나 안전 장치를 대체하지 않는다.
- 장비 연결 후 `ros2 topic hz`, `ros2 topic bw`, ping jitter와 실제 화면
  stopwatch 시험으로 FPS·대역폭·종단 지연을 각각 측정한다.

### 빈 기판 자체 특징 기반 좌표 검출 사전 확인

- D435 compressed RGB 토픽에서 현재 1920x1080 빈 기판 영상을 직접 저장해
  확인했다. 로봇 이동은 수행하지 않았다.
- 기판 외곽의 큰 직사각형과 네 모서리에 배치된 8개의 원형 체결 구멍이 선명해
  ArUco 없이도 기판 중심, 평면 회전(yaw), 원근 자세를 검출할 수 있는 형상이다.
- 좌우/상하 방향 혼동을 막으려면 비대칭 금색 패드 배치까지 방향 특징으로 함께
  사용한다. 외곽선만 사용하면 180도 방향 모호성이 생길 수 있다.
- 영상 좌표를 실제 기판 좌표와 FR5 Base 좌표로 변환하려면 체결 구멍 중심 간
  거리 또는 CAD상의 정확한 기준점 치수가 필요하다.
- 마커 없는 일반 RGB 프레임 진단용 `capture_color_frame.py`를 추가했다.

### 139×110 mm 빈 기판 좌표 dry-run 구현 및 실기 검증

- Unity 후보 크기 140×110.33742 mm와 사용자가 측정한 실물 139×110 mm를
  분리해 `vision_assembly/config/physical_board.json`에 기록했다.
- D435 RGB에서 검정 외곽 사각형을 찾고 139×110 mm 평면 PnP를 수행한 뒤
  `T_base_board=T_base_flange@T_flange_camera@T_camera_board`로 Base 좌표를
  계산하는 `detect_board_pose.py`를 추가했다. 로봇 이동 명령은 없다.
- 실제 1920×1080 영상 20프레임 검증 결과:
  Camera 중심 `[8.784, 3.998, 210.286] mm`, Base 중심
  `[297.307, -223.097, -7.146] mm`.
- Base 반복성 표준편차 `[0.040, 0.003, 0.066] mm`, median reprojection
  error 2.911 px로 측정됐다. 이는 같은 자세에서의 영상 반복성이며 실제 절대
  배치 정확도를 뜻하지 않는다.
- 디버그 영상에서 검출 외곽이 실물 기판 경계와 일치하는 것을 확인했다.
- 외곽 사각형만으로는 180도 방향 모호성이 있으므로 금색 패드 비대칭 방향
  판별 전까지 자동 배치에는 사용하지 않는다.

### 기판 정방향 확정 및 실시간 중심 오버레이

- 사용자가 빈 기판을 180도 회전한 현재 방향을 실제 조립의 정방향으로
  확정했다. 같은 화면 오른쪽의 완성 기판도 동일 방향임을 확인했다.
- 정방향은 빈 기판에서 큰 금색 패드 군집이 오른쪽 위에 보이는 방향으로
  정의하고 `physical_board.json`에 기록했다.
- 여러 기판이 동시에 보여도 색상 점유율이 가장 낮은 빈 기판을 선택하고,
  완성 기판은 `ASSEMBLED/OTHER`로 제외하는 `board_view` 노드를 추가했다.
- 출력 토픽 `/vision/board/image/compressed`에 빈 기판 외곽, 빨간 중심 십자,
  canonical 방향 판정, 중심 pixel 및 FR5 Base XYZ를 실시간 표시한다.
- 실제 화면에서 왼쪽 빈 기판 중심 십자와 외곽 검출이 맞고 오른쪽 완성 기판이
  제외되는 것을 확인했다. 노드는 로봇 이동 명령을 보내지 않는다.
- 기준 원본과 검증 오버레이 이미지를 `vision_assembly/data/reference/`에
  보관했다.

#### 기판 축·Yaw 및 조립 허용 상태 표시

- 중심 십자는 영상 수직·수평으로 고정하고 기판 회전과 분리했다.
- 기판 canonical +X를 파란 화살표, +Y를 노란 화살표로 표시하고 영상 기준
  `YAW(image)`를 추가했다.
- 정책을 `canonical=READY`, `rotated_180_corrected=READY`, `unknown=CHECK`로
  변경했다. 180도 회전은 좌표축을 canonical 방향으로 자동 정규화한다.
- 실기 화면에서 기판이 약 -3.74도 기울어진 상태를 canonical/READY로 판정하고,
  중심 십자는 고정된 채 축 화살표만 기판 외곽을 따라 회전하는 것을 확인했다.
- 산업 적용에서는 지그·키 구조로 역방향 유입을 예방하고, 평면 180도 회전은
  비전 판정 후 좌표 보정 또는 반송한다. 앞뒤 반전은 조립하지 않고 반송한다.

#### 기판 오검출 억제와 정보 패널 개선

- 어두운 선·그림자를 기판으로 오인하지 않도록 139:110 외곽 비율,
  rectangularity 0.78 이상, 모서리 원형 체결 구멍 최소 6개를 동시에 요구한다.
- 방향은 상단 두 구역 비교 대신 canonical 빈 기판의 금색 패드 4분면 분포
  `[0.053, 0.390, 0.300, 0.257]`와 0도/180도 가설을 비교한다.
- 현재 실기 화면은 holes=8, rect=0.98, dirErr=0.01로 READY를 통과했다.
- 저장 프레임을 180도 회전한 오프라인 시험에서
  `rotated_180_corrected`로 판정되고 canonical 축으로 정규화됨을 확인했다.
- 좌측 상단 텍스트를 반투명 패널 한 개로 정리하고 상태, orientation, yaw,
  center, geometry 진단값, Base XYZ를 줄맞춤해 표시한다.
- 중복 실행된 구버전 `board_view` 2개를 종료하고 최신 노드 하나만 실행했다.

#### Unity 소형 부품 슬롯 오버레이

- 6×3.5×2.5 mm 밝은 부품을 Unity의 `cap_small/right_white_brown` 후보로
  연결했다. Unity nominal은 약 6.80×3.84×3.02 mm다.
- Unity 중심 좌표를 실물 139×110 mm 축척으로 보정해 빈 기판 영상에 S1~S4
  슬롯을 투영했다. S1은 자주색 큰 십자, 나머지는 청록색으로 표시한다.
- 실기 화면에서 S1~S4가 빈 기판 왼쪽 세로 슬롯 열에 투영되는 것을 확인했다.
- 현재 S1 Base 후보는 `[149.1, -249.0, -4.3] mm`로 표시됐다. 이는 아직
  화면 확인용이며 로봇 이동 명령은 보내지 않았다.
- 실제 완성 기판에는 5개가 있지만 Unity 조립 파일에는 4개만 있어 다섯 번째
  슬롯은 좌표 미확정 상태를 유지한다.

#### 실물 배치로 소형 슬롯 5개 좌표 교정

- 사용자가 빈 기판의 실제 슬롯 5개에 밝은 소형 부품을 직접 배치했다.
- 정규화된 1390×1100 기판 영상에서 5개 밝은 부품 중심을 검출해 기판 중심
  기준 실물 좌표를 측정했다:
  P1 `[-41.88,-39.67]`, P2 `[-60.63,-17.60]`,
  P3 `[-60.41,-1.26]`, P4 `[-61.46,15.66]`,
  P5 `[-60.99,33.66] mm`.
- Unity의 기존 S1은 실제 슬롯이 아니므로 폐기했다. Unity S2~S4는 P2~P4와
  대체로 대응했고, 아래 외삽 B가 P5와 대응했다. P1은 위쪽 체결 구멍 앞의
  별도 X 위치다.
- 다섯 좌표를 `physical_board.json`의 `physical_slot_overrides`에 저장하고,
  화면 표시를 P1~P5로 교체했다.
- 실기 오버레이에서 P1~P5 십자가가 수동 배치한 부품 중심과 일치하는 것을
  확인했다. 당시 P1 Base 후보는 `[129.8,-253.7,-4.1] mm`였다.
- 아직 로봇 이동은 수행하지 않았으며, 실제 접근 전 다중 프레임 안정화와
  P1 상공 dry-run 검증이 필요하다.

#### P1 안정 좌표 저장

- `board_view`가 선택된 슬롯의 Base `PoseStamped`를
  `/vision/board/target_pose`로 발행하도록 추가했다.
- P1을 30프레임 수집해 Base XYZ `[74.082,-247.455,-4.141] mm`를 저장했다.
- 프레임 흔들림 median/max는 `0.083/0.226 mm`였다.
- 결과는 `vision_assembly/data/board_target_last.json`에 저장했다. 로봇 이동은
  수행하지 않았다.
# 2026-08-14 — 기판 인식 오버레이 가독성 개선

- 상단 보드 상태, 방향, yaw, 중심 픽셀, 선택 타겟, Base XYZ 및 Target XYZ를
  하나의 반투명 정보 패널 안에 정렬했다.
- 타겟 표시의 하드코딩된 `P1` 문구를 제거하고 실제 선택된 P1~P5 번호가
  표시되도록 수정했다. 타겟이 없으면 `NONE`으로 표시한다.
- 보드 +X/+Y 라벨을 각 화살표 끝 바깥쪽으로 이동하고 어두운 배경을 추가해
  축 선과 글자가 겹치지 않도록 개선했다.

## 2026-08-14 — P1 흰 종이 기준 슬롯 중심 1차 등록

- 사용자가 실제 부품 크기의 흰 종이를 P1 중심에 배치했다.
- 저장된 RQT 스크린샷에서 종이 외곽 중심과 기존 P1 십자 중심을 분리 측정했다.
- 기존 P1은 종이 중심 대비 기판 좌표로 약 `X -0.93 mm`, `Y -0.46 mm`에 있어
  P1을 `[-41.88,-39.67]`에서 `[-40.95,-39.21] mm`로 보정했다.
- 스크린샷 축소 영상 기반 1차 값이므로 원본 프레임 기반 최종 검증 전까지
  provisional로 취급한다.

### P2 흰 종이 기준 1차 등록

- P2에 세로로 배치한 흰 종이 외곽 중심과 기존 P2 십자 중심을 비교했다.
- 기존 P2 십자는 종이 중심 대비 기판 좌표로 약 `X -0.20 mm`, `Y +0.37 mm`에
  있어 P2를 `[-60.63,-17.60]`에서 `[-60.43,-17.97] mm`로 보정했다.
- P1과 동일하게 저장된 RQT 스크린샷 기반 provisional 값이다.

### P3 흰 종이 기준 1차 등록

- P3의 흰 종이 중심 대비 기존 십자는 기판 좌표로 약 `X -0.43 mm`,
  `Y +0.12 mm`에 있었다.
- P3를 `[-60.41,-1.26]`에서 `[-59.98,-1.38] mm`로 보정했다.
- 저장된 RQT 스크린샷 기반 provisional 값이다.

### P4 흰 종이 기준 1차 등록

- P4의 흰 종이 중심 대비 기존 십자는 기판 좌표로 약 `X -1.07 mm`,
  `Y +0.07 mm`에 있었다.
- P4를 `[-61.46,15.66]`에서 `[-60.39,15.59] mm`로 보정했다.
- 저장된 RQT 스크린샷 기반 provisional 값이다.

### P5 흰 종이 기준 1차 등록

- P5의 흰 종이 중심 대비 기존 십자는 기판 좌표로 약 `X -0.74 mm`,
  `Y +1.19 mm`에 있었다.
- P5를 `[-60.99,33.66]`에서 `[-60.25,32.47] mm`로 보정했다.
- 저장된 RQT 스크린샷 기반 provisional 값이다.

## 2026-08-14 — 전체 조립 부품 대략 배치 등록

- 완성 배치 상태의 D435 원본 1920×1080 프레임을
  `vision_assembly/data/all_parts_layout_raw.jpg`로 저장했다.
- 부품 이름과 개수를 GPU 1, HBM 8, Power Module 5, VRM 2, Inductor 4,
  SMD Capacitor 5로 통일했다.
- 기존 Unity 배치와 139×110 mm 실물 기판 축척을 대조해 기판 중심 기준 대략
  좌표를 `vision_assembly/config/assembly_layout_approx.json`에 저장했다.
- 기존 P1~P5는 `SMD Capacitor` 슬롯으로 이름을 변경했으며 흰 종이 보정값을
  유지했다.
- 최종 테이블 및 S22 설치 후 전체 좌표를 다시 정밀 등록해야 한다.

### 전체 부품 슬롯 오버레이 표시

- 기판 화면에 전체 25개 슬롯을 표시하도록 확장했다.
- 화면 혼잡을 줄이기 위해 `G=GPU`, `H=HBM`, `P=Power Module`, `V=VRM`,
  `I=Inductor`, `S=SMD Capacitor`와 번호 조합으로 표시한다.
- 기존 P1~P5의 P는 단순 Placement Point 의미였으며, 이제 S1~S5로 변경했다.
- 부품 종류별 색상을 분리하고 일반 마커/라벨 크기를 줄였으며 선택 목표만
  분홍색과 큰 마커로 강조한다.
- 기판 X/Y 화살표 선 굵기와 화살촉을 축소했다. 끝점 위치는 아래 사용자 피드백
  반영 항목에서 최종적으로 기판 외곽 108%로 변경했다.

#### 실물 VRM 위치 및 축 끝점 수정

- VRM은 S2 위쪽에 있는 흰색·검정 무늬 부품 2개임을 사용자 확인으로
  확정했다.
- 실물 영상 기준 VRM 대략 좌표를 `[-60.70,-45.00]`,
  `[-60.70,-33.60] mm`로 수정했다.
- X/Y 축은 사용자 요청에 따라 기판 경계의 108% 길이로 확장해 화살표 끝이
  기판 외곽보다 약간 바깥에 위치하도록 변경했다.
- 노란 Inductor 위의 노란 라벨이 보이지 않던 문제를 해결하기 위해 I1~I4
  마커와 글자 색상을 대비가 큰 밝은 파란색으로 변경했다.
- `+X` 축 라벨의 수직 여백을 12 px에서 24 px로 늘려 X축 선과 화살촉에
  겹치지 않도록 위치를 조정했다.
- 전체 부품 약어 라벨에 4 px 검정 외곽선을 먼저 그리고 2 px 밝은 색 본문을
  겹쳐 배경 대비를 높였다.
- 라벨 크기를 0.46에서 0.50으로 확대하고 오버레이 JPEG 품질을 88에서 95로
  올려 분홍·파랑·연두 계열 글자의 번짐을 줄였다.
- 초기 빈 기판 후보 선택용 `EMPTY`/`ASSEMBLED/OTHER` 문구는 완성 기판에서도
  잘못 표시되어 오버레이에서 제거했다. 향후 검사 단계의 실제 PASS/FAIL 상태로
  대체한다.

## 2026-08-14~17 — 초기 스마트폰 카메라 연결 검증(폐기)

- 개인 휴대폰과 S22로 초기 USB·Wi-Fi 영상 경로를 검증하고 `/camera2` ROS 토픽,
  OpenCV V4L2 변환 노드와 자동 복구 구조의 기반을 만들었다.
- 이때 사용한 앱·클라이언트·주소·포트·실행기는 2026-08-31에 모두 삭제했다.
  현재 운영 경로는 USB scrcpy뿐이며, 초기 연결 절차를 다시 사용하지 않는다.

## 2026-08-17 — D435 RGB-D 실행 확인

- D435 시리얼 `254622074096`을 USB 3.2 포트에서 인식했다.
- RGB `1920x1080x15`를 유지하고 Depth `848x480x15`, 컬러 정렬, 동기화 조건으로
  RGB-D 노드를 실행했다.
- 초기 `1280x720` Depth 실행에서 USB 재연결과 `Right MIPI error`가 한 차례
  발생해 노드를 종료하고 Depth 대역폭을 낮춰 재실행했다.
- 대용량 원본 영상에 대한 `ros2 topic hz`는 구독 도구의 처리 한계로 낮게
  측정됐지만, 센서 metadata 기준 컬러 `14.98 FPS`, Depth `14.99 FPS`를 확인했다.
- 로봇 이동 명령은 보내지 않았다.
- RQT에서 1920x1080 raw 영상을 직접 표시할 때 끊김이 발생했고, 컬러 compressed
  JPEG 품질 기본값 `95`에서 압축 발행률이 약 `7 FPS`로 저하되는 것을 확인했다.
  런타임 JPEG 품질을 `85`로 조정한 뒤 compressed 토픽이 `14.98 FPS`로 복구됐다.
  RGB 원본 해상도와 CameraInfo/캘리브레이션 값은 변경하지 않았다.

## 2026-08-20 — S22 최종 설치 각도 확정

- S22는 설치 공간 제약으로 작업면을 완전 수직으로 보지 않고 비스듬한 고정
  시점으로 운용한다.
- 화면 전체에 하나의 픽셀/mm 비율을 적용하지 않고, 조립·검사 정지선은 각
  위치에서 독립적으로 측정한다.
- 정밀 기판 pose나 로봇 좌표에 S22 영상을 사용할 때는 현재 고정 자세에서
  평면 homography를 별도로 캘리브레이션한다. 현재 정지선 검출은 영상 좌표
  기반이므로 이 보정 전에도 사용할 수 있다.

## 2026-08-20 — 구 USB 스마트폰 입력 프레임 지연 분석

- 같은 컨베이어 속도에서 Wi-Fi 연결은 정지 위치가 맞고 USB 연결만 한 박자 늦는
  현상을 확인해 관성이나 정지선 보정보다 USB 영상 큐를 우선 원인으로 판단했다.
- 기존 camera2 노드는 1920x1080 프레임을 타이머에서 읽고 JPEG 처리까지 하므로
  처리 지연 시 `/dev/video10`에 쌓인 과거 프레임을 순차 소비할 수 있었다.
- V4L2 버퍼 크기를 1로 요청하고, 별도 캡처 스레드가 입력을 계속 소비하면서 ROS
  타이머는 항상 최신 프레임 하나만 복사·발행하도록 변경했다. 중간 프레임은
  지연시키지 않고 폐기한다.
- Python 문법 검증을 통과했다. 다음 USB 실행부터 적용되며 실제 컨베이어 정지
  위치는 동일 속도 `0.10m/s`에서 재검증한다.
## 2026-08-21 - S22 수평 재설치 확인

- S22 Wi-Fi 영상 토픽 `/camera2/image_raw/compressed`가 정상 발행 중이다.
- 현재 영상 해상도는 1920×1080이며 측정 프레임 속도는 약 8~9Hz였다.
- 수평 재설치 후 기존 ROI가 맞지 않아 기판 검출이 0개였고, 현재 영상 기준
  ROI 재설정으로 기판 2개가 오프라인 검출되는 것을 확인했다.
- 검출 오버레이 토픽은 QoS가 best-effort이므로 일반 reliable 구독에서는 보이지
  않을 수 있다. RQT에서는 compressed 영상 토픽을 선택한다.

## 2026-08-21 - S22 프레임 저하 최적화

- 기존 S22 노드는 1920×1080 프레임마다 raw와 JPEG를 동시에 발행하고 JPEG
  품질 95를 사용해 CPU 사용량이 약 53%까지 올라갔다.
- 컨베이어가 사용하는 compressed 영상만 기본 발행하도록 변경했다.
- 기본값을 15 FPS, JPEG 품질 85로 설정하고 해상도 1920×1080은 유지한다.
- raw 영상이 필요한 경우 `PUBLISH_RAW=1`로 선택적으로 활성화한다.
- 화질 우선 설정으로 JPEG 품질 기본값은 95로 최종 복원했다. 프레임 부하는
  raw 동시 발행 제거와 15 FPS 제한으로 줄인다.

## 2026-08-21 — D435 부품 트레이 검출 게이트

- D435 컬러 영상과 `/camera/camera/aligned_depth_to_color/image_raw`를 이용해
  부품 트레이 외곽 검출을 추가했다.
- 밝은 대형 직사각형의 면적, 종횡비, 직사각형 충실도와 aligned depth 유효율을
  함께 검사한다. 현재 트레이 검증값은 bbox 약 `471,38,1099,993 px`, depth
  중앙값 약 `483 mm`, 유효 깊이율 약 `0.97`이었다.
- 트레이가 검출되지 않으면 6개 부품 영역을 그리지 않는다. JSON 상태 토픽의
  `tray_detected=false`와 화면의 `TRAY NOT DETECTED | ZONES HIDDEN`으로 확인한다.
- 트레이가 확인되면 검출 외곽에 맞춰 영역을 동적으로 맞추고, 각 영역의 aligned
  depth 중앙값과 카메라 좌표를 `/vision/tray/zones`로 발행한다.
- 깊이 프레임 지연으로 화면이 깜빡이지 않도록 3회 연속 유효 검출 후 활성화하며,
  영상에서 트레이 외곽 자체가 사라지면 즉시 비활성화한다.
- 변경 파일: `vision_assembly/scripts/view_tray_zones.py`,
  `vision_assembly/config/tray_zones.json`, `vision_assembly/README.md`.

## 2026-08-21 — D435 트레이 HBM·Power Module 영역 보정

- HBM을 트레이 우측 구역의 가장 왼쪽에 배치한 실제 상태를 반영해 HBM 영역의
  왼쪽 경계를 확장했다.
- HBM과 GPU 영역이 겹치지 않도록 GPU 오른쪽 경계는 소폭 안쪽으로 조정하고,
  두 영역 사이에 안전 여백을 남겼다.
- Power Module이 우측 상단 칸의 아래쪽 벽에 붙어 있는 상태를 포함하도록 해당
  영역의 하단 경계를 아래로 확장했다. HBM과의 경계에는 여백을 유지했다.

### GPU·HBM 실제 배치 기준 분할선 재조정

- 최신 화면에서 GPU가 오른쪽 벽까지 붙어 GPU 영역 밖으로 일부 보이고, HBM은
  그 오른쪽에 붙어 있는 배치임을 확인했다.
- GPU 오른쪽 경계를 실제 GPU 끝까지 확장하고 HBM 왼쪽 경계를 그보다 오른쪽에
  배치해 두 부품 사이에 명확한 분할 여백을 만들었다.

## 2026-08-21 — Power Module·HBM 수평 경계 재조정

- Power Module이 상단 우측 칸의 아래쪽 벽에, HBM이 하단 우측 칸의 위쪽 벽에
  놓인 현재 배치를 확인했다.
- Power Module 영역의 하단을 아래로 확장하고 HBM 영역의 상단을 함께 아래로
  이동해, 두 부품을 각각 포함하면서 영역끼리는 겹치지 않도록 조정했다.

- 사용자 확인에 따라 Power Module 하단을 HBM 방향으로 아주 소폭 추가 확장했다.
  HBM 상단 경계는 유지해 두 영역이 겹치지 않도록 했다.

## 2026-08-21 — D435 트레이 오버레이 CPU 최적화

- 트레이 오버레이 노드의 CPU 사용량이 약 `104%`로 측정되어 원본 compressed보다
  오버레이 영상의 프레임이 떨어지는 원인을 확인했다.
- 6개 영역의 깊이 마스크를 매번 전체 `1920×1080`으로 만들던 구조를 각 영역의
  bounding box 내부에서만 계산하도록 변경했다.
- 영역 깊이값은 2프레임마다 갱신하고 중간 프레임은 마지막 유효값을 재사용하도록
  해 표시용 오버레이의 처리 부담을 줄였다.
- 작은 부품 검출·로봇 좌표 계산은 오버레이 토픽이 아니라
  `/camera/camera/color/image_raw/compressed`와 aligned depth를 직접 사용한다.
- 전체 해상도 JPEG 재압축 부하를 줄이기 위해 화면용 오버레이는 입력 2프레임마다
  최신 프레임을 처리한다. 이는 원본 카메라 FPS나 depth 발행률을 제한하지 않는다.

## 2026-08-21 — D435 사용 스트림 최소화

- D435 실행 스크립트에서 실제 사용하는 컬러 compressed, aligned depth raw,
  CameraInfo를 기준으로 센서 구성을 정리했다.
- IR1/IR2, RGBD 합성 토픽, IMU, pointcloud, colorizer 및 사용하지 않는 depth
  필터를 명시적으로 끄고, color-depth sync와 depth-to-color alignment만 유지했다.
- 현재 Jazzy RealSense 드라이버는 image transport publisher 이름을
  `ros2 topic list`에 등록해 두므로 `compressedDepth`, `theora`, `zstd`, raw
  color 이름 자체는 남을 수 있다. 구독자가 없으면 해당 transport를 프로젝트
  입력으로 사용하지 않으며, compressed color 생성에 필요한 raw color source도
  구조상 유지한다.
- 실제 점검 중 `tray_zones`가 수정 전 코드로 raw color를 구독하고 있던 것을
  발견했다. 해당 프로세스를 종료하고 현재 코드로 재시작한 뒤 raw color
  subscription은 0, compressed color subscription은 1로 정리했다.
- 진단용 `ros2 topic hz` 프로세스가 남아 있던 것도 종료해 영상 처리에 불필요한
  추가 구독을 제거했다.
- 변경 파일: `calibration/run_d435_rgbd_stable.sh`,
  `calibration/config/d435_rgbd_minimal.yaml`,
  `vision_assembly/scripts/view_tray_zones.py`.

## 2026-08-21 — D435 트레이 오버레이 중복 실행 정리

- 영역이 흔들리는 현상 점검 결과 `view_tray_zones.py`가 2개 실행 중이었고,
  `/vision/tray/zones/image/compressed` 발행자도 2개였다.
- 기존 PID 26981, 28113을 종료한 뒤 트레이 노드를 1개만 재실행했다.
- 재확인 결과 실행 프로세스 1개, 오버레이 토픽 발행자 1개로 정상화됐다.

## 2026-08-21 — 팀원 트레이 등록·부품 검출 기능 선택 적용

- 원격 `fr5-robot-control-full` 브랜치에서 트레이 관련 파일만 선택적으로 가져왔다.
- 추가 파일: `tray_layout_candidate.json`, `part_specs_candidate.json`,
  `view_tray_sections.py`, `detect_tray_parts.py` 및 실행 스크립트·reference 이미지.
- 팀원 방식의 화면 등록은 고정 reference image와 SIFT/RANSAC homography를 사용하며,
  실제 실행에서 `TRACKING`, matches 45, inliers 42를 확인했다.
- 영역 polygon은 팀원 원본 대신 사용자 검토 영역값을 반영해 유지했다.
- 부품 검출 dry-run은 12초 동안 `TRACKING`, 원시 검출 22개, 안정 검출 13개를
  기록했다. 당시 신선한 로봇 상태가 없어 `base_transform_status`는
  `NO_FRESH_ROBOT_STATE`였으며 로봇 명령은 전혀 보내지 않았다.
- 기존 `tray_zones` 노드는 중복 처리를 막기 위해 종료하고, 새
  `tray_section_viewer`만 유지했다.
- 팀원 viewer의 자동 polygon inset 약 5px을 제거해 사용자님이 정한
  `tray_zones.json`과 동일한 영역 경계를 그대로 표시하도록 수정했다.
- 사용자 확인 후 영역을 벽 방향으로 넓히지 않고 축소하는 방향으로 재조정했다.
  VRM·Power Module의 상단 영역은 유지하고, 중앙 Inductor/SMD와 하단 GPU/HBM의
  시작선을 분리해 영역 겹침을 제거했다. GPU/HBM의 좌우·하단은 실제 칸막이와
  부품이 붙은 위치를 반영했다.
- GPU 오른쪽 선을 HBM 왼쪽 선에서 약 `0.007` normalized 간격만큼 안쪽으로
  이동해 두 선이 겹치지 않도록 했다. Inductor와 GPU의 왼쪽 선은 VRM 왼쪽 선과
  같은 위치로 확장했다. 수정 후 실제 화면에서 GPU/HBM 사이 간격과 좌측선 정렬을
  확인했다.

## 2026-08-21 — 트레이 자세 변경 대응 점검

- 부품 검출이 `fixed_view` 모드로 실행되면, 저장한 트레이 관측 자세의 픽셀
  좌표를 그대로 사용하므로 로봇(카메라) 자세 변경 뒤 박스가 실제 트레이 위치와
  어긋난다. 이 모드는 자동 Pick에 사용하지 않는다.
- 검출기를 SIFT/RANSAC 기반 `sift` 추적 모드로 재시작했다. 현재
  `TRACKING`, matches 23, inliers 13이며 로봇 정지 후 base 좌표 계산까지
  정상 상태(`VALID_COORDINATES_ONLY`)를 확인했다. 모든 동작은 dry-run이며
  로봇 이동 명령은 보내지 않았다.
- 영역 표시 전용 `tray_section_viewer`도 1개 실행 중이며,
  `/vision/tray/sections_image/compressed`를 발행한다. rqt에서 이 토픽을
  선택하면 트레이 추적 결과에 따라 각 부품 구역을 표시한다.
- GPU 두 개의 instance 번호가 화면의 미세한 Y 오차 때문에 좌우가 바뀌던 문제를
  수정했다. 이제 reference 화면 기준 왼쪽 GPU가 `GPU #1`, 오른쪽 GPU가
  `GPU #2`가 되도록 X 좌표 우선 정렬한다.
- GPU의 검정 표면이 로고·반사광으로 분절될 때 raw contour 외곽이 일부만 보이던
  표시 문제를 보완했다. 검출한 중심·방향은 유지하되, 표시 및 안정화 box는 사용자
  실측 크기 `57:27 mm` 비율로 재구성한다. 따라서 GPU가 180° 회전해도 전체
  부품 box의 비율이 동일하게 유지된다.
- 실시간 GPU 화면을 확인해, 깊이만으로 외곽을 확장하는 실험은 트레이 그림자·깊이
  노이즈까지 결합해 box가 과대해지는 것을 확인했다. 해당 변경은 즉시 되돌렸다.
  최종 검출은 `D435 높이 차이 + 어두운 GPU 표면`으로 후보를 제한하고, CAD 비율로
  box를 정규화하는 방식이다. 현재 두 GPU 모두 전체 외곽이 안정적으로 표시된다.
- GPU 흰 점은 현재 프레임에서 아직 특징점으로 확정되지 않았다. GPU 본체 검출과
  Pick 중심 계산에는 영향을 주지 않으며, 추후 방향이 반드시 필요한 공정에서
  별도 특징점/마커 검출로 보완한다.

## 2026-08-21 — GPU HSV/LAB + Depth 검출 및 180도 방향 판별

- GPU 검출을 `HSV/LAB 검정색 후보 → D435 상승 픽셀 검증 → Depth 기반 중심·각도
  재계산` 구조로 변경했다. 흰 트레이의 평평한 그림자는 Depth 상승 비율 검증에서
  탈락하며, 검정 GPU와 붙은 그림자는 최종 중심·각도 계산에 사용되지 않는다.
- GPU 박스 크기는 프레임별 contour 면적 대신 실측 `57 x 27 mm`, 카메라 내부
  파라미터와 깊이로 투영한다. 실제 영상에 맞춘 투영 보정계수 `1.07`을 적용해
  두 GPU 모두 약 `198.09 x 93.83 px`의 동일한 박스로 안정화했다.
- 모서리 흰 점은 3~4px로 매우 작고 흰 트레이 경계와 붙어 간헐적으로 오인될 수
  있어 방향 판정의 주 입력으로 사용하지 않는다. 진단 후보로만 유지한다.
- 대신 GPU 표면의 녹색 NVIDIA 로고를 HSV로 검출하고, GPU 중심에서 로고로 향하는
  벡터를 이용해 사각형 각도의 180도 모호성을 해결했다.
- 실시간 검증 결과 GPU #1은 방향각 `271.71 deg`, GPU #2는 `100.86 deg`로 약
  171도 반대 방향임을 구분했다. 두 대상 모두 `VALID_COORDINATES_ONLY` 상태로
  Base 좌표까지 계산되며, 이 검증 중 로봇 이동 명령은 전혀 전송하지 않았다.
- 변경 파일: `vision_assembly/scripts/detect_tray_parts.py`.

## 2026-08-21 — GPU 방향 검출과 일반 검출 분리

- 단일 프레임의 녹색 로고/흰 점 후보를 화면에 바로 표시해 점이 이곳저곳으로
  이동해 보이던 문제를 제거했다. 일반 검출은 GPU 박스와 중심만 계산·표시한다.
- GPU의 180도 방향이 실제로 필요한 단계에서만 `--resolve-gpu-orientation`을
  사용한다. 이 모드에서도 원시 후보는 표시하지 않고, 여러 프레임에서 안정화한
  방향점과 화살표만 표시한다.
- D435 RGB 입력 설정은 `1920x1080x15`를 유지한다. 검출 오버레이 토픽의 JPEG
  재압축 품질은 88에서 기본 95로 올렸으며 `--jpeg-quality`로 조정할 수 있다.
- GPU 일반 모드에서 단일 프레임의 울퉁불퉁한 분할 contour·중심·각도 표시도
  제거했다. 계산용 원시 분할은 내부에서만 사용하고, 화면에는 시간 안정화 후의
  실측 CAD 크기 사각형과 중심만 표시한다.
- GPU #1 접근을 반복할 때 만료된 과거 좌표를 재사용하지 않도록, 최신 검출 5개를
  고정한 뒤 중심 100 mm 위로 접근하는 통합 실행기
  `vision_assembly/run_gpu1_center_hover.sh`를 추가했다.

## 2026-08-26 — 구 S22 연결 재시도 안정화(폐기)

- S22의 DHCP 주소가 `192.168.11.7`에서 `.3`으로 변해 Wi-Fi 연결이 실패한 원인을
  확인했고, 이후 공유기/휴대폰 설정에서 `.7`로 고정한 것을 다시 반영했다.
- Wi-Fi 런처는 USB ADB가 함께 연결된 경우 S22의 실제 `wlan0` 주소를 자동 탐지해
  저장 주소가 오래됐더라도 현재 주소로 접속하도록 수정했다.
- 구 USB 경로는 반쯤 열린 세션에서 프로세스만 살아 있고 프레임이 없는 상태를
  복구하도록 매 재시도 전에 앱을 재시작한다. ROS 카메라 노드에도 시작 후 8초간
  프레임이 없거나 실행 중 5초간 정지하면 상위 런처가 자동 재연결할 수 있도록
  스트림 watchdog을 추가했다.
- 최종 재시험 도중 ADB가 `unauthorized`로 전환되어 휴대폰의 RSA 승인 재확인이
  필요한 상태다. 이는 코드나 IP 문제가 아니라 Android USB 디버깅 인증 상태다.
- Wi-Fi와 USB 모두 영상이 잠시 보인 뒤 종료된 직접 원인은 카메라 연결 실패가
  아니라 상위 컨베이어 런처의 단발성 `ros2 topic echo` 준비 검사 오판이었다.
  이 검사가 카메라를 종료해 ROI 노드가 시작되지 못했다. 단발성 DDS discovery
  검사 의존을 제거하고 카메라 런처가 살아 있으면 지속 구독자인 컨베이어 ROI를
  바로 시작하며, 이후 두 프로세스를 함께 감시하도록 수정했다.

## 2026-08-27 — S22 컨베이어 화면 전송 최적화

- `config/ksmc.env`가 S22를 1920×1080, 30 FPS, JPEG 95로 강제해 카메라 JPEG
  재압축과 full-HD ROI 재출력이 동시에 발생하는 것을 확인했다.
- 실제 ROS 측정값은 원본 약 17~20 FPS, ROI 주석 약 17~20 FPS였지만 프레임 간격이
  약 0.03~0.13초로 불규칙했고, full-HD/JPEG 90 영상을 rqt에서 다시 디코딩하면서
  체감 끊김이 커지는 구조였다.
- 검출 입력 해상도 1920×1080은 유지하고 카메라 발행을 15 FPS/JPEG 85로 변경했다.
  정지선 판정은 원본 해상도에서 수행하므로 검출 좌표와 정지선 위치는 바뀌지 않는다.
- 사람이 보는 ROI 주석 영상만 최대 1280 px/JPEG 78로 축소해 DDS 전송량과 rqt
  디코딩 부하를 줄였다.
- 당시 Wi-Fi 전용 실행기는 full-HD 입력을 유지하면서 15 FPS/JPEG 82를 명시했고,
  USB 기본값은 15 FPS/JPEG 85로 두었다. 두 구 실행기는 이후 폐기됐다.
- 당시 Wi-Fi 입력 또는 ROS 카메라 노드가 일시 종료될 경우 최대 5회까지 두
  프로세스를 함께 정리하고 재접속하도록 자동 복구 루프를 추가했다.
- 실제 Wi-Fi 시험에서 첫 연결은 `/dev/video10` 준비 타이밍으로 실패했지만 두 번째
  시도에서 `/camera2/image_raw/compressed`를 1920×1080, 15 FPS, JPEG 82로 정상
  발행했고, 시험 종료 후 관련 프로세스가 남지 않은 것을 확인했다.

## 2026-08-27 — S22 최신 프레임 발행 최적화(공용 코드로 이관)

- 당시 USB와 Wi-Fi의 공통 입력은 `1920×1080`, `20 FPS`, JPEG 품질 `85`로
  통일했다.
  작은 부품 검사와 녹화를 위한 원본 Full-HD 토픽은 그대로 유지한다.
- `/camera2/image_raw/compressed` 발행 QoS를 `BEST_EFFORT + KEEP_LAST(1)`로
  변경했다. 느린 뷰어나 네트워크가 과거 프레임을 쌓아 재생하지 않고 항상 최신
  프레임을 우선하므로 체감 지연과 순간적인 몰아 재생을 줄인다.
- 캡처 스레드가 새 배열로 프레임을 교체하는 구조를 이용해, 발행 때마다 발생하던
  Full-HD 프레임 전체 복사를 제거했다. 원본 화질에는 영향을 주지 않는다.
- 최신 프레임 교체와 QoS 최적화 코드는 현재 scrcpy용 ROS 발행기로 이관했고,
  구 USB·Wi-Fi 런처는 제거했다.
## 2026-08-27 — S22 고정형 좌표 카메라 역할 확장

- S22를 고정형 Hand-to-Eye 카메라로 사용할 수 있도록 해상도 독립 정규화
  기판 외곽 토픽을 추가했다. 카메라 거치·각도·줌이 바뀌면 평면
  Homography를 다시 계산해야 하며, S22는 전역 XY/회전 보정, D435는 근접 정밀
  보정과 높이 측정을 담당하는 하이브리드 역할로 유지한다.

## 2026-08-31 — S22 USB 고화질 overview와 망원 검사 촬영 분리

- 공식 scrcpy 4.1 카메라 입력을 추가해 S22 후면 메인 카메라를
  3840×2160·30 FPS·50 Mbps H.264로 수신한다. 캡처와 ROS JPEG 발행을 분리하고
  항상 최신 프레임만 유지해 느린 구독자가 과거 프레임을 누적시키지 않게 했다.

- 실시간/원격 확인은 1280×720 JPEG 88, 필요할 때만 활성화되는 분석 토픽은
  1920×1080 JPEG 92, 요청 캡처는 원본 4K 무손실 PNG로 역할을 분리했다.
- scrcpy main-camera zoom은 디지털 crop임을 확인했다. 정밀 검사는 overview를
  잠시 멈추고 Samsung Camera의 실제 3× 망원 렌즈를 선택해 기본 3.5×로 촬영한 뒤
  overview를 자동 복구한다.
- 유효 망원 사진은 4000×3000, physical focal length 약 7.0 mm, 35mm 환산 약
  69 mm인지 EXIF로 확인한다. 원본 JPEG와 upright 전체 PNG, 원근 보정 PCB ROI를
  각각 보존한다.

## 2026-08-31 — 구 스마트폰 앱 USB·Wi-Fi 연결 경로 완전 폐기

- S22와 초기 개인 휴대폰 테스트에 사용했던 구 앱 기반 카메라 연결은 화질과
  안정성 문제로 운영 경로에서 완전히 제거했다. USB·Wi-Fi 런처, 저장 IP/포트
  환경값, Linux 클라이언트 설치 소스와 프로젝트 참조를 삭제했다.
- 기존 폴더에 함께 있던 OpenCV V4L2→ROS 발행기는 scrcpy가 계속 사용하는 공용
  구성요소이므로 `camera2_scrcpy/camera2_ros_node.py`로 이전했다.
- v4l2loopback은 scrcpy의 `/dev/video10` 출력 sink로 필요하므로 유지하고 장치
  라벨과 부팅 설정 이름을 `S22-scrcpy-HQ`로 변경했다.
- 운영 명령은 `~/KSMC/run_s22_conveyor_hq.sh` 하나로 통일했다. S22의 구 앱
  패키지와 PC 클라이언트를 제거하고 부팅 설정도 scrcpy 이름으로 교체했다.
- 새 HQ 실행기를 18초간 무동작 실기동해 3840×2160 캡처 약 29.8 FPS, ROS 발행
  15 FPS와 정지선 ROI 시작을 확인했다. 종료 후 관련 프로세스는 남지 않았으며,
  로봇·컨베이어 이동 명령은 전송하지 않았다.

## 2026-08-31 — S22 AOI 수집 촬영 조건 고정

- 동일 위치 A/B 사진에서 Samsung Camera 플래시는 3D 프린트 표면 반사와 무해한
  적층 무늬를 강조해 검사 데이터에 불리했다. 자동 데이터 수집 촬영은 실제 망원
  렌즈 3.5×, 플래시 OFF로 고정했다.
- Android `Flashlight_brightness_level`을 1009와 1004로 바꿔 비교했으나 stock
  Camera의 사진 플래시에는 밝기 차이가 반영되지 않았다. 시험 후 휴대폰 설정은
  원래 최대값 1009로 복원했다.
- 실내등은 유지하되 차단할 수 없는 햇빛 변화는 `lighting_condition`으로 별도
  기록한다. 원본 4000×3000 JPEG와 1600×1266 보정 ROI를 모두 보존한다.
- 이번 변경 검증은 모의 이미지로 수행했으며 실제 촬영이나 컨베이어 구동은 하지
  않았다.

## 2026-08-31 — S22 overview 30 FPS 저지연 제어 경로

- 컨베이어 overview의 3840×2160@30 FPS·50 Mbps 입력은 정지 검출에는 불필요한
  디코딩·메모리 부하를 만들었다. overview만 1920×1080@30 FPS·20 Mbps로 변경하고,
  실제 검사는 기존 Samsung Camera 4000×3000 망원 촬영을 그대로 유지했다.
- 상시 제어 스트림을 960×540/JPEG 84/30 FPS로 변경했다. Full-HD JPEG 92 분석은
  별도 thread에서 구독자가 있을 때만 최대 5 FPS로 발행해 제어 인코딩과 분리했다.
- 독립 30 Hz 폴링을 새 프레임 condition wake 방식으로 교체했다. 무동작 실측에서
  원본 capture 30.0 FPS, 제어 28.9~29.8 FPS를 확인했다. 변경 전 제어 실측은
  21.6~22.2 FPS였다.
- 정지선 UI 구독 상태에서도 제어 29.2~29.8 FPS를 유지했다. Full-HD 분석 구독은
  5.0 FPS로 제한됐으며 순간 0.20초 초과 프레임은 하위 fail-safe가 폐기했다.
- 테스트 종료 시 launcher/running/paused 상태 파일이 모두 정리됐다. 실제 모터는
  구동하지 않았다.
## 2026-09-01 — S22 USB 3.x 새 케이블 재연결 검증

- 새 C-to-C 케이블로 S22(SM-S901N, `R5CT32WHE9V`)를 다시 연결하고 ADB
  authorized 및 MTP/ADB 인터페이스를 확인했다. 노트북 Thunderbolt 4 포트와
  케이블 정격보다 휴대폰 USB 인터페이스가 먼저 제한되어 실제 링크는
  SuperSpeed 5000M(5 Gbps)로 협상됐다.
- 정지선과 컨베이어 제어는 실행하지 않고 `camera2_scrcpy` 카메라만 기동했다.
  1920×1080@30 H.264 20 Mbps 입력, 제어용 960×540 JPEG 84 스트림으로 실측한
  내부 capture는 29.9~30.0 FPS, control publish는 29.4~29.6 FPS였다.
- `/camera2/image_stream/compressed`를 8초간 실제 구독한 평균은
  29.6~29.8 FPS였고 최대 프레임 간격은 약 0.051초였다. 연결 끊김은 없었다.
- 휴대폰 위치를 다시 고정한 뒤 기판 외곽과 조립/검사 정지선을 재보정해야 한다.
  이번 검증에서는 광학 검사 촬영, 로봇 및 컨베이어 이동 명령을 실행하지 않았다.

## 2026-09-01 — S22 최대 화질 실시간 프로필 시험

- 사용자의 요청에 따라 안정 프로필 대신 최대 화질 우선값을 적용했다. S22 main
  camera source는 3840×2160@30 H.264 50 Mbps, rqt용 live stream은
  1920×1080 JPEG 95, subscriber-isolated analysis는 3840×2160 JPEG 95 최대
  5 FPS로 설정했다.
- S22 실제 V4L2 입력은 3840×2160으로 확인됐고, rqt 구독이 연결된 상태에서도
  카메라 노드 내부 capture는 약 30.0 FPS, live publish는 29.4~29.8 FPS를
  유지했다. DDS Python 측정기 3개를 동시에 연결한 수신 통계는 처리 병목으로
  왜곡되어 최종 FPS 근거로 사용하지 않았다.
- overview service로 3840×2160 lossless PNG
  `s22_inspection_20260901_100214_554325145.png`를 저장해 실제 4K 프레임을
  확인했다. 현재 휴대폰 위치가 바뀌어 영상 방향과 조립/검사 정지선은 재보정
  전이며, 이 프로필의 컨베이어 정지 지연은 아직 검증하지 않았다.
- 프레임 저하나 정지 지연이 확인되면 검증된 1920×1080@30/20 Mbps source와
  960×540 JPEG 84 live profile로 되돌린다. 이번 시험에서 정지선 노드, 광학
  망원 촬영, 로봇 및 컨베이어 이동 명령은 실행하지 않았다.

## 2026-09-01 — S22 안정형 고화질 실시간 프로필 확정

- 4K source/1080p JPEG95 live 화면은 카메라 노드 발행이 약 30 FPS여도 rqt에서
  디코딩 큐가 쌓이며 사용자가 명확한 끊김과 지연을 확인했다. 따라서 실시간
  프로필을 1920×1080@30 H.264 30 Mbps source, 1280×720 JPEG90 live,
  1920×1080 JPEG95 analysis 최대 5 FPS로 조정했다.
- rqt가 live 토픽을 구독한 상태에서 별도 `ros2 topic hz` 구독을 추가해도 평균
  29.3~29.75 FPS를 유지했고 최대 프레임 간격은 0.044초였다. 기존 안정값
  960×540/JPEG84보다 화질을 높이면서 지연 누적은 발생하지 않았다.
- 정밀 AOI는 실시간 스트림과 별개인 Samsung Camera 4000×3000 망원 촬영을
  계속 사용하므로 검사 원본 화질은 낮아지지 않는다. 휴대폰 위치와 정지선은
  아직 재보정 전이며 실제 컨베이어 정지 시험도 남아 있다.
- 이번 조정에서는 정지선 노드, 광학 망원 촬영, 로봇 및 컨베이어 이동 명령을
  실행하지 않았다.

## 2026-09-01 — S22 망원 검사 배율 3.0/3.5/4.0 비교

- 같은 휴대폰·기판 위치와 플래시 OFF 조건에서 3.0x, 3.5x, 4.0x 사진을
  연속 촬영했다. 세 원본 모두 4000×3000, 실제 초점거리 7.0 mm,
  35 mm 환산 69 mm로 확인되어 S22의 물리 3x 망원렌즈를 사용했다.
- 현재 삼성 카메라 UI에서 3x 버튼을 기준으로 1080 px 화면의 왼쪽 33 px
  드래그가 화면 표시 `4.0x`가 되는 것을 직접 확인했다. 30~31 px에서는
  `3.9x`였으므로 검사 스크립트의 4.0x 제스처를 33 px 상당으로 보정했다.
- 기판이 원본에서 차지한 면적 비율은 3.0x 0.0735, 3.5x 0.1037,
  4.0x 0.1397이었다. 동일 1600×1266 기판 ROI의 중앙 부품 영역 선명도는
  Laplacian 분산 기준 113.11, 116.39, 97.76이었다. Tenengrad도 각각
  8503.36, 8545.81, 7270.75로 같은 경향이었다.
- 현재 위치에서는 3.5x가 기판 확대와 미세 경계 선명도의 균형이 가장 좋아 검사
  촬영 기본값으로 확정했다. 컨베이어 overview는 메인 카메라 1.5x를 사용한다.
  4.0x는 기판을 더 크게 담지만 디지털 확대 영향으로 정규화 후 세부 선명도가
  약 14~15% 낮았다. 최초 `s22_tele_4x_20260901_104613.jpg`는 제스처가
  적용되지 않아 실제 3x였으므로 비교 근거에서 제외했다.
- 촬영과 영상 분석만 수행했으며 로봇 및 컨베이어 실제 이동 명령은 실행하지
  않았다. 낮 시간대 조명 변화와 실제 불량 판별 성능은 별도로 검증해야 한다.

## 2026-09-02 — S22 수동 UI 촬영과 신규 JPEG 일괄 전송

- 학습 데이터 수집용으로 S22 화면을 일반 scrcpy 조작창에 띄워 사용자가 초점과
  셔터를 직접 누르는 세션 실행기를 추가했다. 실시간 conveyor camera-source
  scrcpy가 관리형으로 실행 중이면 pause 파일 계약으로 렌즈를 해제하고, 수동
  촬영이 끝나면 기존 overview를 자동 복구한다.
- 세션 전·후 `/sdcard/DCIM/Camera` 목록 차이를 비교해 새 JPEG만 USB ADB pull하며
  전송 중 JPEG 재압축은 하지 않는다. 실제 망원렌즈 사용 여부는 EXIF의 35mm 환산
  초점거리 60mm 이상으로 검증하고, 원본은 runtime 세션 폴더에 보존한다.
- 기존 실측 최적값인 3.5배 망원 프레이밍과 플래시 OFF를 자동 preset한다. 실제
  S22 촬영·전송과 overview 복귀는 아직 검증하지 않았고 shell 문법/도움말만
  확인했다. 로봇·컨베이어 실제 명령은 보내지 않았다.

## 2026-09-02 — 수동 UI 촬영 실측 및 사진 복구

- 첫 UI 세션에서 창을 닫자 scrcpy가 non-zero 상태를 반환해 후속 ADB pull이
  생략됐지만 사진은 휴대폰 DCIM에 정상 저장돼 있었다. 실행기를 수정해 앞으로는
  창 종료 상태가 비정상이어도 새 JPEG를 검색하고 가져오도록 했다.
- 신규 사진 14장은 모두 USB ADB로 원본 전송했으며 `4000×3000`, 초점거리
  `7.0mm`, 35mm 환산 `69mm`였다. EXIF flash fired는 5장, 미발광은 9장이었다.
  원본과 ROI는 `runtime/inspection/manual_seg_recovery_20260902_1050`에 보존했다.
- 수동 촬영 동안 관리형 overview가 pause된 뒤 `10:53:35`에
  `1920×1080@30`, 1.5배 camera-source 스트림과 ROS camera2 node로 정상
  복구된 것을 프로세스와 상태 파일로 확인했다. 로봇·컨베이어 이동 명령은
  보내지 않았다.

## 2026-09-02 — 수동 촬영 완료 Enter 제어 및 재촬영

- 데스크톱에서 scrcpy 창을 닫아도 viewer 프로세스가 남아 import가 대기하는
  경우를 확인했다. 수동 촬영 실행 터미널에서 Enter를 누르면 viewer만 종료하고
  신규 DCIM 사진 전송을 시작하도록 완료 제어를 추가했다. 창 자체가 정상 종료된
  경우도 그대로 지원한다.
- 올바른 기판 위치 재촬영 12장은 모두 USB 원본 전송했고 4000×3000,
  7.0mm/69mm-equivalent였다. EXIF 기준 flash 미발광 6장, 발광 6장이다.
  촬영·전송만 수행했으며 로봇·컨베이어 명령은 보내지 않았다.
## 2026-09-02 — S22 현재 화면 전체 AOI 촬영 연결

- `run_s22_live_hybrid_inspection.sh`에서 managed S22 overview를 안전하게
  pause하고 Samsung Camera의 flash off/3.5x 망원 정지 사진을 촬영한 뒤
  overview를 복구하도록 기존 optical capture 경로를 전체 25-slot 검사와
  연결했다.
- 실측 원본 `4000×3000`, focal 7.0mm, 35mm equivalent 69mm, ROI
  rectangularity `0.907`을 확인했다. 새 ROI target이 생성되지 않으면 이전
  사진을 검사하지 않고 종료한다.
- 카메라 전송 해상도·비트레이트·연결 방식 자체는 변경하지 않았다. 로봇과
  컨베이어 이동 명령은 수행하지 않았다.

## 2026-09-04 — 기존 D435 트레이 RGB-D 상태 재사용

- 팀원이 실행한 D435와 `/tray_part_detector`를 종료하거나 재실행하지 않았다. 새 50 mm 상공 실행기는 카메라 원본을 중복 구독해 처리하는 대신 현재 검출기가 발행하는 `/vision/tray/unity_state`와 `/vision/tray/registration`의 작은 JSON 상태를 사용한다. 카메라 해상도·노출·화질·정합 설정은 변경하지 않았다.
- ROS 그래프에서 검출기는 `/camera/camera/color/image_raw/compressed`, `/camera/camera/color/camera_info`, `/camera/camera/aligned_depth_to_color/image_raw`를 구독 중이고, 출력 상태는 `TRACKING`, `at_trayhome=true`, `VALID_COORDINATES_ONLY`로 계속 갱신됨을 확인했다. 현재 상태에는 aligned Depth 기반 Camera XYZ와 Hand-Eye Base XYZ가 포함된다.
- 다른 컴퓨터에서 대용량 raw RGB/aligned-depth를 뒤늦게 직접 구독했을 때 이미지 패킷 유실로 완전한 프레임 저장은 실패했지만, 카메라 PC에서 처리된 소형 상태 토픽은 안정적으로 수신됐다. 따라서 실제 실행 파일은 D435가 연결된 로봇 PC에서 현재 검출기와 함께 사용하고, `run_d435_rgbd_stable.sh`를 중복 실행하지 않는다.
- 상태 토픽의 관측 지연은 최대 2.645초였고 live freshness 제한을 3.5초로 설정했다. 목표 고정 후에는 15초 안에만 상공 경로를 사용할 수 있다. 다섯 비-SMD 종류의 5프레임 live 수집은 모두 통과했다.
- 이번 작업에서 D435 시작/종료/파라미터 변경, 로봇·그리퍼·컨베이어 실제 명령은 없었다. 원격 디버그 JPEG 자체는 전송 손실로 신규 저장하지 못했으며, 물리 50 mm 간격과 절대 Hand-Eye 정확도는 별도 실제 이동 검증이 남아 있다.
## 2026-09-10 Stop-line preview scheduling

Moved stop-line dashboard rendering/encoding off the control image callback to
a single bounded worker. USB acquisition and image timestamps are unchanged.
See docs/logs/conveyor.md asynchronous-stop-overlay entry for measured frame
ages, tests and deployment limitations. No camera restart or real motion occurred.

## 2026-09-11 — ROS-TCP camera fan-out and latest-frame delivery

The local ROS graph showed `/camera2/image_stream/compressed` publishing one
BEST_EFFORT/volatile stream at about 29.3–29.9 FPS and roughly 2.2 MB/s, while
the ROS-TCP graph had no active S22 stream subscriber. `/camera3/image_raw/compressed`
had a subscriber, but the endpoint implementation stored one global outgoing
queue and one subscriber node per topic. Consequently, a second Unity client
could replace the first client's queue and receive no camera frames.

The ROS-TCP endpoint now maintains an independent bounded queue for each TCP
client, broadcasts a topic to all clients that requested it, keeps one ROS
subscriber per topic, and removes a dynamic subscriber only after its last
client disconnects. Camera subscriptions use explicit KEEP_LAST depth 1,
BEST_EFFORT, volatile QoS. A keyed camera entry replaces an older pending
JPEG, preventing a slow Unity socket from accumulating stale frames or
blocking ROS callbacks. Unity-side protocol payloads and the supported camera
topic names remain unchanged.

Static checks passed with `python3 -m py_compile` for the modified endpoint
modules. The queue behavior was exercised with a bounded latest-entry test;
no Unity client playback was performed. A brief local bind probe used during
diagnosis was terminated immediately and the endpoint is not left running on
this laptop; the team-managed endpoint remains the deployment owner. No robot
or conveyor motion command was issued. All team computers still need
ROS_DOMAIN_ID 5 and network reachability to the endpoint's TCP port 10000; the
endpoint must be running on the configured endpoint computer, and Unity should
subscribe to `/camera2/image_stream/compressed` for S22 and
`/camera3/image_raw/compressed` for GoPro.
