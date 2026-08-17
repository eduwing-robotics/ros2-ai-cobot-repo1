# Vision Assembly

반도체 패키지 모형의 CAD/Unity 배치, 부품 recipe, 기판 인식 및 FR5 조립
기능을 단계적으로 모으는 디렉터리다.

## 현재 산출물

- `tools/extract_unity_board_layout.py`: Unity prefab과 OBJ에서 기판 중심 기준
  부품 중심·방향·크기 후보를 추출한다.
- `config/board_layout_from_unity.json`: 전체 메타데이터와 안전 경고 포함.
- `config/board_layout_from_unity.csv`: 슬롯 좌표 검토용 표.
- `config/board_layout_from_unity.svg`: 평면 배치 검토 및 발표용 그림.

## 다시 생성

```bash
python3 ~/KSMC/vision_assembly/tools/extract_unity_board_layout.py \
  --source /home/hc/Downloads/Board_obj
```

현재 전달 모델은 로봇 조립 대상 24개만 포함한다. 프로젝트 요구사항의
`right_white_brown` 5개 중 1개가 누락되어 있으며 JSON의
`unresolved_required_parts`에 좌표 미확정 상태로 기록된다.

이 레이아웃은 CAD-derived candidate다. 실제 출력물 크기, 기판 frame 방향,
부품 높이를 검증하기 전에는 FR5 실행 좌표로 사용하지 않는다. 배치 Z는 OBJ
bounds만 믿지 않고 검출된 기판 평면, aligned depth, 실측 recipe 높이로 만든다.
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

전달된 Unity 모델에는 실제 요구 수량 5개 중 4개만 있었으나, 실물 슬롯에
부품 5개를 수동 배치한 D435 영상에서 중심을 측정해 `physical_board.json`의
실물 override 레시피로 교체했다. 정밀 자동 배치 전 TCP 상공 검증은 별도로 한다.
