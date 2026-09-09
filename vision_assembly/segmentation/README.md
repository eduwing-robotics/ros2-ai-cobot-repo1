# S22 Parts Instance Segmentation

This dataset and model are exclusively for the perspective-rectified S22
inspection image. Do not mix the teammate's D435 images or labels into this
tree. The six classes are GPU, HBM, Power Module, VRM, Inductor, and SMD
Capacitor.

The model supplies component presence candidates, mask centres, and undirected
long-axis angles to `s22_hybrid_aoi_v1`. It remains `ADVISORY_ONLY` until slot
matching and controlled-defect validation are complete. It does not inspect
GPU/HBM white pins or make a final PASS/FAIL decision.

## 1. Capture a fresh S22 sample

Keep the inspection board inside the established 3.5x optical framing. Use a
different `--scene` name for each physical arrangement so near-duplicate
captures from one arrangement cannot be split across training and validation.

Verified normal assembly:

```bash
~/KSMC/vision_assembly/run_capture_s22_segmentation.sh \
  --scene normal_pose_a --board-state normal
```

For dataset collection, the manual S22 UI session is usually faster. It pauses
the managed conveyor overview, opens a controllable Samsung Camera window on
the laptop, presets the verified 3.5x telephoto/flash-off condition, and imports
only the JPEGs created during that session after the window is closed:

```bash
~/KSMC/vision_assembly/run_capture_s22_segmentation_manual.sh \
  --scene normal_pose_a --board-state normal --label-after
```

Use the mouse in the S22 window to tap focus and the shutter. Take only 2–3
photos while the physical component arrangement remains unchanged, then press
Enter in the terminal that launched the session. Closing the scrcpy window also
works, but Enter is the deterministic completion control. Do not close the
terminal with Ctrl+C. The new 4000x3000 JPEGs are pulled over USB without
recompression, checked for the physical 3x telephoto lens, rectified to the
canonical 1600x1266 board ROI, and registered for labelling. A component
movement or a new defect arrangement requires a new command with a new `--scene`
name so train/validation grouping remains valid.

One missing component, with 24 visible bodies:

```bash
~/KSMC/vision_assembly/run_capture_s22_segmentation_manual.sh \
  --scene missing_hbm_h2 --board-state controlled_defect \
  --expected-count 24 --notes "H2 removed" --label-after
```

Shifted or rotated components are still labelled at their actual visible
positions. They are useful for the detector because the later slot comparison,
not YOLO class training, determines whether their pose is acceptable.

Start with at least 10 scene groups so the dataset builder can hold complete
physical arrangements out for validation. A useful first pilot is 20–30
images; production tuning needs more print, lighting, pose, and controlled
defect diversity.

## 2. Label polygons

```bash
~/KSMC/vision_assembly/run_label_s22_segmentation.sh
```

Keys are shown in the right-side panel. Label only each physical component
body. Exclude the socket, shadow, GPU/HBM white pins, and white orientation
dot. Text is kept outside the image so it cannot hide small SMD parts.

- `0` GPU, `1` HBM, `2` Power Module, `3` VRM, `4` Inductor, `5` SMD;
  either press the top-row/number-pad key or click that class row in the right
  panel and confirm the `selected` text changes before dragging
- tightly left-drag around one component body to create its polygon
  automatically with a SAM2.1 Tiny box prompt; verify every generated outline
- a short left-click still adds manual polygon points; right-click or Backspace
  removes one point
- Enter closes a polygon; `U` undoes the last polygon
- `C` copies all polygons from the previous saved image; on an aligned normal
  board this avoids tracing all 25 bodies again
- place the cursor over a changed component and press `D` to delete that copied
  polygon, then redraw only the moved or rotated body
- `S` completes the image
- `F` completes an intentional expected-count mismatch only for a
  `controlled_defect`/`unknown` capture; normal metadata cannot bypass its
  per-class `1/8/4/5/2/5` count guard

The local SAM weight is stored at
`segmentation/models/sam2.1_t.pt` and is deliberately excluded from Git. If an
automatic outline includes a socket, shadow, GPU/HBM pin, or adjacent object,
move the cursor over it and press `D`, then redraw a tighter box or use manual
points. SAM accelerates annotation but does not replace the operator's dataset
review.

Use `--relabel` to reopen completed images or `--match 'name*'` to select a
specific capture group.

## 3. Validate and split

```bash
~/KSMC/vision_assembly/run_build_s22_segmentation_dataset.sh
```

Only images with a completed review record are included. Scene groups never
cross training and validation splits. Invalid class IDs, malformed polygons,
out-of-range coordinates, degenerate masks, missing files, and absent classes
stop the build.

## 4. Train on the RTX GPU

```bash
~/KSMC/vision_assembly/run_train_s22_segmentation.sh \
  --epochs 150 --imgsz 1280 --batch 4
```

The default is pretrained `yolo26n-seg.pt`. The latest trained weights are
linked as `models/s22_parts_seg_candidate.pt`; this is a candidate link, not a
production promotion.

## 5. Preview one fresh inspection

Capture and infer:

```bash
~/KSMC/run_s22_parts_segmentation.sh
```

Reuse the current ROI intentionally:

```bash
~/KSMC/run_s22_parts_segmentation.sh --skip-capture
```

Outputs are saved under `runtime/inspection/segmentation/s22_parts/`. Every
detection is emitted with `status=UNKNOWN` and `authority=ADVISORY_ONLY` until
slot assignment, tolerance calibration, and controlled validation are added.
