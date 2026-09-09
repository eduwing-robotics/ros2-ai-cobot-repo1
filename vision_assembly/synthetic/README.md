# PCB 3D Synthetic OBB Dataset (Blender reconstruction deprecated)

> 주의: Blender FBX/OBJ 재구성은 Unity와 Bounds 중심·크기는 맞출 수 있지만 내부
> 메시 축과 지그 핀 위치가 달라 최종 학습 데이터 생성에 사용하지 않는다. 현재
> 기준은 Unity 씬 직접 렌더 방식이며, 이 디렉터리의 Blender 생성기는 실험용으로만
> 남겨 둔다.

Unity의 실제 PCB/부품 OBJ 모델과 현재 `PcbPickCoordinates.csv`를 Blender에서 읽어 `board_inspection_obb`용
합성 이미지와 YOLO-OBB 라벨을 자동 생성한다. Unity 원본 프로젝트는 수정하지 않는다.

대상 클래스:

- `gpu`, `hbm`, `power_module`, `vrm`, `inductor`, `smd_capacitor`

정상 배치는 Unity의 현재 완성 씬 export를 그대로 사용한다. 정상 조립 상태 외에 부품 누락·위치 오류·방향 오류와 카메라/조명 변화를 함께 생성한다.
누락은 YOLO의 별도 클래스가 아니라, 기대 슬롯과 검출 결과를 비교하는 검사 규칙에서 판정한다.

PCB는 항상 실제 Unity의 `Cube.001.fbx` 지그에 결합된 상태로 렌더링한다. 지그는
컨베이어 운반·기판 고정·완성품 손잡이 파지를 위한 영구 구조물이며 부품 OBB 클래스에는
포함하지 않는다. 따라서 정상/불량 모든 이미지에 지그가 존재하지만 부품 라벨로 생성되지는 않는다.
지그 4핀 패턴 중심과 기판 안쪽 4개 구멍 패턴 중심을 정렬한 뒤, Unity에서 실제로
확인한 최종 미세 조정값 `X +0.31985 mm`, `Z +0.08084 mm`를 지그에 적용한다.
Blender FBX 축 차이는 별도로 보정하며 손잡이는 현재 저장된 Unity 씬과 동일한 board `-Z` 쪽에 둔다.
최종 지그 위치는 Blender의 추정값이 아니라 Unity에서 직접 추출한
`config/unity_current_exact.json`의 실제 Renderer Bounds 중심과 크기를 기준으로 검증한다.

## 미리보기

```bash
cd ~/KSMC
~/KSMC/vision_assembly/synthetic/run_generate_pcb_synthetic.sh \
  --assets-dir "$HOME/My project/Assets/반도체 기판 모델링(Unity)/ASt" \
  --output-dir ~/KSMC/vision_assembly/synthetic/output/preview \
  --count 8 --seed 20260824
```

`output/preview/images/000000.png`와 대응하는 `labels`, `metadata`를 먼저 확인한다.

OBB 라벨은 아래처럼 이미지 위에 그려서 검토할 수 있다.

```bash
python3 ~/KSMC/vision_assembly/synthetic/scripts/preview_yolo_obb.py \
  --image ~/KSMC/vision_assembly/synthetic/output/preview/images/000000.png \
  --label ~/KSMC/vision_assembly/synthetic/output/preview/labels/000000.txt \
  --output ~/KSMC/vision_assembly/synthetic/output/preview/000000_obb.png
```

## 학습용 생성

```bash
~/KSMC/vision_assembly/synthetic/run_generate_pcb_synthetic.sh \
  --assets-dir "$HOME/My project/Assets/반도체 기판 모델링(Unity)/ASt" \
  --output-dir ~/KSMC/vision_assembly/synthetic/output/board_inspection_v1 \
  --count 500 --seed 20260824
```

합성 데이터는 `board_inspection_obb`의 사전학습용이다. D435 부품 트레이용
`tray_pick_obb`와 섞지 않고, S22 실제 이미지로 반드시 fine-tuning한다. 크랙 검사는
3D 합성만으로 충분하지 않으므로 D435 근접 실제 이미지가 필요하다.

## Unity-native 학습 결과

검증된 Unity Scene에서 생성한 300장 데이터는 아래 명령으로 학습한다.

```bash
~/KSMC/vision_assembly/synthetic/run_train_pcb_obb.sh \
  --epochs 100 --imgsz 960 --batch 8 --device 0
```

현재 합성 사전학습 가중치는 `vision_assembly/models/pcb_obb_unity_pretrain.pt`이다.
이는 실제 S22 영상 fine-tuning 전 단계이며 raw 검출 개수를 곧바로 PASS/FAIL로
사용하지 않는다. 최종 검사는 기판 기준 예상 슬롯과 OBB를 1:1 매칭한다.
