# VRM seating: measurement review (2026-09-07)

Status: engineering assessment, NOT a changed inspection contract or production rule.

## What the experiments establish

- Latest contact-tail candidate: held-out normal192342 scores0.202502, lip192557 scores0.178817. The ordering is wrong. No monotonic high-score threshold separates this pair correctly.
- Earlier full-contour comparison: historical normal nearest-boundary p95 spans1–6px; known subtle lip184100 is4px. The latest larger displacement is distinguishable, but subtle height/contact state is not reliably inferred by the tested methods.
- Training only fits a small number of physical seating arrangements. All-flat validation10/10 is NOT evidence of defect recall. Reused failures are regression examples, not independent tests.
- These failures do NOT prove all single-image methods impossible, nor that the camera alone is the unique cause.

## Separate the requirements

1. Slot-relative XY displacement and in-plane rotation: measure registered part geometry relative to reviewed socket geometry. A normal-reference boundary is not the socket wall. Verify measurement uncertainty before enforcing the requested1mm right-wall clearance toward PM1. Do not reinterpret that requirement as a1mm height or all-around clearance.
2. Actual lifted corner/seating: requires independently validated evidence of contact/height. Appearance scores are currently unverified proxies. A small silhouette displacement is not a measured height.
3. Presence, orientation, pins and surface: retain their existing independent stages; a failed seating experiment must not change their labels or thresholds.

## Next-work recommendation

- Do not repeat threshold searches on the current held-out pair or silently reclassify a user-confirmed lip as normal.
- Within current hardware, prioritize the existing XY/socket-relative measurement calibration. Report unresolved seating as UNKNOWN, never infer PASS from an absent heatmap.
- Reliable minimum-height coverage remains an unmet requirement. Before further seating data collection, define the smallest physically unacceptable lift and test whether an additional calibrated view or suitable height measurement resolves it. This needs a separate approved setup; do not move the camera/board automatically.
- No claim that the existing D435, a second RGB view, or stronger light will resolve the minimum lift without measurement. No hardware purchase recommendation made here.
- If hardware/illumination must stay unchanged, retain the unresolved capability explicitly; removing seating from required inspection would need user agreement and a contract revision. No such revision is made.

## Primary-source context

OMRON documents black-on-black component extraction difficulties and using height information for lifted components and coplanarity:
https://inspection.omron.eu/en/3d-sji/cases/post-printing-inspection-machine--post-reflow-inspection-machine

OMRON's technical discussion describes optical-information loss from shadows/reflections and multi-direction imaging with3D measurement:
https://www.omron.com/global/en/technology/omrontechnics/vol54/007.html

These industrial examples motivate separating geometry from appearance; they do not validate KSMC performance or mandate a particular vendor.

No capture, model training/promotion, threshold or runtime contract modification, API restart, or robot/conveyor command in this review.
