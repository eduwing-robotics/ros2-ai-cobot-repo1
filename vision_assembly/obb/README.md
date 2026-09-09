# GPU YOLO-OBB

This dataset is intentionally separate from runtime calibration data.

Workflow:

1. Capture D435 RGB images at the fixed tray-view pose.
2. Move/rotate both GPUs between capture batches.
3. Label the four GPU corners with `label_gpu_obb.py`.
4. Split the labeled images and train with `train_gpu_obb.sh`.
5. Copy `best.pt` to `ros2_ws/src/vision_server/models/gpu_obb_best.pt`.

The first ten images are one unchanged GPU arrangement. Label the first image and
use `P` only for that initial batch. For later data, move/rotate the GPUs and
capture one image per arrangement; use `S` so labels from different arrangements
are never copied.

The label format is Ultralytics YOLO-OBB:

`class x1 y1 x2 y2 x3 y3 x4 y4`

Coordinates are normalized. Points are reordered clockwise by the labeler.

For the real six-class dataset, use `capture_part_obb_images.py` and
`label_parts_obb.py`. Its class mapping is kept identical to the Unity-native
dataset: GPU=0, HBM=1, Power Module=2, VRM=3, Inductor=4, SMD Capacitor=5.

Train all six completed classes with:

`./train_multiclass_obb.sh --epochs 100 --imgsz 960 --batch 8 --device 0`

The deterministic output is `runs/parts_obb_6class/weights/best.pt`. The
dataset builder must not exclude `smd_capacitor` after its labels are complete.

Labeling controls:

- Left click: select one corner (four clicks per GPU)
- Enter: finish the current GPU box
- U: undo
- S: save this image and continue
- P: copy this image's boxes to every remaining image (identical images only)
- Q: quit

By default, images with an existing non-empty label are skipped. Use
`--relabel` only when an existing annotation must be corrected; it loads and
draws the saved boxes so `U` can remove the wrong box before saving again.
