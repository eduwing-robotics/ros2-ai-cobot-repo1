# Component tray: active implementation

The active tray view is `run_tray_sections_view.sh`. It uses the team reference-image
registration method (SIFT/RANSAC homography), not the retired depth/white-rectangle
`tray_zones` method.

Run it after the D435 RGB stream is available:

```bash
~/KSMC/vision_assembly/run_tray_sections_view.sh
```

It publishes the verified section overlay to:

```text
/vision/tray/sections_image/compressed
```

The six physical tray areas are defined in `config/tray_layout.json`:

- VRM / black block
- Power Module / long orange
- Inductor / marked white
- SMD Capacitor / right white-brown
- GPU
- HBM

`tray_reference_no_tape.jpg` is required for registration. The config contains the
physically adjusted section boundaries and is the source of truth for later per-part
detectors. This viewer never sends a robot motion command.
