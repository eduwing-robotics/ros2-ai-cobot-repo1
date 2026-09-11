# S22 GPU/HBM white-leg inspection

## Locked hybrid AOI architecture

The canonical inspection contract is
[`../config/inspection_fusion_contract.json`](../config/inspection_fusion_contract.json).
It is independent of the teammate's D435-trained segmentation model and keeps
the following S22 pipeline fixed even when an individual model is replaced or
temporarily performs poorly:

1. capture-quality gate and fixed board perspective registration;
2. per-slot component presence, center, and angle from an S22-trained
   segmentation or OBB provider, with slot-constrained geometry as a candidate
   fallback;
3. independent orientation evidence, especially the GPU/HBM white corner dot;
4. explicit high-resolution white-pin checks plus slot-level PatchCore or
   FR-PatchCore for appearance anomalies;
5. optional strict-normal whole-board PatchCore screening;
6. fail-safe fusion of `PASS`, `FAIL`, and `UNKNOWN` evidence.

An unverified or low-confidence model is `ADVISORY_ONLY`: it can still produce
heatmaps and evidence, but it cannot make a board pass or fail. `PASS` requires
every mandatory, calibrated branch to pass. Missing or weak evidence becomes
`UNKNOWN`, which means automatic recapture and, after the retry limit,
`NG_UNCERTAIN`/line hold rather than an operator-approved pass. FR-PatchCore is
restricted to appearance inspection; its registration must never hide a
slot-relative position or orientation defect.

The contract is currently a locked design target, not a claim that every stage
has already been wired into the runtime fusion node.

The independent S22 component-provider preparation and commands are documented
in [`../segmentation/README.md`](../segmentation/README.md).

This stage runs on the perspective-rectified 3.5x S22 board image. It compares
the visible left and right white-leg rows of the GPU and eight HBM packages
with a verified normal board captured at the final inspection stop.

The PCB-plane homography cannot reconstruct a component sidewall hidden by
parallax. Such a side is reported as `RECHECK` and listed under
`d435_recheck`; it is never guessed as `PASS`.

## One-time golden reference

Place a verified normal board at the final inspection stop, create the
rectified ROI, and save it as the local golden image:

```bash
~/KSMC/vision_assembly/run_package_leg_inspection.sh \
  --set-reference ~/KSMC/runtime/inspection/s22_inspection_roi_latest.png
```

Repeat this calibration after moving the S22, changing optical zoom/focus, or
changing the final conveyor stop position.

## Inspect the latest capture

```bash
~/KSMC/vision_assembly/run_package_leg_inspection.sh
```

Use `--image /absolute/path/to/rectified.png` to inspect another capture.
Results are written under `runtime/inspection/package_legs/`:

- `package_leg_inspection_latest.png`: operator/debug overlay
- `package_leg_inspection_latest.json`: machine-readable result and D435 list

Status meanings:

- `PASS`: all S22-visible leg rows match the golden reference.
- `RECHECK`: at least one row is hidden or uncertain and needs a D435 view.
- `FAIL`: an expected visible leg signal is missing.

Pass `--strict-exit` only in automation: exit code `2` means `RECHECK`, and
exit code `3` means `FAIL`.

## Automatic inspection at the conveyor stop

Use the combined launcher instead of the normal S22 conveyor launcher:

```bash
~/KSMC/run_s22_conveyor_auto_inspection.sh
```

It starts the S22 HQ overview, both conveyor stop lines, and the inspection
trigger. It does not move the belt. In another terminal, send an assembled PCB
to the inspection station:

```bash
~/KSMC/run_conveyor_to_inspection.sh
```

When `/vision/conveyor/inspection/stop_trigger` becomes true, the flow is:

1. wait 0.35 seconds for the stop command to settle;
2. pause the overview and take one true 3.5x optical S22 photo;
3. extract and rectify the PCB ROI;
4. run the full 25-component board inspection;
5. restore the overview and wait for the next upstream PCB.

The same parked PCB cannot retrigger the capture. The node rearms only after a
fresh board is observed at least 20 px upstream of the inspection line.

Latest automatic results:

- `runtime/inspection/auto_inspection_latest.json`
- `runtime/inspection/full_board/full_board_inspection_latest.png`
- `runtime/inspection/full_board/full_board_inspection_latest.json`

ROS status topics:

- `/vision/inspection/auto/status`
- `/vision/inspection/auto/armed`
- `/vision/inspection/auto/running`
- `/vision/inspection/auto/completed`
- `/vision/inspection/auto/result`
- `/vision/inspection/auto/report_path`

## Capture-only AOI dataset collection

Use this mode while building a reviewed inspection dataset. It uses the same
inspection stop trigger and S22 optical capture, but deliberately does not run
the legacy OpenCV defect verdict:

```bash
~/KSMC/run_s22_conveyor_dataset_collection.sh \
  --split known_defect_unverified \
  --lighting evening_indoor \
  --board-state known_defect \
  --known-defects missing_smd \
  --once
```

Move the board from a second terminal:

