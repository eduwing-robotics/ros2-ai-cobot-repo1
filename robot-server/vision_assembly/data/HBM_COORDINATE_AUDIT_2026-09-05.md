# HBM coordinate comparison audit — read-only

No robot or gripper commands, calibration changes, or correction changes in this audit.

## Reference chronology (KST)

- hbm_cycle_snapshot_2026-09-04.json: 11:31:46, HBM01 [-595.645,-50.349,-47.733] mm. Not the final successful pick.
- full_restart_raise03_snapshot_2026-09-04.json: 15:46:34, HBM01 [-600.319,-49.825,-45.585] mm. This was incorrectly treated as the current physical-cell reference during remaining15 preparation.
- safe_pick_hbm_1.json: 18:09:54, HBM01 [-592.394,-39.920,-47.873] mm. Matches the operator-confirmed successful pick log.
- The 18:09 minus 15:46 difference was already [+7.925,+9.905,-2.288] mm on September 4. Thus the remaining-part mismatch against 15:46 does not prove a new September 5 transform fault or operator movement today.

## Numerical isolation using present TrayHome transform

- Successful stored camera point [0.052280,0.032834,0.482000] m passed through current T_base_flange @ T_flange_camera gives [-592.391446,-39.918911,-47.875355] mm.
- Difference from successful saved Base point: [+0.002554,+0.001089,-0.002355] mm. This is numerical agreement, not a physical calibration accuracy measurement.
- Present RGB CameraInfo: 1280x720, fx905.594543457, fy904.604614258, cx644.421691895, cy379.840270996.
- Reprojecting the successful camera point with present K gives [742.646760,441.462238] px; saved successful pixel [742.76,441.52]. Difference [-0.113240,-0.057762] px (about0.127px).
- Current serialized camera-to-Base arithmetic residual max0.000673mm. Current HBM camera-to-pixel residual max0.231546px. Stable pixel and camera vectors are separately aggregated; exact equality is not expected.
- Earlier full snapshot and current detection HandEye hashes agree: f08dc2dd9a40523e3f0c69e9285d88c774d69553659c3d9be891da727877c558. The final safe-pick target itself does not retain HandEye hash/K/flange pose.

## Limits and decision

- The successful HBM01 is now on the PCB, not in the tray; current remaining HBM cannot be treated as repeated measurements of HBM01.
- Final safe-pick target lacks raw RGB/depth images and contemporaneous K/flange pose. Full independent reconstruction of yesterday's segmentation and depth sampling is unavailable from that file.
- Agreement above argues against a gross current arithmetic/profile mismatch for this stored point. It does NOT validate HandEye across poses, physical TCP, other parts, or current pick safety.
- The cause of the September4 reference-to-final difference is unresolved (detection, part state, or other upstream change). Do not invent a new offset or relax the5mm matching gate.
- Do not use the15:46 snapshot to establish today's remaining physical-cell identities without independent validation. Need fresh non-SMD cell identity checks and fresh board capture before assembly; explicit-slots executor integration remains incomplete.
