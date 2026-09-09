# PCB anomaly dataset v1

S22 3.5x optical captures from 2026-08-31, cropped and perspective-normalized to
the inspection-board ROI (1600x1266).

Dataset layout follows the common PatchCore/MVTec convention:

- `train/good`: 16 normal images used to build the normal feature memory bank.
- `test/good`: 4 held-out normal images used to tune the anomaly threshold.
- `test/mixed_defect`: 13 known-defective images used only for evaluation.

The defective captures intentionally mix missing parts, orientation errors, and
missing/abnormal white pins. Their exact per-image defect type was not recorded
at capture time, so they must not be used for defect-type classification until
`manifest.csv` is reviewed and given detailed labels. They are valid as generic
`abnormal` samples for anomaly-detection evaluation.

The source captures remain under `runtime/inspection`; this dataset contains
copies so the originals are preserved.

Run the first GPU baseline from the workspace root:

```bash
~/KSMC/vision_assembly/run_train_pcb_patchcore.sh
```

The baseline resizes the board ROI to 640x512. It is intended to prove the
normal-vs-abnormal workflow and detect relatively large assembly changes. Tiny
GPU/HBM pin defects require a later component-ROI model at higher effective
resolution.

First measured baseline (RTX 5070 Ti, 640x512, 2026-08-31):

- image AUROC: 0.9583 on the held-out test split
- image F1: 0.5455
- all 4 normal test images predicted GOOD
- 7 of 13 known-abnormal images predicted ANOMALY at the learned threshold

The high ranking metric and low thresholded recall mean the model is useful for
an initial anomaly heatmap experiment but is not ready to control production
pass/fail decisions. Add substantially more reviewed normal captures and train
separate high-resolution component ROIs for white-pin inspection.