```bash
~/KSMC/run_conveyor_to_inspection.sh
```

The trigger waits 0.35 seconds after the stop to avoid motion blur, takes one
3.5x telephoto photo with flash off, extracts the rectified PCB ROI, and saves
the complete sample below
`runtime/datasets/s22_aoi/<split>/<lighting>/<date>/`. Raw JPEG, ROI PNG, full
upright image, ROI metadata, debug image, per-capture manifest, and `index.jsonl`
are retained together.

Every new sample is `UNVERIFIED`, has `normal_training_allowed=false`, and must
be reviewed before it can enter normal-only anomaly-detection training. The
`known_defect` annotation records operator knowledge such as `missing_smd`; it
is not an automated inspection result. Use separate lighting labels such as
`evening_indoor` and `daylight_noon` instead of mixing uncontrolled sunlight
conditions.

## Component PatchCore candidate

The whole-board baseline loses too much detail when the complete PCB is
resized. Build normalized, high-resolution crops for GPU, HBM, Power Module,
VRM, Inductor, and SMD Capacitor instead:

```bash
~/KSMC/vision_assembly/run_prepare_smd_normal_dataset.sh
~/KSMC/vision_assembly/run_build_component_patchcore_dataset.sh \
  --source ~/KSMC/vision_assembly/inspection/datasets/pcb_smd_normal_v3 \
  --output ~/KSMC/vision_assembly/inspection/datasets/pcb_components_smd_v3 \
  --include-smd
~/KSMC/vision_assembly/run_train_component_patchcore.sh \
  --component all \
  --dataset ~/KSMC/vision_assembly/inspection/datasets/pcb_components_smd_v3 \
  --output ~/KSMC/runtime/inspection/patchcore/pcb_components_smd_v3
~/KSMC/vision_assembly/run_predict_component_patchcore.sh
```

PatchCore 실행기는 `--accelerator auto|cpu|gpu`를 지원한다. `auto`는 CUDA가
있으면 GPU를 사용하고, 개발용 CPU-only 환경에서는 같은 checkpoint를 CPU로
실행한다. 이 옵션은 추론 장치만 선택하며 `ADVISORY_ONLY` 권한과 fail-safe
융합은 그대로 유지한다.

배포 전 전체 준비 상태는 다음 읽기 전용 게이트로 확인한다.

```bash
python3 ~/KSMC/vision_assembly/hybrid_inspection/model_completion_gate.py \
  --report ~/KSMC/runtime/inspection/hybrid_fixed_slot/hybrid_report_latest.json
```

게이트가 모든 필수 모델과 독립 검증을 확인하기 전까지는 최종 결과를
`UNKNOWN`으로 유지한다.

The current SMD-present v3 dataset contains 975 reviewed-normal training crops
from 53 board images (39 train and 14 held out). The crops from mixed-defect boards are stored under
`unverified/mixed_defect`; they are never treated as slot-level defect ground
truth because the original captures did not record which slot was defective.

Latest outputs:

- `runtime/inspection/patchcore/component_live_v3/component_patchcore_latest.png`
- `runtime/inspection/patchcore/component_live_v3/component_patchcore_latest.json`

The original v1 models and the current v3 models are `UNVERIFIED_SCORE_ONLY`.
The default predictor uses `pcb_components_smd_v3` and evaluates all 25 slots.
Do not connect these scores to conveyor PASS/FAIL until controlled, slot-labeled
defect captures establish per-type thresholds. The legacy mixed-defect metrics
are exploratory because their bad component and slot were not recorded.

Capture the board currently stopped at the inspection position and immediately
run the whole-board v4 model followed by all six component v3 models with one
command:

```bash
~/KSMC/run_s22_whole_board_inspection.sh
```

This command requires the authorized S22 USB connection. It forces a fresh
3.5x optical still, runs whole-board v4 only by default, and rejects stale
ROI/report reuse. Add `--skip-capture` only when intentionally rechecking the
already saved latest ROI. The experimental component models remain available
with `--with-components` but are not part of the default inspection.

Whole-board v4 outputs are linked at:

- `runtime/inspection/patchcore/whole_live_v4/whole_patchcore_latest.png`
- `runtime/inspection/patchcore/whole_live_v4/whole_patchcore_latest.json`

The provisional fixed triage in `config/whole_board_patchcore_v4.json` is:
`NORMAL_CANDIDATE <= 0.40`, `RECHECK` between 0.40 and 0.55, and
`ANOMALY_CANDIDATE >= 0.55`. Pixel heat below 0.35 is hidden to suppress normal
texture noise. These values separate the current held-out normal and legacy
mixed-defect sets, but remain provisional until controlled, defect-specific
captures validate them.

`component_patchcore_latest.png` is a three-panel visualization containing the
aligned source, the 25-slot relative anomaly heatmap, and its overlay. Separate
heatmap, overlay, and slot-score images are also linked beside it. Heatmap colors
are normalized per component model within one run and are not calibrated defect
probabilities. Only the physical component bodies are colored; the 22% training
context margins are intentionally removed from the board-level visualization.
