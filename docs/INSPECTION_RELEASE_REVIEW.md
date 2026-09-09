# Inspection verification and release review

Verification is split into three parallel tracks: presence/direction, geometry/clearance, and final decision/export. Results are consolidated under `runtime/inspection/parallel_release_20260908/`.

## Distinct decisions

- An advisory candidate identifies what to investigate or display. It is not a confirmed production defect.
- A controlled photograph has a ground-truth label for specific slots/tasks. It does not label every other slot or task.
- A release review determines whether a particular provider/configuration has enough independently validated evidence for authority. A successful software test or a high model score does not grant authority.
- The production decision remains the actual hybrid result. UNKNOWN is preserved through export; it is not silently converted to PASS or FAIL.

## Current verification boundaries

Retain original-RGB S22 learned inputs, fixed slot-relative placement, separate direction features and PatchCore evidence. The two-region VRM presence corroborator affects missing-candidate display only. It must not approve position or seating.

For geometry, pixel offset from a left-seated reference or dark groove is not a calibrated physical socket-wall clearance. In particular, the requested right-side1mm cannot be verified from the current groove comparison alone. Do not widen position tolerances merely to silence a labelled normal image before reconciling physical seating and process-clearance labels.

## Before granting an individual provider authority

1. Identify the exact provider weights, preprocessing, slot scope and decision configuration by version/hash.
2. Preserve explicit slot/task truth and later corrections; exclude ambiguous or conflicting truth.
3. Separate independent physical-scene evaluation from training and repeatedly used development controls.
4. Report normal false positives, defect misses and abstentions separately; agree acceptance criteria before tuning on that evaluation set.
5. Validate capture/registration and the applicable measurement uncertainty, especially for millimetre claims.
6. Review the scoped validation evidence and apply authority only to that scope; keep other checks UNKNOWN/advisory.

The release-review script is read-only with respect to inspection configuration and never performs step6 automatically. Backend JSON/PNG routes, IDs, authentication, production sequencing and running servers are unchanged.
