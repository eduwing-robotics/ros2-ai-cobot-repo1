# Inspection quality and diagnostic evidence

## Scope

The S22 fixed-25-slot hybrid inspection remains unchanged in its component model
weights, learned RGB inputs, slot geometry and component defect thresholds. These
additions check gross capture problems and make unavailable or unpromoted evidence
visible. They do not establish improved defect recall, calibrated crack detection,
physical corner-lift measurement or a production PASS capability.

## Capture-quality triage

`hybrid_inspection/capture_quality.py` compares the registered image with the
existing reference using the same static-board mask as board registration. Moving
parts are excluded; no part is recentered or rotated into a normal pose.

- `NO_GROSS_ISSUE_DETECTED`: no configured gross-degradation rule fired, **not PASS**.
- `RECAPTURE_RECOMMENDED`: gross texture/contrast loss, brightness shift or clipping.
- `NOT_EVALUATED`: invalid registration/input or insufficient usable reference pixels.

The latter two block the effective board/slot decision as UNKNOWN. Original stage
evidence and any pre-quality slot decision remain available. This module does not
trigger another capture; retry/hold policy belongs to the Sequencer, using a new
inspection ID for a genuinely new inspection.

Policy `s22_static_board_quality_v1` is provisional (`validated=false`,
`authority=ADVISORY_ONLY`). It uses 128-pixel cells, at least 512 static pixels per
cell and at least four textured cells. Gross blur requires median Laplacian-variance
ratio <0.18 **and** contrast ratio <0.70; additional triggers are contrast ratio
<0.30, median brightness ratio outside 0.35–2.5, or added white/black clipping
fraction >0.12. Reference/mask hashes and measured ratios are recorded. This is a
coarse image check, not qualification of local pin/crack focus or all illumination
conditions. Even all-PASS slots cannot produce board PASS with an unvalidated
quality policy.

## Reading image and JSON

The original / heatmap / overlay report now includes capture quality, counts of
unpromoted raw FAIL signals, and unavailable checks. A blank heatmap is not evidence
of normality if a provider did not run. Invalid/missing/non-finite PatchCore output
becomes UNKNOWN/UNAVAILABLE rather than a synthetic normal score.

The existing request/pull JSON exposes optional `data.result.diagnostics`:

| Field | Meaning |
| --- | --- |
| `capture_quality` | Triage status, flags, metrics and provisional policy |
| `evidence_audit` | Raw stage FAILs, authority and whether shown as a candidate |
| `provider_health` | Disabled/unavailable stages and missing PatchCore slots |
| `pose_display_audit` | Existing position-display diagnostics |

Counts describe checks/signals, not confirmed defective parts. A raw FAIL with
ADVISORY_ONLY authority remains advisory even when visible in a diagnostic table.
Older saved results may omit these fields: interpret that as **not evaluated**, not
successful quality/provider validation. The offline HTML viewer handles both.

The later parallel hardening pass explicitly lists eight unavailable HBM pin
checks in addition to the five previously disabled experimental VRM seating stages.
That total describes 13 stage entries, not 13 defective parts. Details and the
updated software verification are in [regression checks](SOFTWARE_REGRESSION_CHECKS.md).

Export accepts only explicitly AUTHORITATIVE stage evidence for confirmed findings,
with a valid registration, unblocked capture and FAIL board/slot result. Candidate
objects cannot grant themselves authority. `RIGHT?` maps to the existing
`POSITION_ERROR`; `ROT?` maps to `DIRECTION_ERROR`. Primary reasons respect the
candidate's selected primary code rather than list order. No new defect-code enum
is required on the receiver.

## Compatibility and verification

The API URLs, token, request IDs, idempotency, result polling and separate PNG
download remain unchanged. Diagnostics are optional additive JSON fields; a client
using strict additional-property rejection should update its parser before rollout.
Existing completed records remain immutable. No live server was restarted for this
change and no teammate end-to-end test is claimed.

Eight saved source images produced no new gross-quality warning; 24 artificial
blur/black/white variants were flagged. These are quality-rule regression checks,
not physical defect accuracy. A full host-GPU replay of the saved Sept 7 17:23:49
capture preserved all 25 PatchCore scores and all four displayed candidate sets.
Final result remains UNKNOWN. See `runtime/inspection/quality_guard_20260908/` for
the audit and replay artifacts; failed sandbox GPU attempts are not final results.
