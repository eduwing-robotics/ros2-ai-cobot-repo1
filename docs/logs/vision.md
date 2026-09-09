# AI/Vision 작업 기록

## 2026-09-09 Arrival callbacks and countermeasure evidence cards

- Inspected supplied `/home/hc/Downloads/불량대책서_샘플_종결본_v2.xlsx` (SHA256394a6e3ee96ca263d2e273b05f776e12b90d7c78f462a902af3cd13555f9c7e4): sheets대책서/검사근거/대체품; first-page image ~212×168px with right-panel srcRect crop. It is an UNKNOWN/unissued review sample, not a confirmed closed defect. Source workbook preserved. Derived preview replaces only first-page image relationship/crop and its caption; other sheet evidence remains intact. ZIP/XML/embedded-image integrity checked; no OnlyOffice GUI rendering claim.
- Added optional1200×950per-finding countermeasure cards: registered original pixels, board locator, large component window, slotcode, Korean finding name, explicit unconfirmed/confirmed status. No fabricated heatmap/defect mask, super-resolution, or verdict change. New reports freeze CAD/fixed-slot geometry in REGISTERED_BOARD_CXCYWH. Older reports use saved geometry snapshot, or explicitly labelled display window about archived expected center, never current mutable calibration/pretended outline. Source previewCAP-01 comes from archived inspection1e2f3eab-3d28-4e4b-859b-2ff37b5676f7, not a fresh capture.
- Existing JSON and `/image` full-report bytes preserved. New completed requests may advertise image.countermeasure_views for authenticated `/image?view=countermeasure&slot=CAP-01`; files are frozen at preparation, SHAchecked at retrieval, unknown slots404, duplicate query400, tampering409. Old completed records remain immutable/no retroactive views. Render unavailable does not change original image or verdict. Sequencer remains the requester; no Vision→MainServer uploads/DB access. Manual handoff copies optional cards with path=null rather than advertising unregistered routes. Workbook integrator must remove old srcRect and fit the entire card; full inspection remains on evidence sheet. Integration replay verified unchanged originalPNG andUNKNOWN plus oneCAP-01card.
- Direct5second read-only ROS discovery showed conveyor_roi assembly/inspection trigger publishers, no subscribers on them, no/conveyor/state publisher and no/conveyor/services. HTTP8766not listening. This establishes current server absence, not the root cause of every past missing callback. Local installed conveyor entrypoint resolves to edited source via build symlink. No server started/restarted, no real command published, no camera capture, no model/threshold change.
- Added compatible command-state arrival fields motion_id/server_instance_id/completed_station/arrival; accepted response returns same motion_id. Successful vision-trigger HOLD retains completion across repeated10Hzstate messages/trigger false; reset/fault/manual stop do not advertise arrival. Existing target_station=null behavior and safety interlocks unchanged. Updated Unity sample actually raises AssemblyArrived/InspectionArrived events; Python example deduplicates by motion_id even if an intermediate MOVING message is missed. Completion is commanded vision stop, not encoder feedback or automatic permission to start a robot. Consumer must match its pending motion_id; teammate code/live delivery and Unity compilation not verified.
- Validation:554offline tests passed,3socket tests deselected; two relevant local HTTP roundtrips then passed separately (legacy/full PNG and optional card/auth/integrity). New controller harness covers assembly/inspection, repeated triggers, latch/reset, fault/no-request exclusion; adapter tests late first state and repeated/missed-moving messages. No live motion/DB/remote upload. Handoff instructions in team_handoff/vision_sequencer_api/COUNTERMEASURE_V2_UPDATE.md; actual teammate end-to-end requires server launch and consumer application.

## 2026-09-09 VRM context and geometry conflict repair

- Implemented two additional VRM direction *nomination* routes, without modifying trained weights or final fusion: (a) boundary min-area/PCA and auxiliary axis agree within2deg, same sign, median>=8deg, boundaryconfidence>=.95, aux>=.25, centers<=5px, nonempty>=.95; (b) original RGB context presence>=.99, boundaryconfidence>=.97, nonempty>=.95, both boundary axes same sign/within2deg and exceed max(5deg, configured angle tolerance+2deg). Finite/range/probability-sum checks fail closed. The second route tolerates a weak auxiliary angle disagreement, NOT height evidence; boundary axes share one mask and are not independent sensors. Existing routes remain; no slot-relative alignment, wall-clearance criterion, authoritative PASS/FAIL, model or API change.
- `full_label_rotation_audit.json` matches125unique labelled source/slots (88correct,17empty,20rotated) across saved reports, checking source hashes and preserving unknown truth. Newly eligible geometry is confined to3known rotated source/slots (5report observations including repeats); one already had an existing context DIR nomination. Thus only2previously missing displayed directions are demonstrated recovered, not3new detections. No additional normal/empty nomination in the archive scan; missing boundary evidence remains abstention, so88normal matches are NOT88qualified PASS observations. These are reused development controls used for tuning, not independent performance estimates.
- Full GPU replays after changes: historical144017→`three_axis_replay_144017/20260909_163810_103038` now VRM05DIR?; historical150517→`rotation_final_20260905_150517/20260909_164445_899453` now VRM03DIR?. Historical144513 still VRM01POSE? with inconsistent direction estimates; do not relabel it as a confirmed orientation detection. Normal historical143632 has noVRMwarning; recent normal154203→`rotation_final_20260909_154203` has0total candidates. YOLO available and PatchCore executed on these saved-image runs; full25slot report staysUNKNOWN. Visually checked rendered VRM03DIRECTION annotation and JSON agreement. No fresh capture, robot/conveyor motion, server restart or external API/DB write. Frozen3class candidate remains undeployed; pin/seating/production-authority limitations remain unresolved.
- Final software regression:507passed,2HTTPsockettests deliberately deselected; includes confidence/NaN/probability/angle-wrap/object-center/normal-angle rejection, no input mutation and advisory-only fusion assertions. `git diff --check` clean for tracked touched runtime/log files. Running services were not restarted, so already-imported long-lived code is not claimed hot-reloaded; new inspection subprocesses load the changed module.

- Joined frozen-state historical controls to hash-verified archived full reports with `audit_vrm_context_geometry.py`: initial coverage normal0/17, empty6/6, rotation1/4; covered rotation had geometry warnings, but missing reports cannot imply PASS. Replayed historical144017 with current full GPU pipeline into `vrm_deadline_candidate_20260909/geometry_replay_144017/20260909_162647_512907`. Explicit rotatedVRM05 still has no displayed VRM candidate: oldstateCORRECT, auxiliaryposeoutside-limit, boundary axes-9.638/-7.732degrees; the existing two-axis8degree gate is not met. This demonstrates that existing geometry cannot yet safely cover the new classifier's abstention. No threshold relaxation, model replacement, authority promotion, live capture, robot/conveyor command, server restart or external API/DB write. Replay completedUNKNOWN; other scene components are not labelled normal by this VRM-only control. Archived join is diagnostic, not current-runtime acceptance or independent accuracy.

- Trained a materially different isolated frozen-context3stateprobe: localcachedImageNetEfficientNetB0 central37%+context88%fixedRGBviews,balancedlogisticC1,unchangedscene split and0.90gate,noaffine/CLAHE/refit-after-holdout. Internal12validation raw12/12 but10abovegate; fresh153954/154203normal10slots candidate9correct/1abstain versusold4correct. Additional6historicalscenes with pre-existing explicitlabels, no fitting-source hash overlap:normal17/17,empty6/6,smallrotation0/4atgate(allUNKNOWN). Rawsmallrotation3/4incorrectCORRECTat0.562/0.889/0.860; fourthROTATED0.892. Hence no threshold lowering or globalpromotion despite normal improvement. Saved `vrm_deadline_candidate_20260909/frozen_context_state/{evaluation,historical_evaluation}.json` andDEPLOYMENT_DECISION.md. Historicalsourcehashes missing in originallabelcontract are explicitly marked; newlycomputedhashes preserve this replay, not prior provenance. Initial unit-test collection importpath fixed; focused tests verify fixedviews,inputpreservation,rejection and rawargmaxvsqualifiedvote accounting. No active model/reference/criteria changes,newcapture,motion,serverrestartorDB/APIwrites; correlateddevelopmentalcontrols are not independent deploymentaccuracy.
- Actually built and trained isolatedVRMdeadlinecandidate:83crops=70existingV2+13target-labelled crops from7Sept9controlledscenes; original manifests/crops preserved. Excluded freshnormal153954/154203 andsame-placement144833. Added opt-in trainer geometry-safe(noaffine),localTorchScriptinitialization,and fixedconfidence flags with early invalid-value rejection; legacy defaults retained.20GPUepochsfromV6,lr3e-5,gate0.90,RGBphotometricjitteronly; candidate staysADVISORY_ONLY. Internal scene-split macrorecall0.8333,ROTATED0.50; inheritedV6 prior exposure to historicalvalidation explicitly limits independence. Held-out-from-fine-tuning currentnormal10slot observations:old4CORRECT at0.9,candidate3;VRM2/3/4unresolved and oneVRM5regression. REJECTED candidate, `runtime/inspection/vrm_deadline_candidate_20260909/DO_NOT_DEPLOY.md`; model/evaluation retained for provenance, not installed.10trainer/datasettests passed. No new capture, robot/conveyor motion, camera/serverrestart or DB/API write. This is a failed improvement experiment, not increased detection accuracy or final qualification.
- Investigated current normalVRM02/03/04: three-stateV6 confidences0.545EMPTY/0.534CORRECT/0.379CORRECT conflict with independent RGB-context presence0.99965/0.99884/0.99666. Shared crop function and model crop-pipeline metadata agree; that alone does not prove historical geometry equivalence or a unique distribution-shift cause. No threshold reduction or retraining. Added `vrm_presence_state_summary` to future raw slot JSON, separating PRESENT/EMPTY context candidates from already-gated EMPTY/CORRECT/ROTATED state, explicitly UNKNOWN/EXPLANATION_ONLY; raw votes and candidate/fusion behavior unchanged. Model disagreement is flagged rather than converting presence into correct orientation. Replay15savedslot records over freshnormal,batchmissing,andVRM3rotation preserves ambiguity: missingVRM1context unresolved, missingVRM4/5empty; rotatedVRM3present butstate unresolved, notnormal. Saved `hbm_release_regression_20260909/vrm_presence_state_explanation.json`; prior reports unmodified.472tests passed,2HTTPsockettests deselected. This improves explanation, not demonstrated classification accuracy. No capture/training/reference/model/threshold change, motion, server restart or DB/API writes; compact teammate API propagation not tested.
- Audited latest fresh-normal154330 raw fusion evidence, not just displayed candidates: all active slot stagesADVISORY_ONLY;surface23/25controlled-defect-threshold-missing;9orientationtype providersuncalibrated;HBM1–4reference insufficient;GPU pinuncertain;VRMseating5disabled;capturepolicyunvalidated. Specifically normalVRM02 low-confidenceEMPTY,VRM03/04low-confidenceCORRECT andVRM04YOLOmissing remain underneath zero displayed candidates. Therefore no-candidate normal repeats are NOT full recognition or final qualification. Read fuse_required_stages/fuse_board_result; finalUNKNOWN is contract-consistent, not an export bug. Saved `hbm_release_regression_20260909/FINAL_DECISION_BLOCKERS.md` with targeted next priorities. No capture, training, authority/threshold/model/runtime changes, motion, server restart or DB/API writes.
- User explicitly confirmed all currently placed components normal. Two new flashOFF4000x3000/7mm optical captures153954 and154203, each followed by full GPU/CAD-trial inspection154032_384501 and154330_779617:25slots,YOLOavailableADVISORY_ONLY,0displayed candidates both times,HBM07individual left/right no missing indices (internalPASS,not authoritative). Right first-anchor ratio1.8189 both vs old warning0. All final results remainUNKNOWN. Saved source hashes/truth provenance in `hbm_release_regression_20260909/fresh_normal_confirmation.json`; no training or runtime/reference/threshold changes. This is repeated non-reproduction, not a repaired intermittent detector. Both overview restores confirmed; no robot/conveyor motion, server restart or DB/API writes. Normality is user-labelled, not inferred from zero candidates.
- Inspected native HBM07warning133552 and restored133923 crops; raw fixed candidate neighbourhood measurements show warningLmax86/p9576.7 versus disclosedHBM01defect142758 Lmax87/p9572.0 (OpenCVuint8Lab,low saturation). Thus simple brightness relaxation is not supported: warning and true-defect background overlap. Strong HBМ07gap/HBM08endpoint defects are darker, but cannot generalize those alone to single-pin sensitivity. Saved `hbm_release_regression_20260909/HBM7_PHOTOMETRIC_LIMIT.md` with source/region values. No new classifier, threshold, training, runtime/reference changes, capture, robot/conveyor command, server or DB/API writes. Unique cause and physical truth of old collateral warning remain unresolved; controlled known-normal unchanged placement is needed, not repeated fitting to the same ambiguous frame.
- Final batch software regression:463hybrid/integration tests passed,2HTTP socket tests deselected. This is code-level coverage, not physical inspection accuracy; all launched offline inference children finished.
- Deadline regression batch: implemented offline paired-column x-only probes (agreement<=2px,shift<=12px,no y fitting), then original legacy strip replay with integer-only diagnostic translation and defect points mapped back. Fixed-slot pose/direction and runtime remain untouched. Short-anchor probe is still inadequate; legacy replay over19VRM-control scenes/152HBMcrops plus4normal/defect scenes/32crops preserves side statuses/missing indices, including HBM8endpins8/9 but also unexplainedHBM7warning. No measurable runtime improvement, so reject deployment. Clarification: ~8.5px displacement diagnoses NEW narrow7x7 probe failures, not the established broad-strip warning's cause. Source/control-label dependence retained.
- Actual GPU full-stack replays: normal144833→`hbm_release_regression_20260909/gpu_normal/152550_266951`,0candidates; defect142717→`gpu_known_defects/153041_579022`,HBM01/04/07PINS? andPM04POSE?,HBM04falseDIRabsent but orientationUNKNOWNconflict. Both25slots,YOLOADVISORY_ONLY,finalUNKNOWN. Visually checked three-panel PNG/heatmap. Initial sandbox runs had unavailableCUDA/YOLO; preserved and excluded, rerun with approved GPU access. Added hash/source/slots/provider/candidate/authority regression checker,passed; evidence and limits grouped in `runtime/inspection/hbm_release_regression_20260909/VALIDATION_SUMMARY.md`. No fresh capture/training/reference/runtime changes, robot/conveyor commands, server restart, DB/API writes. Still not all-slot release qualification or independent accuracy validation.
- Added offline `audit_hbm_column_displacement.py`; visually inspected reference/current native HBM07 crops and measured unwarped white-column positions for16crops from two user-normal scenes against hash-pinned references. Current144924 HBM07 left/right move+8.68/+8.53px; earlier normal104727 +8.35/+8.18px. CurrentHBM06 +3.81/+3.84px, HBM08 +6.05/+5.31px. This demonstrates systematic lateral correspondence mismatch beyond the prior +/-3px reference window on these slots, rather than establishing missing pins; origin (part placement, crop/registration mapping or reference geometry) is not isolated. HBM01–04left still cannot be fitted, so this does not solve visibility. Saved `column_displacement_probe.json`. Three new tests,21combined passed. No compensation, reference update, production criterion change or PASS promotion: nearest-y statistics do not identify pins, and local alignment must not erase independent slot pose faults. No capture, robot/conveyor motion, server restart or DB/API writes.
- Added offline reference-locked comparison `audit_hbm_column_reference.py`: SHA-verified existing reference columns supply original-coordinate7x7 white-evidence targets; current anchors never shift targets. Missing endpoints cannot redefine the reference. Four new tests cover endpoint removal, identical UNKNOWN, darkness abstention and shape mismatch; combined18tests passed. Replayed24crops over normal144924, relocated142758 and historical183116; saved `column_reference_probe.json`. Normal scene has6/16sides without near-absence at tested anchors,6reference-unresolved and4sample-unresolved; zero displayed deficit candidates does not imply successful inspection. HistoricalHBM08right yields one deficit candidate but leftHBM07/08 also yield candidates; relocatedHBM01/07right abstain andHBM04right reference is unresolved. This fails acceptance for replacing existing pin detection. Exact physical pin counts and candidate-side truth are not established by this probe. No runtime/reference/threshold/model/capture/robot/conveyor/server/DB/API changes. Current reference coverage and across-capture correspondence must be resolved before promotion; synthetic tests only establish code behavior, not detection accuracy.
- Offline white-component column probe `audit_hbm_pin_columns.py` now searches broad side windows in original RGB, excludes central logo/lower dot regions, and fits only sufficiently supported/spread columns. No warp, reference rewrite, automatic pin count, missing-pin judgement or production import. Four synthetic tests plus existing band tests:14passed. Replay24saved crops (normal144924, relocated defect142758, historical two-pin-loss183116) found unverified columns11/16,10/16,9/16sides respectively. NormalHBM01–03left only3/2/3candidate anchors; HBM04left has9but geometry fails. Normal rightHBM04 also lacks support. Historical defectiveHBM08right still yields a column with6anchors: finding a row DOES NOT mean intact pins, and adaptive localization must not hide endpoint loss. Therefore do not promote this probe or replace existing defect evidence. Output `runtime/inspection/hbm_blind_relocated_20260909/white_column_probe.json` (initial generic abstention label; subsequent script distinguishes geometry from count); data are development observations, not accuracy validation. Runtime unchanged; no capture, robot/conveyor motion, server restart or DB/API writes. Single-pin certainty and left-side visibility remain unresolved.
- Implemented offline audit_hbm_outline_bands.py: hash-verified saved segmentation outlines define row-wise left/right +/-6px bands in the original image frame, with no image warp or changes to fixed-slot pose/direction. Invalid/clipped outlines abstain; JSON explicitly UNVERIFIED, no PASS/FAIL. Five geometry tests pass (source preservation, separation, invalid/clipped input). Fixed latest-JSON alias handling after initial ambiguity rejection; replay then completed24HBM observations over normal restoration and two known-defect scenes.
- Prototype did NOT establish improvement: normal144833 HBM01–04left white counts28/29/0/143, and HBM05–07left15/1/31 despite previously usable fixed-band evidence. Unverified segmentation silhouette is not reliably the white-pin boundary; +/-6px and tip exclusions may miss pins. Saved outline_band_probe.json. Brightness totals alone cannot establish defect sensitivity; do not deploy or replace old strips. No live geometry/reference/threshold/model changes, training, capture, robot/conveyor motion, server restart or DB/API writes. Need explicit pin-row localization/visibility evidence rather than assuming learned body contour matches leads.
- Added offline audit_hbm_left_strip.py; inspected native HBM01/03normal-restoration crops and probed fixed left strip shifted0/4/8/12px without changing runtime geometry. Three scenes ×4slots results saved left_strip_coverage.json. Current HBM03 has0white pixels in original strip,28at+4px; HBM01 57→86, HBM02 39→69, HBM04 371→407. Thus some usable signal lies outside original strip, but modest shifting still leaves sparse evidence inHBM01–03. At+12px additional body/logo contamination is possible; brightness counts are not validated pins. Original referenceHBM03 remains0at+4px; exposure/visibility differences persist. No justified universal ROI correction or proof of full occlusion; do not widen runtime bands simply to maximize white pixels. No production config/reference/model changes, capture, training, motion, server or DB/API write. Offline script executed successfully over12native crops; this is geometric/photometric diagnosis, not defect accuracy validation.
- Screened84saved HBM01–04crops from explicit normal104704, later VRM-only presumed-unchanged-HBM controls and normal restoration144833 (excluded old empty-board replays). Left self-reference peak maxima6/5/4/7; six-peak eligibility counts1/0/0/6. These are repeated/presumed normal observations, not independent pin-normal labels. Candidate104704 references forHBM01/04 fail transfer over40other crops:HBM01 0PASS/9FAIL/11NOT_INSPECTABLE, HBM04 0PASS/19FAIL/1RECHECK at internal side level. Therefore rejected replacement; high self-count alone is not stable reference quality. Saved reference_candidate_screen.json; no thresholds/models/references/training/capture/motion/server/DB/API changes. HBM02/03 left coverage and cross-image variability remain unresolved; don't fix them by reducing required peaks or treating abstention as PASS.
- Diagnosed persistent normal HBM01–04 left-side abstention: pinned REFERENCE peaks are0/2/0/4 (<existing6 minimum), not current-sample darkness. Adapter previously overwrote reference failure as insufficient visible sample anchors. Now preserves REFERENCE_PIN_ANCHORS_INSUFFICIENT, separates reference_review_required/reference_insufficient_sides from sample_uncertain_sides/recapture_recommended, and emits HBM_PIN_REFERENCE_INSUFFICIENT when no other candidate exists. Both reference and sample issues may coexist. Diagnostic recommendation only; global retry policy unchanged.
- Replayed16native crops (normal144924 and blind relocation142758): normal HBM01–04 correctly require reference review rather than sample-only recapture; knownHBM01/04/07pin candidates preserved.442tests passed,2socket tests deselected including mixed reference/sample failure test. No reference replacement, thresholds/authority promotion, training, capture, robot/conveyor command, server restart or DB/API write. This fixes failure attribution, not the missing left-side reference coverage; validated better reference geometry/visibility is still required.
- User-acknowledged normal replacement ofHBM01/04/07: fresh144833→hbm_blind_relocated_20260909/fresh_normal_restoration/144924_643925 has0displayed candidates, all8HBM expected lower-left dot selections. Previous3pin nominations clear without further tuning/training. HBM01–04still report insufficient pin observation; do not equate warning clearance with pinPASS. FinalUNKNOWN, source/placement provenance saved. FlashOFF4000x3000 capture/overview restoration succeeded, no robot/conveyor motion, server restart or DB/API writes. Completes this mixed-defect→normal candidate restoration check, not all-slot production qualification.
- Fresh post-conflict capture143941→hbm_blind_relocated_20260909/fresh_conflict_validation/144020_397813 selects onlyHBM01/04/07PINS?. HBM04 direction remainsUNKNOWN/size-position conflict (not PASS), no false DIR? displayed; PM04POSE? now absent after user's planned restoration, physical completion not separately assumed. Source/expectation saved, no tuning/training. FinalUNKNOWN, flashOFF4000x3000 capture and overview restored; no robot/conveyor motion, server restart or DB/API writes. Fresh candidate behavior confirmed, not full direction recovery or production accuracy.
- Added symmetric HBM dot size/position-ranking conflict abstention: when the score-winning corner is not the unique largest selected blob, return UNKNOWN/WHITE_DOT_SIZE_POSITION_CONFLICT instead of PASS or FAIL. No expected-corner preference, pixel alignment, pin suppression or new size threshold; raw candidates/scores retained with area winners and recapture recommendation. This is reduced assertion under conflicting evidence, NOT restored normal-direction recognition. Other pin/pose stages remain independent.
- 441 tests passed,2socket tests deselected including3new symmetric/conflicting-normal tests.216saved HBM crops reviewed: target relocatedHBM04 becomesUNKNOWN, prior suppression-fix cases retain expected-dot advisoryPASS; two archived HBM08upper-right controls retainFAIL. Full GPU saved142717 replay→dot_conflict_repair/143709_208398 removes onlyHBM04DIR?; HBM01/04/07PINS? and PM04POSE? retained, finalUNKNOWN. Source validation saved; no fresh capture, training, motion, server restart or DB/API writes. Evidence is developmental, not independently qualified new lighting/pose coverage.
- Relocation ground truth disclosed: HBM01/04/07 defective matches all3slot nominations; PM04 is the top module and user observes upward displacement, plans restoration. User explicitly confirms HBM04directionNORMAL, so its DIR? is a FALSE POSITIVE after the previous repair. Saved separate ground_truth_confirmation.json without altering blind prediction. Native crop/code review shows true lower-left dot now survives(area195.5,score0.654261), but upper-left end pin(area180.5,score0.816842) wins proximity-weighted ranking. Different mechanism from prior suppression; shape/size similarity remains unresolved. No new capture during PM restoration, code/threshold/training/server/DB/API changes or motion. FinalUNKNOWN, no complete per-reason success claim.
- New blind relocation142717→hbm_blind_relocated_20260909/142758_452582: frozen pre-disclosure predictionsHBM01PINS?(right top1), HBM04DIR?/PINS?(upper-left dot/right bottom8), HBM07PINS?(right upper/middle gap1,2,3,4,6), PM04POSE? persists despite requested restoration. Identities/actual orientation/PM truth withheld; do not claim success from3HBM count or ignore direction warning. No top-three selection, tuning/training; blind_prediction.json preserves source hash and expected setup. FinalUNKNOWN. FlashOFF4000x3000 capture/overview restore succeeded; no robot/conveyor motion, server restart or DB/API write.
- Fresh post-fix same-placement capture142116→hbm_blind_three_20260909/fresh_dot_filter_validation/142246_912129: HBM04 lower-left true dot selected (margin0.716427), direction warning absent; HBM03/04/05PINS?, HBM04POSE?, PM04POSE? retained with no additional displayed candidates. Source/user-label provenance saved; no tuning/training on fresh image. FinalUNKNOWN and ADVISORY_ONLY retained. FlashOFF4000x3000 optical capture and overview restored, no robot/conveyor motion, server restart or DB/API writes. Successful fresh temporal repeat, not cross-slot/lighting qualification.
- Corrected white-dot pin-column filtering symmetrically: peers must have area ratio0.5–2.0, and3comparable blobs constitute an edge column (previously4any-size blobs). This deliberate development-rule change preserves large dots beside small fragments and excludes3remaining similar pins; it never favors expected_corner or moves the crop. Added configured constants to evidence limits. Authority unchanged. Three new synthetic tests cover normal/reversed dots and pin-only abstention;438 regression tests passed,2socket tests deselected.
- Replayed224saved HBM crops: only the two target false-direction cases change stage status to advisoryPASS; empty crops remainUNKNOWN (direct-function reason differs from presence-gated runtime, not a pipeline change). Additional archived upper-right HBM08 cases154112/154202 both retain directionFAIL. These are reused saved cases, not broad independently labelled accuracy. Full GPU replay of141114→dot_filter_repair/141636_956776 removes only HBM04DIR? while retaining HBM03/04/05PINS?, HBM04POSE?, PM04POSE?. True dot[40.16,177.02] selected, finalUNKNOWN; validation.json saved. No fresh capture/training, robot/conveyor motion, server restart or DB/API writes. Subsequent child inspections load change; fresh physical repeat remains unverified.
- User explicitly confirms HBM04 orientation normal (position warning plausible), correcting any broad success interpretation. Same-placement flashOFF capture141114→hbm_blind_three_20260909/unchanged_direction_review/141207_951823 reproduces identical candidates, including erroneous HBM04DIR?. Code/component diagnosis: true lower-left dot(x40.16,y177.02,area306.5) has4near-x peers and is suppressed as an edge pin column; remaining right pins have3peers and survive, bottom pin(x130.99,y190.60,area130) wins lower_right. Previous frame exhibits same4versus3 mechanism. This is a demonstrated pin-column filtering failure, not actual reversed direction; wrong-dot attribution not simply generic lighting. Saved diagnosis.json; original blind prediction preserved. No runtime modification/training, finalUNKNOWN, overview restored, no robot/conveyor motion, server restart or DB/API writes. HBM3/4/5pin and PM4position nominations retained; HBM04 per-reason success explicitly rejected.
- Blind140134 ground truth disclosed AFTER saved prediction: user confirms defectiveHBM03/04/05 and PM04 left side outside socket after handling. All3disclosed defectiveHBM slots were nominated; collateral PM04POSE? is confirmed, not a false warning. Appended separate ground_truth_confirmation.json, preserving original blind_prediction.json and raw report. Exact pin numbering and HBM04 additional DIR?/POSE? were not independently confirmed; no per-reason100% or population accuracy claim. This is one successful blind slot-identification scene with finalUNKNOWN unchanged. No tuning/training, capture, motion, server or DB/API changes.
- Prospective blind trial: user disclosed3defectiveHBM parts but withheld IDs. FlashOFF capture140134→hbm_blind_three_20260909/140158_589514 with unchanged criteria selects HBM03PINS?(right upper peak1), HBM04DIR?/PINS?/POSE?(right long gap, pose confound), HBM05PINS?(right lower peaks8/9), plus PM04POSE? collateral. HBM06 right peak4 uncertain without displayed candidate. Recorded blind_prediction.json BEFORE ground-truth disclosure; no top-three selection, tuning/training or success claim based on count. FinalUNKNOWN; actual identities and collateral truth await user. Overview restored, no robot/conveyor motion, server restart or DB/API writes.
- HBM runtime evidence now retains individual-side reason/uncertain_indices and exposes observation_quality with uncertain sides and recapture_recommended, derived solely from EXISTING NOT_INSPECTABLE/RECHECK abstentions. No new brightness cutoff, candidate suppression or authority change. UNKNOWN without a competing candidate receives HBM_PIN_OBSERVATION_INSUFFICIENT_RECAPTURE; other-side/long-gap/individual candidates remain intact. This flag is diagnostic only, not a new scheduler or API retry mechanism; NO_EXISTING_ABSTENTION explicitly does not certify visibility/normality.
- Saved eight-crop runtime-adapter replay (HBM07/08 over four captures) preserves known HBM08two-pin candidates and the unexplained HBM07 warning. It correctly exposes an uncertain left side alongside a retained right-side HBM08 candidate. Thus this change improves explanation, NOT the original HBM07 false-warning sensitivity.435 hybrid/integration tests passed,2socket tests deselected;17 focused pin/audit tests include dark abstention and cross-side candidate preservation. No new capture, training, motion, server restart or DB/API write. Existing reports unchanged; subsequent inspection children serialize the additional raw JSON evidence. Actual teammate API roundtrip not performed.
- Extended offline visibility audit with finite gain validation, source-preserving synthetic intensity scaling and exclusive-create JSON output. Four captures/32original crops ×5gains ×2sides give320 correlated side observations, saved hbm_pin_synthetic_gain_audit.json. Both known HBM08two-pin controls retain8/9 at gains1.0–0.7, abstain NOT_INSPECTABLE at0.6; restoredHBM07 transitions PASS→RECHECK→NOT_INSPECTABLE as synthetic brightness falls. Legacy side states are not final authoritative decisions. No new brightness cutoff deployed: global pixel scaling cannot certify local shadow/occlusion or dim single-pin sensitivity.15focused tests pass. No training, new physical capture, motion, camera/runtime/server/DB/API change. Detailed comparison extended; source images preserved.
- Added offline audit_hbm_pin_visibility.py to replay hash-pinned reference comparisons without runtime votes/threshold changes. Four saved captures yield32HBM crops/64side observations (not independent labelled normals). Sept8 corrected-provenance actual two-pin-loss HBM08 retains right indices8/9 in both captures; visible-anchor medians1.1871/1.0736, versus Sept9 HBM07 warning0.46535/restored0.8025. HBM01 partial-loss controls also retained. Diagnostic comparison extended;9 existing pin tests passed. Evidence motivates visibility-quality development but cannot select a production cutoff or certify dim-defect sensitivity. No training, capture, motion, server/DB/API changes or PASS/FAIL promotion.
- Read-only HBM07 follow-up compares133528 warning vs133900 cleared, including visually inspected fixed crops and per-pin code trace. Same reference; right-band white pixels60→240, first peak ratio0→0.8147, remaining peaks0.3967–0.5111→0.6509–0.8728. No long-gap candidate: individual thresholded first-peak absence triggers PINS?, not PatchCore. Existing three-anchor gate still passes the weaker frame. Immediate trigger established, physical absence and unique lighting/occlusion/registration cause NOT established. Saved hbm07_pin_warning_comparison.md; no suppression, threshold tuning, training, additional capture, server/DB/API changes or robot/conveyor commands. A visibility guard requires intact/real-defect controls before deployment; both final statuses remainUNKNOWN.
- Batch restoration133900→fresh_restored_vrm1_vrm4_vrm5/133923_077499: all displayed candidates0. VRM01/04/05 missing warnings cleared, CORRECT0.996095/0.964059/0.992224; HBM07PINS? did not recur on this frame without any code/threshold changes. This is temporal non-reproduction, NOT a repaired pin detector. FinalUNKNOWN. Source/acknowledged placement archived; no training/tuning. FlashOFF4000x3000 optical capture and overview restored, no robot/conveyor motion, server restart or DB/API writes. Latest requested VRM rotation and removal controls have candidate responses, but all-slot production authority and robust HBM pin detection remain unqualified.
- Fresh batch removal133528→fresh_missing_vrm1_vrm4_vrm5/133552_676235 selected all requested VRM01/04/05MISSING? (EMPTY0.996985/0.997496/0.964718), with VRM02/03 unflagged. However HBM07PINS? appeared additionally on otherwise requested unchanged placement: NOT a clean whole-board control and not a confirmed HBM defect. Preserve collateral warning for review rather than suppressing it. FinalUNKNOWN; restoration pending. Source/acknowledged labels and outcomes archived, no tuning/training. FlashOFF4000x3000 capture and overview restored; no robot/conveyor motion, server restart or DB/API writes.
- Fresh VRM03 restoration133229→fresh_restored_vrm3/133250_717444: displayed candidates0, axes2.489553/1.446372deg, stateCORRECT0.986827. Rotation132904 produced onlyVRM03DIR? and restoration clears it without intervening tuning/training. Source hash and user-acknowledged restoration archived. FinalUNKNOWN, not production PASS qualification. FlashOFF4000x3000 capture and overview restoration succeeded; no robot/conveyor motion, server restart or DB/API writes. This completes the latest rotation/restoration candidate pair; remaining missing-slot coverage and authoritative fusion qualification are separate.
- Fresh requested VRM03 rotation132904→fresh_rotated_vrm3/133021_748728: ONLYVRM03DIR? via context/two-outline agreement, axes8.530766/7.031282deg; stateCORRECT0.843085 does not veto geometry. Source/user-acknowledged placement recorded in validation.json; angle not physically measured. No training/tuning, finalUNKNOWN, restoration pending. FlashOFF4000x3000 optical capture and overview restore succeeded; no robot/conveyor motion, server restart or DB/API submission. This is one fresh candidate detection, not production FAIL qualification.
- Fresh VRM05 restoration132006→fresh_restored_vrm5/132132_197616: displayed candidates0, axes0.806929/0.797871deg, stateCORRECT0.997009. The preceding fresh rotation131557 selected onlyVRM05DIR?; restoration clears it without intervening tuning/training. Source hash and requested/user-acknowledged label retained in validation.json. FinalUNKNOWN, not full-board PASS or all-slot qualification. FlashOFF optical capture and overview restoration succeeded; no robot/conveyor motion, server restart, DB/API writes. VRM03 fresh rotation and remaining missing-slot controls are not established by this pair.
- Corrected context-pose entry condition: an ADVISORY_ONLY presencePASS with predictedCORRECT/PRESENT may now coexist with independent outline direction evidence; stateCORRECT is no longer a candidate veto. Explicit emptyFAIL, invalid/other authority and malformed PASS labels still abstain. No angle/confidence/distance threshold changed, raw votes untouched, no production authority promotion.
- Recomputed21 saved reports: VRM05failed131054 nowDIR?, normal/restored controls no new VRM candidates; missing cases preserved.427 regressions passed,2socket tests deselected, including4 entry-condition guards. Immediately captured fresh unchangedVRM05rotation131557→fresh_vrm5_nonveto/131635_369781: ONLYVRM05DIR? from boundary+context routes; finalUNKNOWN. No tuning/training on new capture; original failed report preserved. FlashOFF4000x3000/7mm capture and overview restored, no robot/conveyor motion/server restart/DB/API writes. Fresh normal restoration still needed; same-scene detection is not general qualification.
- Fresh VRM05 requested rotation131054→fresh_rotated_vrm5/131152_674429 FAILED: candidates0. Boundary axes-8.74616/-10.88707deg differ2.14091 (>2deg fallback agreement), while stateCORRECT0.951339 andROTATED0.026499 misclassify requested rotation. No threshold tuning/training; finalUNKNOWN not PASS. Source/provenance validation.json retained; other slots not newly independently certified. FlashOFF capture4000x3000 and overview restoration succeeded, no equipment motion/server/DB/API changes. VRM01/02/04 successes cannot be generalized toVRM05.
- Mixed-control restoration130637→mixed_restored_vrm1_vrm3/130744_436456: all displayed candidates0; stateCORRECT VRM01=0.992158/VRM03=0.987538. Both requested warnings clear without criteria/training changes. FinalUNKNOWN; source/user acknowledgement retained. Completes one mixed rotation/removal→restoration pair, not all-slot qualification. FlashOFF4000x3000 optical capture and overview restore succeeded; no robot/conveyor motion, server restart, DB or API writes.
- Fresh mixed control130020→mixed_vrm1_rotation_vrm3_empty/130119_988576: ONLYVRM01DIR? andVRM03MISSING?, matching requested/user-acknowledged rotation and removal. VRM01 stateROTATED0.841020 + PatchCore1.000 triggers existing corroboration; axes10.9541/13.1834deg. VRM03EMPTY0.999430. No collateral displayed candidates, finalUNKNOWN; unchanged criteria, no training/tuning. Source/labels saved in validation.json; restoration remains. Optical flashOFF4000x3000 and overview restore succeeded, no robot/conveyor commands, server restart, DB or API writes.
- Fresh normal restoration121831→fresh_restored_vrm4/121925_427494: all displayed candidates0; VRM04 axes0.895174/0.487309deg, stateCORRECT0.925456. New pair-confidence version therefore gave compound121532DIR?/POSE?→restored121831none without tuning between captures. FinalUNKNOWN; a successful candidate pair is not production qualification or a height measurement. Source hash/user-acknowledged restoration preserved in validation.json. FlashOFF optical capture/overview restoration succeeded; no motion/server/DB/API changes, no training.
- Refined candidate confidence gate to (boundary>=0.95 AND auxiliary>=0.20) OR (boundary>=0.90 AND auxiliary>=0.40), retaining context>=0.95, signed-angle/centre agreement, raw offset limits, explicit-empty abstention and ADVISORY_ONLY authority. This is deliberate development gate tuning from failed121116, not an accuracy guarantee or fusion-policy change. Both models observe the same RGB scene; no independent sensor claim.
- Replayed16 saved reports; VRM04compound controls nominatedDIR?/POSE?, normal/restored reports no new VRM candidate, knownVRM02missing retained.423 regression tests passed,2socket tests deselected, including7 confidence-pair guards.
- Immediately captured untouched compound placement121532 (flashOFF4000x3000, optical7mm) and inspected fresh_pair_confidence/121608_586113: ONLYVRM04DIR?/POSE?, finalUNKNOWN. Source/expectation in validation.json; no tuning/training on this fresh capture. One fresh repeat succeeds; need normal restoration and broader qualification, not repeated threshold changes presented as validation. Overview restored, no robot/conveyor motion, server restart or DB/API submission. Updated candidate code used by subsequent inspection children.
- Fresh unchanged compound-placement121116→fresh_compound_vrm4/121139_043296 FAILED reproduction: candidates0, finalUNKNOWN. ContextPRESENT0.994493, auxiliary confidence0.407853, boundary0.930313 below newly required0.95; signed outline angles both8.3659deg, centres~1.788px apart. Other gates cannot override confidence abstention. No tuning/training on this fresh check; prior same-image repair did not generalize even to this temporal repeat. Validation/source hash archived. FlashOFF optical capture and overview restoration succeeded; no server/DB/API or motion changes. Keep this as failure, not confirmed detection.
- User clarified115915 VRM04 is rotated AND seated on the left lip with right-side slot exposed. Corrected validation expectation to compound position/direction defect while preserving original failed output. Fixed stateEMPTY0.808 conflicts with separate RGB context PRESENT0.993426, boundary confidence0.973655 and visible body. This is not absence truth.
- Added candidate-only context_pose_codes: only ambiguous presence statusUNKNOWN, available RGB context>=0.95, boundary>=0.95, auxiliary outline>=0.20; the two outline centres agree within3px and signed vertical angles within2deg, both exceed configured angle tolerance+1deg. Additional POSE? requires raw CAD offset >=position tolerance+0.50mm (not common-bias-corrected displacement). Explicit missing votes, invalid or low-confidence context/geometry abstain. No stage vote, physical height claim, threshold promotion or right-wall clearance requirement. All outputs remainADVISORY_ONLY. These exploratory gates are tuned on the development control, not independently certified.
- Recomputed14 saved reports without mutating source dictionaries: only target115915 gains newDIR?/POSE?; existing VRM02missing/rotation retained and normal/restoration reports gain none. Full GPU replay context_pose_repair/120845_477747 confirms targetVRM04DIR?/POSE?, finalUNKNOWN.416 tests passed,2socket tests deselected including8 new finite/conflict/normal/raw-offset tests. No new capture/training, no server restart, robot/conveyor command, DB/API submission. New child inspections consume updated candidate route; independent fresh compound-defect/normal validation remains necessary. Source115915 is development data now, not independent holdout.

## 2026-09-09 VRM second rotation control fails

- Fresh cross-slot VRM04 requested rotation115915→fresh_rotated_vrm4/120026_970654 FAILED: displayed candidates0 despite visibly rotated target in reviewed image. State EMPTY0.808357/CORRECT0.072358/ROTATED0.119285; boundary axes7.253196/4.134620deg both below8deg and disagree >2deg. Heatmap responds but is not defect confirmation. This disproves generalizing VRM02 cycle to VRM04. User r interpreted as requested placement acknowledgement; physical rotation not measured. No rule tuning/normal relabel, finalUNKNOWN, validation.json/source hash preserved. FlashOFF4000x3000 capture/overview restoration succeeded. No robot/conveyor motion, server restart or DB/API changes.
- Completed VRM02 reinsertion115501→fresh_reinserted_vrm2/115631_445401: candidates0, CORRECT0.994540, EMPTY0.001686, finalUNKNOWN. Full same-setting sequence normal→rotation→restored→empty→reinserted gives0→DIR?→0→MISSING?→0; no additional displayed candidates in this five-capture cycle. No training/tuning. Source hash/labels retained; this concludes this single-slot candidate cycle, not calibration/production release across all slots, angles or lighting. Optical flashOFF capture and overview restoration succeeded; no robot/conveyor motion, server restart, DB or API writes.
- Fresh VRM02-only removal115009→fresh_missing_vrm2/115148_417384: sole displayed candidateVRM02MISSING?, state EMPTY0.9996958. Other displayed candidates0. FinalUNKNOWN because stage remainsADVISORY_ONLY; score is not accuracy/certification. Source hash and user-acknowledged removal recorded in validation.json. Same criteria, no training/tuning; flashOFF4000x3000/7mm capture and overview restored. No robot/conveyor movement, server restart or DB/API submission. Single-slot normal/rotated/restored/missing sequence is successful at candidate level, not all-slot release qualification.
- Completed fresh VRM02 restoration114642→fresh_restored_vrm2/114721_268661, same config/weights/criteria. All displayed candidates0; VRM02 CORRECT0.986213, axes0/-1.676926deg. Sequence normal113749(0)→rotation114223(VRM02DIR? only)→restored114642(0) responds correctly at candidate level. Every final remainsUNKNOWN; no full qualification claim. Archived validation/source SHA, no tuning or training on cycle. FlashOFF4000x3000 capture and overview restoration succeeded, no robot/conveyor motion, server restart or DB/API submission.
- Fresh controlled VRM02 rotation114223 after user acknowledgement (~10deg requested, not independently measured). Full GPU report fresh_rotated_vrm2/114305_740435 selects ONLY VRM02DIR?, finalUNKNOWN. Trigger is EXISTING stateROTATED0.799048 plus PatchCore1.000 corroboration, not new boundary route: boundary axes8.82038/10.90371 differ2.08333deg (>2 gate), confidence0.914186. Thus fresh target detection succeeded but does not independently qualify new fallback. Visually checked report; flashOFF optical4000x3000, overview restored. Source/provenance in validation.json. No thresholds/training changed, no server/DB/API or robot/conveyor motion. Normal→rotated pair now observed; restoration check remains.
- Fresh post-change normal repeat: flashOFF113749 optical4000x3000,7mm/69mm equivalent; overview restored. Full GPU report fresh_normal/113932_133868, alignment0.981594, all displayed candidates0 including VRM direction. Five VRM axis pairs remain near vertical (-3.419..0deg). Source hash/provenance recorded in fresh_normal/validation.json. No tuning/training on this image. Same physical normal placement as prior capture, not independent-placement/lighting coverage; finalUNKNOWN. Next needed is fresh controlled rotatedVRM, rather than more identical normal captures. No robot/conveyor command, server restart or DB/API submission.
- Follow-up repair: retained original EMPTY<=0.05/boundary>=0.90 advisory gate; added a candidate-only alternative requiring valid normalized three-class probabilities, CORRECT+ROTATED>=0.90 (EMPTY<=0.10), and stronger boundary confidence>=0.95. Both same-mask axes must still exceed8deg and agree within2deg. Explicitly this IS candidate gate tuning, not qualification; it does not promote weak evidence into final PASS/FAIL. Raw state/orientation votes remain unchanged.
- Recomputed candidates on7 saved reports, asserting source dictionaries unchanged. Both targeted VRM04 and previously missed VRM02 now nominate DIR?; current normal104704 retains zero VRM candidates. Other reports gain no new VRM direction candidate; existing missing nominations remain. These are reused development/review controls, not independent holdout. No training performed on normal104704, but it has now been consulted during candidate tuning and must not be claimed untouched independent release evidence.
- Full GPU replay of same142049 after repair: after_split_presence/20260909_113449_344092; finalUNKNOWN, VRM02DIR? displayed. Prior failed report/validation preserved. Regression408passed,2socket tests deselected; new tests cover split orientation, stronger boundary confidence, invalid probabilities and normal angles. No camera capture, robot/conveyor commands, server restart, DB or teammate upload. Subsequent child inspections use the added advisory route; socket containment and release authority remain unresolved.
- Paused manual wall calibration after user rejected ambiguous annotation. Replayed archived Sept5_142049 (explicit VRM02 expectedFAIL in vrm_position_range_audit) through current separated-CAD config and GPU, report vrm_direction_followup_20260909/20260909_112656_677812. No new camera capture or physical motion.
- Target VRM02 direction candidate is absent: axes8.392924/9.586922deg and boundary confidence0.955315 satisfy geometry gates, but state EMPTY0.086050 exceeds0.05 gate. CORRECT0.765421/ROTATED0.148529 remain uncertain. This is a FAILED target regression, not evidence of normality. Earlier VRM04 success is insufficient for direction authority. Saved validation.json; no threshold relaxation, training or promotion. Other candidates/slots not assigned new truth. FinalUNKNOWN and live server/API/DB unchanged.

## 2026-09-09 Fixed socket footprint prototype

- Operator reported accidental Enter without reliable boundary identification. Moved VRM04 annotation1788919919642393204 to socket_wall_annotations_20260909/rejected and marked REJECTED_USER_UNCERTAIN_BOUNDARY, usable_as_reference=false, runtime_enabled=false. Original coordinates/provenance preserved for recovery/audit only; exclude from calibration/training/validation. GUI had saved only this offline annotation and exited; no inspection configuration or server consumed it. No replacement edge guessed and no motion issued.
- Added operator empty-wall polygon annotation UI, initially VRM04 only. Existing prior single right-edge annotation is preserved, not copied between dates or extended to unobserved walls. UI uses verified archived empty-panel geometry/source hashes, native-coordinate conversion, undo/reset/cancel and unique append-only JSON saves. Selected polygons remain UNVALIDATED_WALL_ANNOTATION with runtime disabled; never self-labels or promotes. Five tests passed for coordinate conversion and degenerate/nonfinite/crossed polygon rejection; check-only verifies VRM04 origin9,317,size178x214. No training/model/calibration changes or equipment motion. Actual operator polygon selection is pending.
- Added generalized empty-only CAD edge probe over23 rectangular slots (six-sided IND skipped). Reads only unannotated empty panels and verifies trial hash; retains3 competing gradient peaks per side in an exploratory +/-15px window. Output normal_validation_20260909/empty_cad_edges.json. Across slots strongest right-edge offsets range -14.67..14.64px; several peaks lie near search limits or tie. These are search candidates, NOT measured physical wall offsets or a basis for global translation. Example SMD01 right peaks -13.23/+5.77px have identical strength2; VRM04 right +5.64/-0.36px strengths5/4. A unique wall cannot be chosen from maximum gradient alone. No calibration fitted, new capture or production changes. Three new pure tests cover competing peaks, coordinate origin, absent signal and nonfinite/window guards.
- Added compare_empty_cad_frame.py and executed it on user-labelled fully empty Sept5_134637 versus fresh normal Sept9_104704. Both separately use existing whole-board registration (0.980255/0.979478), with no per-part fitting. Generated25 native-pixel four-panel slot comparisons: empty original/CAD, occupied original/CAD, plus source/trial hashes in normal_validation_20260909/empty_cad_comparison. Inspected VRM04/PM02/SMD01 directly: projected CAD edges do not exactly coincide with visible grooves. Inner wall versus rim/shadow and height projection remain unresolved; no wall coordinates were automatically fitted or promoted. Historical empty image is NOT a new capture. Python compilation and8 footprint regressions passed; no live config, motion, camera, training, DB or server changes. Prior empty-wall ambiguity was reviewed rather than requesting another identical capture.
- Implemented socket_footprint.py and offline audit_socket_footprint.py: compare saved segmentation outlines against convex fixed CAD floor polygons in physical mm, preserving six-sided IND polygons. Reports signed clearance/max exit; no common component-derived offset, local fitting, tolerance enlargement or decision promotion. Invalid/missing polygons abstain; inside remains UNKNOWN because floor projection and silhouette do not certify physical seating.
- Replayed fresh normal104704 and archived VRM04 rotation142337 using identical CADa8puvcqm mapping. VRM04 max projected exit normal0.686mm versus defect1.381mm. However all25 normal silhouettes have some projected exit (0.177–1.446mm). Thus direct zero-exit gating would false-alarm; this prototype is NOT a replacement production criterion. Do not calibrate away the validation image residuals. Normal and defect outputs saved under normal_validation_20260909/footprint_trial and footprint_vrm_defect. Missing detections have no exit measurement, not zero clearance/pass.
- Eight geometry tests passed (boundary contact, rotated protruding corners despite inside centre, polygon order, scale, invalid/nonfinite/degenerate data and concave socket rejection). Visually checked yellow CAD/cyan measured normal overlay. Live pipeline/server/thresholds remain unchanged, no fresh capture, training, robot/conveyor commands, DB writes or teammate upload. Need board/height-aware wall calibration and independent controls before replacing centre diagnostics.

## 2026-09-09 Fresh all-normal validation

- Follow-up read-only diagnosis: seven raw pose flags all exceed the shared0.75mm radial centre threshold, not3deg angle threshold. Component-derived common bias(+0.259146,-0.610942)mm increases PM02 offset0.666→0.962mm; blanket removal would instead flag GPU/sixHBMs and others on the same normal-labelled scene. Recorded numeric comparison and limitations in normal_validation_20260909/pose_diagnosis.md. No tolerances/authority changed or labels fitted; socket containment is not established by this centre test. This is diagnosis, not completed corrective validation.
- User replaced HBM with normal parts after declaring normal placement. Captured flash-OFF S22 optical still104704 (4000x3000, 7mm/69mm equivalent), restored overview, and inspected with isolated separated-CAD config a8puvcqm. Source SHA256 and explicit user-label provenance are preserved in runtime/inspection/normal_validation_20260909/normal_104704_label.json; no training or tuning on this frame.
- Report104727_014632: registration0.979 (rounded), zero displayed candidates, PatchCore available for25/25. Seven raw auxiliary pose flags remain (PM02/04, SMD01, VRM01–04); five VRM seating checks disabled. Heatmap response remains visible independently of selected candidates. Final UNKNOWN, not PASS; no qualified authority promotion or full normal acceptance claim.
- No robot/conveyor motion, server restart, API upload, DB write or camera-setting persistence change. One fresh normal scene cannot qualify defect sensitivity, cross-lighting behaviour, or all required stages. Existing inspection files were preserved.

## 2026-09-09 VRM boundary rotation advisory repair

- Added a DIR? display candidate when VRM boundary min-area/PCA axes both exceed 8 degrees from vertical, agree within 2 degrees, boundary confidence is at least 0.90, and independently reported EMPTY probability is at most 0.05. These axes come from the SAME mask, not independent sensors. Missing/nonfinite/unavailable evidence abstains. No changed PASS/FAIL authority, thresholds for other parts, or per-part alignment; final fail-safe fusion remains unchanged.
- Recomputed the new predicate over five existing separated-CAD reports: known Sept5_142337 VRM04 rotation control is selected (axes -10.7625/-10.1063 degrees); no other VRM is newly selected in the other four reports. This is an archived development replay, not fresh capture or a full labelled normal/defect qualification. Existing reports/images were not overwritten; full image inference was not rerun for this change.
- Regression: 387 passed, 2 socket tests deselected, including eight new guard tests. Smaller rotations, seating/position defects and unseen lighting remain unqualified. Next inspection child uses the added candidate rule; no connected server restart, camera change, robot/conveyor command, DB write or teammate upload was performed.

## 2026-09-09 CAD geometry and provider crop separation

- Additional archived regression: Sept6_211735→102606_490894 preserves user-labelled normalIND01 with no displayed candidate and direction-defectIND02DIR?/SURFACE?; HBM04/08PINS? additional unverified flags. Sept5_142337→102819_430529 misses targeted known VRM04rotation as a displayed candidate: pose rawFAIL, presence/orientation low-confidenceCORRECT UNKNOWN, boundaryUNCERTAIN. Other largely absent components nominate missing, but their truth was not newly verified. This is a failed VRM rotation control, not successful validation. No thresholds changed to force detection; both finalUNKNOWN. No new capture, training, motion/server/DB changes.
- Controlled-defect GPU replays with same separated config: September4_133042→102130_823024 retains SMD02POSE?/SEATING?; collateral HBM01/06PINS? unverified. September7_134016→102256_807631 retains GPU DIR? and HBM03MISSING?. Historical SMD01 seating in that mixed image is not nominated under previously approved micro-seating deferral; do not count as full mixed-case success or newly restored coverage. Both UNKNOWN, archived development controls not independent holdout, no new capture/motion/DB/server changes. This verifies retention of three targeted defect types only, not all25-slot accuracy.
- Added optional `provider_crop_config` to isolated CAD trials. Registration, learned crops, pin references and VRM boundary inputs use original fixed provider configuration; CAD slot centers are separately projected in that same board frame for auxiliary pose. No local part-following alignment, threshold relaxation or changed fusion authority. `geometry_reference.json` explicitly records geometry versus provider config. Live/default config remains unchanged.
- Executed GPU full replay of095829 photo under `cad_yellow_trial_a8puvcqm/results/20260909_101708_818258`: only displayed candidates HBM01/08PINS?. All8HBM pin stages now load compatible references; all5VRM boundary stages return UNCERTAIN rather than crop-outside-image UNAVAILABLE. No SMD03 or IND surface display candidate in this frame. Availability recovery is not accuracy validation: finalUNKNOWN, no certified pin-single-loss or VRM containment claim.
- Regression379passed,2socket tests deselected. No new camera capture, equipment command, server restart, DB or external upload. Full defective/normal holdout validation remains incomplete; additional controlled defects needed before production authority. This record covers runtime connection recovery, not a claim that all inspection models are complete.

## 2026-09-09 Unity pose reference binding correction

- Fresh user-requested capture095829 flashOFF4000x3000/7mm, overview restored, no movement. Previous CAD trial replay100002_768939 repeated SMD03POSE? at1.286163mm and SMD05POSE?, plus IND01/02SURFACE?. Found integration error: CAD crops changed but auxiliary pose consumed YOLO's old expected center. Previous yellow trials therefore were mixed-reference experiments, not fully CAD-referenced position inspection.
- Added opt-in `auxiliary_pose_use_active_slot_centers` to generated CAD trials and `bind_active_slot_centers`: copies evidence, retains measured centers and original expected centers, uses fixed active slot centers before shared-bias estimation/pose. No part-following normalization or threshold relaxation. Existing live/default config behavior unchanged. Association still uses YOLO slot IDs; normalized_slot_distance remains original-provider evidence, not a recalculated CAD distance.
- Corrected trial `cad_yellow_trial_19uf3qeu/results/20260909_100409_744152` on SAME095829 photo: SMD03 expected center1495.256,639.485 vs old1490.417,648.883; transverse0.739588mm, angle0, no SMD03/05 displayed pose candidate. Remaining IND01/02SURFACE?, finalUNKNOWN. Previously noted changed-crop HBM reference and VRM boundary limitations persist; no full release/accuracy claim. No server restart, DB writes or teammate upload.
- Regression379passed,2socket tests deselected. Explicit tests preserve measured center/input and do not fabricate missing detections. Runtime code addition is default-off; no live criteria promotion. User prefers Unity geometry going forward, but this trial is not yet a deployable replacement for all learned-provider crops.

## 2026-09-08 Unity socket face extraction

- User-requested full yellow-CAD trial executed on same203448 photograph, isolated config under `cad_yellow_trial_7fg10skq`, results204422_114985. Added `prepare_cad_trial.py`: type-constrained bijective nearest fixed-slot assignment with3mm rejection; replaces candidate crop centers/bounds with corrected CAD polygons, preserves polygon metadata, disables only trial physical/reference-center overrides. IND six-sided floor is bounded by rectangular crop, not polygon-clipped learned input. Live config/server unchanged.
- GPU full inference completed UNKNOWN, all25PatchCore available; three displayed candidates IND01/02SURFACE? and SMD02POSE? vs baseline seven. SMD02offset0.842612 vs baseline0.846631 (still above0.840), surface0.251820 vs0.0. Reduced warning count is NOT improvement: HBM pin reference now UNKNOWN/HBM_PIN_REFERENCE_REQUIRED from changed crops, all5VRM boundary checks unavailable (`Fixed crop outside image`), and learned crop distribution changed. Reviewed report visually; report exposes missing checks and advisory status. This trial cannot replace production baseline or claim fewer defects. No new photo, motion, server restart, DB write or teammate transmission. Separate output avoids modifying previous API evidence.
- SMD02 restoration capture203448 verified visually (`smd02_current_restored_lyeti2gu`); flashOFF4000x3000 optical7mm, overview restored. Diagnostic helper now accepts explicit empty/restored preparation, avoiding false empty provenance. GPU-backed full replay203549_008851 completed UNKNOWN: SMD02 PRESENT0.998526, transverse0.846631 vs0.840 produces POSE?, surface0.0, angle0.0. Additional candidates HBM01/05/06/07/08PINS? and IND01DIR? retained in full report, not asserted correct. No whole-boardPASS claim. User-prepared normal SMD02 still warns; CAD containment has not resolved this. No runtime criteria/coordinates, server restart, robot/conveyor motion, training or DB changes. Current photograph, not all historical observations, used for this result.
- Repeated current empty-SMD02 capture203232 (flashOFF,4000x3000,7mm; overview restored), SHA42e7ff1ad4de10e41538b52252d6d77b6f6c0c9054aca5f8c3049fc2a5ebd85d. Probe/visual review in `runtime/inspection/smd02_current_empty_j5dt1olc/`, alignment0.978692. Top strongest791.5px repeats; right strongest switches1526.5→1522.5 between two real captures while both peaks persist; bottom880.5→878.5, left1473.5→1452.5. Repetition does not resolve which dark/bright edge is physical inner wall. No validated four-sided adjustment obtained; do not fit nominal region to strongest peak or call absence of exit PASS. End empty-reference collection at this point rather than repeatedly requesting identical captures. CAD is retained as fixed candidate geometry, no production replacement. User may restore SMD02. No equipment motion, DB write or persistent camera setting change.
- Actual flash-OFF S22 capture20260908_202746 after user acknowledged SMD02 removal: 4000x3000,7mm/69mm equivalent,3.5x; overview pause/resume completed, no conveyor/robot movement command. Sandbox ADB listener failed before device access; approved host retry succeeded. Added/executed `probe_current_smd02_empty.py`, source SHA b1ed81799fa3574a0ff07e45b74eb6f9c72438bbe42bc362b8fe86511f110a50, alignment0.977361. Visually inspected `runtime/inspection/smd02_current_empty_lac0mzlg/comparison.png`, confirming empty recess. Strongest candidate coordinates L1473.5/R1526.5/T791.5/B880.5; right secondary1522.5 nearly coincides with CAD1522.891, illustrating inner/outer edge ambiguity. Left evidence remains weak. No certified four-wall update from one frame, no training label or runtime verdict changes. Existing camera settings preserved; diagnostic capture only, no DB/API production submission.
- Extended empty-SMD02 audit with raw-gradient edge candidates in fixed CAD-neighbourhood windows, preserving three competing peaks per side rather than declaring the strongest a wall. Three SHA-verified empty references passed registration. `runtime/inspection/smd02_wall_pdr179yj/audit.json`: strongest right/top medians1522.5/791.5px, each spread1px; left1452.5 spread20px and bottom872.5 spread9px. Left maximum can occur at search boundary; no trustworthy four-wall correction can be inferred. This does not justify widening to fit current normals, whose bright contours already extend past the candidate right boundary. A current empty SMD02 capture is needed to distinguish outdated alignment/reference from printed wall/shadow before any runtime calibration. No threshold/coordinate update, capture, motion, restart or DB write.
- Added/executed `audit_smd02_cad_containment.py`, eight archived cases, corrected positive OBJZ/imageY projection. One same-type face is selected once against fixed nominal slot with distance/ambiguity guards; no selection/recentering from detected component. Artifacts: `runtime/inspection/smd02_cad_containment__4ukgn0w/`. Threshold130 bright-contour maximum outside distance: normal5.109–6.109px, controlled lip9.621px. Across100/130/160 normals4.109–7.109 versus defects8.621–10.621px. CAD projection still puts normal silhouettes outside: not a calibrated wall or sufficient production separation. No zero-exit FAIL rule, fitted threshold, runtime change, new capture, equipment command or DB write. Bright pixels may not represent full part body; planar containment cannot certify height. All eight diagnostic probes completed, no accuracy/holdout claim.
- CORRECTION: user identified reversed vertical projection. Changed diagnostic imageY mapping from minus OBJ Z to plus OBJ Z, preserving imageX and all runtime settings. Executed and visually checked `runtime/inspection/unity_socket_projection_9mqatqd5/comparison.png`: SMD column/horizontal lower slot and lower-right inductors now correspond to photographed layout. Earlier assertion of a different physical SMD/inductor distribution was unsupported; the mismatch was caused by the preview transform. Historical preview retained for traceability, not a valid calibration. Precise wall geometry/slot IDs remain unvalidated. No capture, motion or server changes.
- Added/executed `preview_unity_socket_projection.py`; visually inspected `runtime/inspection/unity_socket_projection_y15v6p55/comparison.png`. Left shows unmodified CAD floor polygons under explicit X-handedness hypothesis and physical board scale; right shows active nominal component ROIs. Archived194313 image, no new capture. GPU/HBM/PM/VRM align approximately, but raw CAD SMD/inductor distribution disagrees visibly (inductors project upper-right rather than lower-right). This confirms raw OBJ placement cannot replace physical overrides. No slot-local recenter/rotation or production calibration was applied; exact boundary agreement remains unverified. Artifacts and audit are diagnostic only.
- Added read-only `extract_unity_socket_candidates.py` for original motherboard OBJ horizontal faces. Retains face indices and actual polygon vertices, source SHA and explicit10x OBJ-to-mm conversion; matches existing nominal socket dimensions within0.02mm rather than constructing enlarged component boxes.
- Actual source extraction returned25 candidates: GPU1/HBM8/PM4/VRM5/IND2/SMD5. Inductor candidates are six-vertex polygons, not assumed circular rectangles. These are dimension-matched floor-face candidates, not topological certification of printed inner-wall edges. No slot identity assignment, mirror transform, physical override replacement or clearance verdict is yet authorized by this evidence.
- Two synthetic parser checks passed (negative OBJ indices/dimension ordering and sloped-face rejection). Actual file extraction completed. Physical SMD/inductor overrides and existing camera mapping must be reconciled before overlay/runtime adoption. No camera capture, equipment command, server restart, training or DB change.

## 2026-09-08 SMD2 position overlap audit

- Added and executed `audit_smd02_empty_wall.py` on three explicitly empty, SHA-verified September2 sources. Board registration0.977374–0.979359 accepted all; native fixed crop origin(1430,754), nominal component geometry(center1495.597,839.818;43.841x78.037px). Compared raw/nominal-overlay/localCLAHE in `runtime/inspection/smd02_wall_8jcudkpx/comparison.png` and visually inspected it. Nominal component rectangle is not the full socket boundary; top/right recess edges are visible but left/bottom blend with print texture and shadow. Presence labels cannot certify an inner-wall polygon or transfer subpixel clearance to current captures. No runtime coordinates or thresholds changed, no new capture/motion/server restart. Diagnostic artifacts only, not training or production result replacement.
- Extended the same audit with fixed-board-window raw-grayscale bright-silhouette probes at100/130/160. Across five recent normal-placement images, threshold130 boxes have left1480–1481, top796–798, width48–49 and height83–84px: substantially more repeatable than the segmentation-derived offset warning. Three historical lip controls have left1458, top791–792, width54–55, height84–85. This is directional silhouette evidence, not proof of socket containment: an empty-slot wall measurement and matched rightward defect controls remain necessary before runtime replacement. All eight image probes executed successfully; no local part alignment, runtime decision change, new capture or motion.
- Added read-only `audit_smd02_position_overlap.py`: replay eight archived SMD02 rows through current candidate logic, preserving source IDs and image hashes. No fitting, retraining, capture, immutable report edits or production criterion changes.
- Five recent user-declared normal-placement captures measured transverse offsets 0.759281–0.887706 mm; three controlled September 4 lip defects measured 0.791456–0.873718 mm. Ranges overlap: increasing a single absolute-offset threshold is not a validated solution. Current normal rows nominate POSE? in 3/5; all three historical lip defects retain SEATING? through independent area/appearance evidence.
- Normal areas 3933.5–4235.5 px² and appearance scores 0.0246–0.1633 differ from these historical defects (4623.5–4667 px², 0.3051–0.4036), but this does not validate suppression of planar displacement: no matched rightward planar-defect control is included, and dates differ. Preserve current advisory status and UNKNOWN; no PASS promotion.
- Audit executed successfully against all eight reports. No camera capture, robot/conveyor motion, server restart, DB write or external upload. These are developmental archived results, not fresh inference or an independent accuracy estimate.

## 2026-09-08 SMD1 micro seating scope deferral

- Restoration request7eb8720a-f664-46ae-bd62-9172bea1697f captured194213/194304. SMD1PRESENT0.999884/0.999796 with no candidate in both; missing/restoration control retained after deferral. Collateral SMD2position0.851/0.888mm against0.840 both; SMD3position0.848 second, PM2position second, IND2surface0.443 against0.439 first. Do not report only successful target or assert whole-boardPASS. FinalUNKNOWN; no parameter changes this verification. Stored non-training provenance, no equipment motion/DB writes.

- Post-change actual API requestb839b77f-caee-4434-aa5e-7a7ef5cdd4b3 captured193735/193827 after requested SMD1 removal. Both EMPTY0.99999964 and MISSING? retained, finalUNKNOWN. Additional SMD2 position warning in both, SMD3 in first only, HBM pin warnings excluded from placement audit. These collateral warnings remain unresolved; not a clean whole-board result. No movement/DB writes or normal training. Non-training request provenance preserved.

- User continued after proposal to defer micro seating and focus missing/clear displacement/rotation. Explicitly deferred SMD1 appearance/area/weak-outline micro-seating nominations only. All four original trigger booleans retained in smd01_lip_evidence_review with UNKNOWN and SMD01_MICRO_SEATING_DEFERRED; raw stage data unchanged. Existing presence, direction and independent displacement logic remain active; other SMD slots and HBM unchanged. Fusion contract documents scope reduction: actual subtle height-only defects may no longer display a seating warning; this is not a detection improvement or PASS.
- Updated scope-specific tests to retain raw defect triggers without rendering, preserving stage immutability. Saved192040report replay only HBM pin candidates, explicit SMD1 UNKNOWN review retained. No camera capture, learned-model/threshold change, server restart, motion, training or DB writes; next inspection child loads code. Earlier wall and score instability evidence remains in history. Normal/defect micro-height separation is unresolved and intentionally deferred.

## 2026-09-08 SMD1 boundary alternative rejected

- Added read-only audit_smd01_current_boundaries.py. Current normal192040/192131 fixed-window bright outlines both xywh[65,39,80,48] at130 and[65,40,79,47] at160. Archived subtle-defect120941 gives[65,37,82,51] at130; clear lip132108[63,31,83,51]. No local recenter/rotation applied.
- Prior empty-reference candidate walls are not calibrated inner walls: top spread9px, left12px across3references. This exceeds the2px subtle top-edge separation; transferring that wall does not solve normal false nomination or measure height. Rejected direct wall-based replacement, kept runtime unchanged. First read-only invocation lacked ROS env, corrected by sourcing Jazzy. No new capture, training, equipment motion, server restart or DB writes. Current weak appearance rule remains unresolved, not certified fixed.

## 2026-09-08 SMD1 deterministic replay diagnosis

- Compared192040/192131 normal repeats without recapture: aligned SMD1 centers differ0.297px, raw-y -0.770005/-0.768319 algorithm-mm, but surface0.172407/0.115099 changes the .14 nomination. Both raw stills EXIF1/60s ISO200 Flash0 focal7mm; fixed crop63x112 gray means117.839/117.863, Laplacian variances218.247/280.166. Global warp differs. These support local image/resampling/detail sensitivity, not proven autofocus failure, illumination cause or physical movement.
- Re-inferred identical first input on GPU, report192535_207790: identical inputSHA b02ea96feaa2d52dc539ad11f43c75f63ae4d5307813fc3ced209f8d5c17019f, identical SMD1score0.17240741848945618 and center. This one repeat does not show stochastic inference drift; weak appearance-based seating nomination remains unvalidated. No further threshold/registration changes or training. No new capture, server restart, motion, upload or DB write. Further correction must not normalize slot-relative errors or turn ambiguous height into PASS.

## 2026-09-08 SMD1 corroboration fresh repeat instability

- Request1b799771-6f84-4923-907c-9f5ce3b34262, OFF192030/192121 completed. Same declared normal placement, no reported reposition. First SMD1 surface0.172407 triggered SEATING?, second0.115099 did not. Both retain HBM pin candidates; no other non-pin public candidates. FinalUNKNOWN. Earlier archived23case agreement did not transfer to stable fresh normal specificity.
- Preserve both attempts and non-training provenance; do not cherry-pick clean final frame or raise score threshold again from this sample. No further threshold/model changes this turn. Capture/inspection only, no motion command, DB write, server restart or training. Need inspect capture/registration and local feature variability against actual subtle-defect controls before declaring fix complete.

## 2026-09-08 SMD1 weak appearance corroboration revision

- User explicitly confirmed current SMD1 normally seated. Traced repeated false SEATING nomination to signed raw-y outside frozen envelope plus weak PatchCore0.115/0.116; prior normal recovery0.129 also flagged. Retained raw position bounds and zero deadband because prior1px deadband missed labelled subtle defect.
- Changed only SMD01 small-lip appearance corroboration floor0.10->0.14 (including independent-outline fallback). New audit_smd01_surface_corroboration.py replays23archived labelled reports with image SHA verification, temporary in-process rule comparison restored in finally. Three normal false nominations clear; all labelled defect nominations retained, including subtle120941case(score0.218). This threshold was chosen using these data; not independent validation, physical clearance or general defect guarantee. Low-score real defects may still be missed. Raw measurements/fusion remain unchanged and UNKNOWN; no relabelling or normal training.
- Regression375passed,2socket cases deselected. First audit lacked ROS environment; reran after sourcing Jazzy successfully. Saved-image GPU replay191350_566317 on current190434capture completed with all25PatchCore providers available. No new capture, motion, server restart, DB write or upload. Per-request children load revision on next request. HBM pin work left untouched and excluded from placement assessment.

## 2026-09-08 normal placement audit excluding HBM pins

- User declared all parts normally placed with defective HBM pin specimens retained. Captured requestd24beed9-4df3-422c-8707-2f67f6918df8, OFF190342/190434; both reports show only SMD1 SEATING? among non-pin public candidates. Raw-Y -0.7528/-0.7231mm and PatchCore0.116/0.115 trigger SMD01_SMALL_LIP_ADVISORY. Against user placement truth this is false nomination, not confirmed raised height. Other raw diagnostic flags remain; absence of public warning is not PASS.
- HBM pin results retained but excluded from this placement evaluation. Prior user correction additionally establishes HBM6/7 intact and HBM3 upper-left one-pin absence; earlier pin nominations/miss must not redefine those labels. This board is not whole-board normal training material.
- OverallUNKNOWN, automatic two captures completed, no runtime threshold changes, training, server restart, robot/conveyor movement or DB writes. Non-training provenance stored. Next targeted task is SMD1 seating-rule specificity with known normal/defective controls, not blanket suppression.

## 2026-09-08 flash off on physical comparison

- Captured separate trial folder runtime/inspection/flash_pair_20260908_trial1: OFF185416 and ON185507, 4000x3000 telephoto originals and1600x1266ROIs. EXIF confirms Flash0 versus1, both7mm; OFF1/60s ISO200, ON1/30s ISO50. Overview restored after each; no motion command, API result replacement or training. User asked to keep same placement; no manual reposition performed by agent.
- Visual review: ON accentuates printed texture/specular edges, without clear recovery of the shadowed HBM pin rows; OFF white pins are generally more distinct. This pair does not justify automatic dual-flash fusion. Not a calibrated contrast study: autoexposure differs and independent ROI warps differ. No PatchCore inference on ON, no classification or threshold changes. Keep default OFF; pair retained for review, not normal training.

## 2026-09-08 individual pin fresh API repeat

- Request5c83b772-0c64-496b-950e-af5d1eee1f45 completed two actual captures184340/184431, final report184441_519722. Both nominate HBM1 long-gap and HBM8 right points166/182. However HBM5/6 left candidates occur, and HBM7 left appears in second frame; new physical truth for these slots unconfirmed. Final also nominates SMD1 seating. Hence target repeatability demonstrated but no robust specificity/release claim; previous clean112crop replay did not predict new live collateral candidates.
- API returns matching evidence image and finalUNKNOWN; original files retained with non-training provenance. No threshold changes, training, server restart, motion command or production DB write. Need side-visibility/photometric corroboration and unchanged-part confirmation before promoting pin decisions. This run is not normal-only validation.

## 2026-09-08 individual HBM pin candidate circles

- Reused legacy inspect_leg_side in hbm_individual_pins.py with same-slot strips, no profile registration, no fallen-shape decisions, near-absence ratio0.05 (legacy0.2 also flagged irregular left HBM8). Right band extended through lower pin row; left dot corner excluded. Require three visible pin anchors or abstain. This is developmental tuning on the current sample, not independent single-pin validation.
- Replay of112presumed unchanged HBM controls from7earlier scenes produced no missing-pin candidates. Both two-pin sample captures identify HBM8 right reference peaks8/9 and HBM1 right long-gap candidate points. Actual exact physical pin numbering not certified. Integrated advisory evidence and crop-coordinate red circles into original/overlay report panels, leaving PatchCore heatmap unmodified and final authority unchanged. Same pinned reference checks remain; totally dark/hidden sides not certified.
- Tests95existing/focused pass plus2new synthetic individual-pin tests pass. GPU saved-image replay184013_101811 shows HBM1/HBM8 PINS? circles and pre-existing SMD3 position candidate, all25PatchCore providers available, finalUNKNOWN. No new capture, motion, training, server restart, external upload or DB writes; next child uses code. Archived API result unchanged. Further print/pose/light variation and one-pin physical test still needed; D435 legacy workflow not restored.

## 2026-09-08 pin sample identity correction and legacy review

- User clarified request91fc40eb scene: previous long-gap HBM8 part moved to HBM1; HBM8 replaced with two-pin-loss part. Updated provenance only. HBM1 nomination is supported, not established false positive; HBM8 miss remains. Prior entry's unconfirmed non-target truth is superseded, not its original detector output.
- Reviewed full_board_inspector.py inspect_leg_side and defect_points_px rendering: legacy method detects expected white-profile peaks, compares local evidence ratios and draws circles for missing/fallen candidates. Synthetic missing-pin/profile-shift tests exist; their existence does not validate present physical samples. Appropriate next experiment is reuse of per-pin evidence/point rendering within advisory hybrid, not legacy overall FAIL/D435 dependency or irregular-shape criteria. No runtime changes, new capture, motion, server restart or DB writes this turn.

## 2026-09-08 two pin loss prospective failure

- Captured request91fc40eb-5907-40ba-be43-0fe0f9a2a4b8 with user-declared two-pin-loss HBM in requested slot8. Exact cut positions not explicitly provided. Two captures183014/183106, reports183024_463061/183116_180629. Both miss target HBM8 pin candidate; both nominate HBM1 instead (its physical truth unconfirmed). Final adds SMD3 position candidate; overallUNKNOWN. This disproves any general two-pin sensitivity claim; earlier112negative controls do not establish robust live specificity.
- Normal pipeline automatic recapture used, no manual movement/robot/conveyor command, DB write, server restart, threshold change or training. Original reports immutable, non-training provenance added. Need confirm non-target HBM1 state and improve pin localization/visibility before broader use; do not lower global thresholds to fit this sample or relabel it normal.

## 2026-09-08 HBM pin advisory integration

- Replayed112HBM crops from14captures/7earlier controlled scenes (normal-board, GPU missing/restored, PM1 missing, VRM3 missing, IND1 missing, SMD1 missing) against the pinned174947reference: zero pin candidates. These are same-session presumed unchanged HBM controls, not112independent or individually certified pin normals. The two known partial-loss crops continue to nominate HBM8 right only. No additional threshold adjustment this turn.
- Wired inspect_hbm_pins into live main.py as ADVISORY_ONLY. Reference manifest pins each slot image by SHA256; missing/corrupt/reference-path errors, invalid alignment and uncertain/empty presence abstain. Output PINS? flows through existing suspect display/export; cannot assert final PASS/FAIL. No learned RGB preprocessing, local geometry normalization or GPU-pin changes. Fully invisible bands, other slots' actual pin defects, shifted/rotated packages and new lighting remain unvalidated.
- Tests:79focused tests pass; broader hybrid/integration368pass,2localhost tests deselected. Runtime replay first hit sandbox GPU restriction (182133report has missing PatchCore; not accepted as full verification). Escalated GPU replay182324_695326 completed with all25PatchCore surface providers available, exactly HBM8 PINS? candidate, full heatmap displayed, overallUNKNOWN. Same saved180638input, no new capture. Existing API artifacts untouched; next per-request child loads changes without restarting connected server. HTTP roundtrip of new output not performed this turn.
- No server restart, camera changes, actual robot/conveyor commands, training, external upload or DB writes. Logs grouped; fusion contract documents advisory scope and deployment reference requirement.

## 2026-09-08 HBM pin band offline prototype

- Added hbm_pin_bands.py and five passing synthetic tests. Local CLAHE plus raw grayscale/saturation corroboration measures long empty spans in fixed side bands; same-slot normal reference required. No individual pin counting, local recentering, automatic PASS, or authority promotion. Missing/invalid reference, absent component and fully dark bands abstain.
- Initial absolute-darkness prototype falsely nominated normal HBM1/4 due to visibility. Reference-relative revision compared saved normal174947 with normal174856 and defects180556/180647: normal repeat8slots no candidates, each defect repeat nominates HBM8 right only; other7slots no candidates. Same-session developmental data used to tune thresholds, NOT independent validation. Left-side HBM8 gap increase0.3397 is close to provisional0.35 limit; slot shifts/lighting remain confounders. Right gap increase0.6795 versus baseline supports this particular sample.
- Deliberately NOT connected to live fusion/API yet. Existing HBM pin stage remains UNAVAILABLE pending broader shifted-normal/defect tests, reference provenance/quality gating, and robust localization. No new capture, model training, server restart, motion or DB writes. Existing archived results unchanged.

## 2026-09-08 HBM partial pin loss controlled capture

- Normal reference request343a8303-eaab-408c-ae62-498b84651d5f and partial-loss requestf176f77d-2750-4189-9e94-012008abd471 retained with non-training provenance. User clarified actual sample: usual logo colors, HBM8 upper-right pins cut, lower-right pins retained; not total pin absence. Reversed-logo spare was never captured, so no deletion performed.
- Actual S22 capture plus automatic UNKNOWN recapture completed, final ROI s22_inspection_roi_20260908_180638.png and report hybrid_fixed_slot/20260908_180647_840917/hybrid_report.json. Visual source review shows missing upper-right pin band. Current output UNKNOWN, zero public candidates; HBM pin provider remains UNAVAILABLE. Surface score rose from0.6244767 to0.9472615 but does not establish defect localization or probability; direction became ambiguous. This is a missed pin nomination, not successful pin validation.
- No model/threshold/authority changes, training, server restart, robot/conveyor motion, external upload or DB writes. Pin-specific evidence extraction and independent normal/defect validation remain required; individual irregular printed-pin shapes must not be assumed defective.

## 2026-09-08 comprehensive available verification report

- Consolidated bounded validation in docs/INSPECTION_VERIFICATION_STATUS_20260908.md. Main hybrid/API/export/trigger suite373passed including localhost sockets; inspection/slot test_*.py93passed (overlaps main suite); segmentation in dedicated OBB env54passed with Axes3D warning; Node viewer1passed. Initial broad wrong-env collection errors documented, not reported as application fixes; manual *_test.py runner excluded from unit-test collection explicitly.
- Prospective audit9/9 target candidates match but one session/representative slots only. Latest reviewed report106advisory,8HBM pins unavailable,5VRM seating disabled. Full release remains incomplete; no authority promotion, fresh capture, production server restart, motion, external upload or DB writes. Requires physical/independent evidence and teammate hold validation, not merely passing software tests.

## 2026-09-08 prospective target audit consolidated

- Added bounded read-only audit_prospective_session.py for nine explicitly selected missing/reversal controls. Checks completed request identity, non-training role, artifact paths and available prior SHA hashes; computes hashes where not previously recorded without claiming prior integrity verification. All9 final target candidates agree (6 representative missing,3 reversal); original collateral warnings retained. Two captures per scene are not independent scenes; same-session data only.
- No current-provider rerun or new authority, model/threshold changes, capture, motion, server restart or DB write. This is target agreement, not overall accuracy: normal false warnings and other slots/lighting remain outside the count. Overall PASS remains blocked by unvalidated mandatory providers/capture quality. Do not solve deadline pressure by flipping validated flags.

## 2026-09-08 demo manufacturer metadata

- Registered user-approved GPU NVIDIA, HBM SK hynix, PM Texas Instruments, VRM Infineon Technologies, IND TDK, CAP Samsung Electro-Mechanics in handoff configuration. Added manufacturer/basis to exported slots and findings; explicitly demo-assigned, not image inferred or physical origin verified. Preserved legacy PM part number with demo-reference basis; no new invented part numbers.
- Export/API tests48passed,1HTTP excluded. Decision/authority/IDs unchanged; additive fields require strict receiver schema accommodation. Existing server not restarted (cached exporter may require restart before serving new fields); immutable old results unchanged. No capture, motion, upload or DB write. Handoff documented in docs/DEMO_COMPONENT_MANUFACTURERS.md.

## 2026-09-08 user-approved VRM socket seating policy

- User replaced right-wall1mm inspection requirement with fully seated anywhere inside socket. Updated contract/scope/docs; robot safety and fusion authority unchanged. Runtime removes RIGHT-only nomination, preserves raw boundary evidence and existing rotation/missing/pose/seating checks. Filtered stage remains UNKNOWN with socket_seating_verified=false; not a new containment/height detector or automatic PASS.
- Saved162155 report replay retains SMD1MISSING and removes VRM3RIGHT-only candidate. Original reports/API responses unchanged. Tests370passed,2socket tests excluded; covers retained ROT/SEATING, immutability and idempotence. No capture, training, motion, server restart or DB write. New children apply policy; uncertain seating and other false warnings remain unresolved.

## 2026-09-08 empty-slot direction abstention

- User acknowledged SMD1 normal restoration; no new photograph taken or certified from that acknowledgement. Added orientation abstention when presence predicts EMPTY: status UNKNOWN, advisory authority and zero confidence with original direction evidence retained under raw_orientation_evidence. Other presence states, missing candidates, thresholds, model weights and fusion contract unchanged. This avoids calling a background dot a component direction; it does not certify presence or hide raw evidence.
- Saved-stage check on HBM8 missing153621 changes background direction PASS to UNKNOWN; HBM8 reversed154202 PRESENT retains FAIL/WHITE_DOT_AT_UPPER_RIGHT. No new inference or independent accuracy claim. Regression369passed,2socket tests deselected. No server restart, capture, motion, upload or DB write. Next child uses change; immutable earlier API results retained. VRM3 position and SMD1 seating false-warning questions remain unresolved.

## 2026-09-08 SMD1 missing control and representative sequence

- Initial API request returned503 before capture. Existing server still running; later read-only ROS samples arrived=true/moving=false. New request14fad7b2 accepted without restart or readiness bypass, captured162056/162146. Final SMD1COMPONENT_MISSING (EMPTY0.9999994), inductor1 PRESENT and BLACK_MARKER_DIRECTION_OK, plus unresolved VRM3POSITION_ERROR. Fused UNKNOWN.
- Hash-bound non-training provenance saved. Six component types now each have one representative missing scene matching selected target; GPU/HBM8/inductor1 reversal controls matched. This small same-session sequence does not establish all-slot/lighting accuracy or authorize promotion. Preserve SMD1 normal seating and VRM3 position false-warning evidence; no threshold/weight changes, production DB association or motion. Actual camera/API/inference and read-only ROS only.

## 2026-09-08 inductor1 reversal control

- User acknowledged inductor1 restored180. Existing API test857570d3 captured160827/160916; final inductor1 PRESENT0.994992, BLACK_MARKER_DIRECTION_WRONG, DIRECTION_ERROR candidate and PatchCore1.0. VRM3 RIGHT position advisory persists and remains unresolved. Board UNKNOWN.
- Scoped hash-bound non-training provenance saved; two repeats/one scene, not authority promotion or small-angle certification. No model/threshold changes, server restart, production DB association or motion command. Actual S22/API/inference only.

## 2026-09-08 inductor1 missing control

- User acknowledged VRM3 normal restoration and inductor1 removal. API test5219339c captured160114/160204; final inductor1COMPONENT_MISSING with EMPTY0.9999386, VRM3 state CORRECT0.987534 plus POSITION_ERROR candidate. Missing detection matches, VRM3 position warning conflicts with acknowledged restoration and remains unresolved rather than relabelled. Whole board UNKNOWN.
- Scoped hash-bound non-training provenance saved; two repeats/one scene, no authority promotion. No model/threshold changes, server restart, production DB association or motion. Actual S22 capture/API/inference only.

## 2026-09-08 VRM3 missing control

- User acknowledged PM1 restoration and VRM3 removal. Existing API testd7a50d79 captured155408/155458; final selected VRM3COMPONENT_MISSING only, EMPTY0.9998307; PM1 PRESENT0.991169. Both board results UNKNOWN. Scoped hash-bound non-training provenance saved, two repeats of one scene, no model or threshold changes or authority promotion.
- Actual S22 capture/API/inference only; no server restart, production DB association or motion command. Successful VRM3 control is not proof across all slots, lighting or seating defects.

## 2026-09-08 PM1 missing control

- User acknowledged HBM8 normal restoration and PM1 removal. Existing API test6c8d1c38 captured154744/154835, final UNKNOWN. Final selected finding PM1COMPONENT_MISSING only, EMPTY0.99999952; HBM8 PRESENT0.997326 and lower-left dot match restored direction.
- Hash-bound scoped provenance excludes training and authority promotion; two repeats of one physical scene. No threshold/model changes, production DB association, server restart or motion command. Actual S22/API/inference only.

## 2026-09-08 HBM8 reversal control

- User acknowledged HBM8 restored180. API test663f387e captured154102/154152; both HBM8 orientation stages report WHITE_DOT_AT_UPPER_RIGHT. Final selected HBM8DIRECTION_ERROR only, PRESENT0.998544, final UNKNOWN. Prior VRM3 warning absent on this capture, not proof of resolved repeatability.
- Stored scoped hash-bound non-training provenance; two repeated captures of one scene, no authority promotion or extrapolation to all HBM slots. No model/threshold changes, motion, production DB association or server restart. Actual S22/API/inference only.

## 2026-09-08 HBM8 missing and GPU recovery control

- Explicit user truth GPU restored/HBM8 removed. Existing API test928bbdc2 captured153520/153611, final UNKNOWN with HBM8COMPONENT_MISSING (EMPTY0.999992) and VRM3POSITION_ERROR (RIGHT boundary candidate). GPU PRESENT0.998685 and expected lower-left dot agree with recovery; surface score1.0 is not confirmed damage.
- HBM8 background still produces advisory orientation PASS despite EMPTY presence; not valid direction evidence and must be addressed before authority promotion. VRM3 collateral warning needs physical truth, not automatic relabelling. Recorded scoped non-training provenance; no thresholds/authority changes, server restart, motion or production DB write. Actual S22 capture and inference only.

## 2026-09-08 GPU reversal confirmed control

- Corrected prior decdc42b provenance after user explicitly confirmed accidental normal restoration; preserve original requested state and exclude from reversal evaluation. New acknowledged GPU180 control9fd034cb-3fc7-466b-b192-c4cc7315a339 captured152806/152856 via existing API. Both orientation stages report WHITE_DOT_AT_UPPER_RIGHT; final finding GPU DIRECTION_ERROR only, PRESENT0.975665, PatchCore1.0, fused UNKNOWN.
- Stored hash-bound non-training provenance. Normal/recovery/missing/reversal observations now agree for GPU in this small same-session sequence; repeated captures are not independent scenes or release certification. No thresholds/weights/authority changes, production DB association, server restart or motion command; actual S22 capture/inference only.

## 2026-09-08 GPU reversal capture requires placement clarification

- Requested GPU180 reversal and user acknowledged. API test decdc42b-aab2-4230-8953-b218a48781e3 captured152307/152356, both UNKNOWN. Final GPU PRESENT0.99856 and lower-left dot reason, zero selected candidates. Direct visual review of final source shows upright logo/lower-left dot, inconsistent with requested reversal.
- Preserve requested state and visual discrepancy in local validation provenance; exclude from training and release evaluation pending clarification. No claim of successful reversal detection or confirmed model miss. Actual S22/API/inference only; no model/threshold changes, production DB write, server restart or motion command.

## 2026-09-08 prospective GPU missing control

- User acknowledged removing only GPU. Existing API test request86580920-5d5e-43ac-af32-046943c467e6 captured151549/151638, completed UNKNOWN twice in100s. Final report selected GPU COMPONENT_MISSING only, EMPTY confidence0.9841374, PatchCore0.9601264; no other displayed candidates. Previous normal SMD01 warning absent in this final capture does not resolve its repeatability problem.
- Saved explicit GPU-only truth, final source/report SHA256 and non-training provenance. One physical scene with two repeats, not independent accuracy certification or authority promotion. No model/threshold changes, production DB association, server restart or motion command. Actual S22 capture/inference and local API request only.

## 2026-09-08 prospective normal request validation

- User acknowledged normal placement of all25 slots. Sent test-only request75b0a3b6-8811-4abd-aac2-fbaccdc57f8c through existing API (no verified production Unit). Real S22 captures151114/151204 and inference completed in101s, UNKNOWN twice; same physical scene, not two independent samples. Added local validation provenance, excluded from training and authority promotion.
- Final presence candidates:20PRESENT and5VRM CORRECT. GPU/eightHBM white-dot and twoinductor marker reasons agree with normal; VRM state agrees. PM/SMD independent orientation remains uncalibrated. Final selected candidate SMD01SEATING contradicts user-normal label; retain false-advisory evidence rather than relabelling or adjusting thresholds. No production motion/DB write or server restart; actual camera and inference only.

## 2026-09-08 separate report heatmap from candidate decisions

- Investigated real request 5806a0b8-e521-4115-a5f9-e5dd163c5bd4: two captures completed UNKNOWN with 25 unknown slots, zero selected findings, six undisplayed advisory pose flags, and available PatchCore maps for all slots. Empty public heat panel came from candidate gating, not missing PNG transport or absent PatchCore inference. Test Unit identity was not verified against production DB; no confirmed-defect form claim.
- Changed newly generated three-panel report to use the existing full-slot fixed-normal-baseline excess map/overlay instead of candidate-gated maps. Labels explicitly identify unverified PatchCore response, independent of candidate count. Separate gated diagnostic images remain; no invented heat for missing parts, per-image rescaling, threshold/model/authority or API enum changes. JSON visualization records the mode; existing findings/defects/diagnostics distinction is retained.
- Added source-wiring and empty-candidate pixel-preservation regressions; complete related suite 370 passed including temporary local socket tests. Existing immutable API result/image were not replaced. No physical capture, production server restart, motion or DB writes. New child inference will use updated rendering on subsequent new requests; existing request IDs retain their original result. Full-map colours can include benign variation and must not be treated as confirmed defects.

## 2026-09-08 local HTTP and integrated regression closure

- Ran the previously excluded HTTP roundtrip after sandbox socket denial and approved escalation. Temporary localhost server verifies unauthorized rejection, acceptance, UNKNOWN result, PNG bytes/MIME/SHA and corrupted-image rejection; shutdown is in test finally. Inputs and inspection are mocked, not physical or teammate network traffic.
- Full hybrid/triggered-pipeline/integration Python suite: 368 passed, none deselected. Node demo viewer suite: 1 passed. Updated demo scope with exact validation boundaries and outstanding physical S22/Sequencer UNKNOWN-hold acceptance. No runtime criteria or authority changes; no production server start, camera capture, motion, external upload or DB write. Completion of these software regressions is not inspection accuracy certification.

## 2026-09-08 production Runner mocked-child coverage

- Added six tests of the production Runner using a fake Popen child and intercepted process-group signals. UNKNOWN/PASS/FAIL package only the final attempt report under the original request IDs; one child owns recapture, inherited external context is removed, and the lock descriptor is passed through. Child error, pipeline error and timeout never package a result; cleanup requests TERM then KILL for the owned fake group.
- Combined suite 331 passed, 1 HTTP roundtrip deselected. These are mocked-child tests, not actual subprocess termination, HTTP, camera or Sequencer validation. No runtime behavior, model, threshold or authority changes; no server, capture, equipment command, upload or DB write. Existing accuracy limitations remain unchanged.

## 2026-09-08 recapture failure regression closure

- Extended Store plus real retry-pipeline mock integration with second-capture failure, unchanged previous ROI, and invalid decision cases. All preserve the first UNKNOWN attempt, record pipeline ERROR/API FAILED rather than completed inspection, retain request identity, and reject duplicate recapture after Store reconstruction. Camera/inference are fakes; the adapter mirrors Runner's completion gate, not its subprocess execution.
- Related hybrid/pipeline/export/API suite: 325 passed, 1 HTTP roundtrip deselected. Runtime thresholds, weights, authority and API contract unchanged. No server started, physical capture, robot/conveyor command, upload or DB write. Live HTTP/Sequencer/equipment hold remains unverified; these tests do not establish model accuracy or resolve residual SMD/VRM boundary ambiguity.

## 2026-09-08 request identity across recapture mock integration

- Added test_api_recapture_contract.py connecting real Store and run_pipeline through a test adapter with fake camera/inference. Three UNKNOWN->UNKNOWN/PASS/FAIL paths verify same job/unit/inspection IDs, exactly2attempts, distinct capture references, duplicateRUNNING no extra capture, differentIDbusy, and restart/replay idempotency. FinalUNKNOWN retains localHOLD recommendation without adding public decision enums or commands.
- Related API/pipeline/hybrid/export suite322passed,1HTTP socket roundtrip explicitly deselected. This is in-process mock integration, not production Runner subprocess/HTTP/Sequencer or physical hold certification. Updated scope document with these boundaries. No runtime implementation changes in this work, camera/robot/conveyor commands, server restart, external API/upload or DB writes.

## 2026-09-08 bounded UNKNOWN recapture pipeline

- Wired triggered_inspection_once.py default one additional capture only onUNKNOWN, maximum2attempts. PASS/FAIL stop immediately; skip-capture forces zero recaptures. Each attempt rejects stale image/report, pins captured image before inference, retains completed attempt paths in event, exports only final report. Invalid decision is operationalERROR. Context snapshot remains once before capture.
- FinalUNKNOWN records recommended_action=HOLD and hold_command_sent=false; no direct equipment command. HTTP enum/routes/IDs unchanged. Current API launches this child afresh per request, so future requests can take longer without restarting server. Existing300s outer timeout unchanged. Caller-level retries must not be multiplied inadvertently. Full physical and Sequencer hold integration remain unverified in scope config/docs.
- Tests cover UNKNOWN->UNKNOWN/PASS/FAIL, initialPASS/FAIL, offline no-camera, stale retryERROR with first-attempt evidence retained, prior freshness/export behavior. Combined hybrid/pipeline/export302passed. No live capture, inference, server restart, external API request/upload, DB write or robot/conveyor/gripper motion in this work.

## 2026-09-08 demo inspection scope frozen

- User approved deadline-limited scope: missing, wrong direction, clear displacement/lip seating, visible pin loss/collapse, and visible surface damage under validated imaging. Added inspection_demo_scope.json and docs/INSPECTION_DEMO_SCOPE.md. Excluded subtle seating, precise1mm clearance and unresolved microcracks from confirmed capability claims, not from uncertainty handling. Existing mandatory fusion stages and authority remain intact; no automatic candidate-toFAIL or no-candidate-toPASS.
- Agreed UNKNOWN workflow requirement: one additional capture, total2attempts, thenHOLD. Explicitly runtime_wiring_verified=false: this scope/config document does not implement or verify recapture. No claim of operational retry completion. Existing API identifiers, exported defect mappings and JSON/PNG delivery untouched; scope categories are explanatory, not new wire codes.
- Freeze expansion/tuning for demo; reproducible execution fixes remain permitted. Candidate/model limitations explicitly documented. Scope invariant test1passed. No capture/inference/model/threshold changes, robot/conveyor/gripper motion, server restart, external upload or DB write.

## 2026-09-08 SMD01 fixed-window visual comparison

- Extended existing compare_smd01_empty_restored.py with display-only labels (never used as paths), source hashes from decoded bytes, checked PNG writes; default filenames/labels retained. Produced fixed canonical crop180x140 at1181,1014 with nearest-neighbor4x viewing; no local recenter/rotation/normalization or generated pixels. Images in runtime/inspection/smd01_boundary_pair_20260908 and recent_pair subfolder.
- Visually compared archived subtle-defect20260907_120941 versus user-normal132425: silhouettes and surrounding dark slot are very similar in this view, with small edge/brightness differences; cannot establish reliable height distinction from this pair. Recent controlled-lip132108 versus same normal shows more evident upward displacement and exposed dark lower slot. These are qualitative observations, not new labels, measured height or validated classifier performance. Retain all historical truth and UNKNOWN.
- No runtime thresholds/model/authority changes, capture/inference or equipment/network commands. Full existing hybrid/export291passed; both comparison CLI runs succeeded with hashed metadata. Visualization extension only; residual normal/microdefect ambiguity remains.

## 2026-09-08 rejected SMD01 pixel deadband experiment

- Tested1canonical-pixel signed-y nomination deadband using existing110mm/1266px scale. This is an engineering abstention proposal, not measured uncertainty.132402 normal excess0.05917mm (~0.68px) then has0rendered candidates in saved-image GPU replay;132035 lip remains beyond deadband. Artifact runtime/inspection/smd01_deadband_20260908 marked REJECTED EXPERIMENT, not deployed success.
- Extended archived-provider replay21unique images found1missed labelled subtle defect:hybrid_fixed_slot/20260907_120941_804840. Therefore restored runtime boundary_deadband_px to0.0; no effective sensitivity change retained. Original normal false advisory remains. Offline runner temporarily applies1px and restores rule in finally; raw stages preserved. Existing3normal/2defect narrow controls alone were insufficient to reveal this regression.
- Kept testable helper, explicit zero deadband diagnostic metadata and audit script. Final hybrid/export291passed. No new capture, training, server restart, upload/DB write or robot/conveyor/gripper command; saved-image GPU experiment only. Do not equate test pass with inspection accuracy or hide the missed control.

## 2026-09-08 SMD01 peer-motion diagnosis

- Added offline audit_smd01_recent_motion.py with source image/report hash checks and target-excluded peer median. Compared saved131643 normal,132035 lip and132402 restored; outputs runtime/inspection/smd01_recent_motion_20260908/audit.json. No coordinate correction applied.
- Normal->lip targetrawy delta-0.702707 algorithm-mm,24peer median-0.014187; residual-0.688520. Normal->restored targetdelta-0.198117,peermedian-0.004043,residual-0.194074. Uniform board drift alone does not explain the target discrepancy in this sample. Cannot distinguish target physical placement variation from mask error or local registration/parallax without further evidence; do not claim measured clearance/height or use the residual as runtime correction.
- Target-exclusion and no-peer uncertainty tests added; full hybrid/export289passed. No fresh capture/inference, model/threshold change, training, robot/conveyor/gripper command, restart/upload/DB write. Normal-restoration false advisory remains unresolved; historical labels preserved.

## 2026-09-08 SMD01 recovery exposes residual false advisory

- User acknowledged normal restoration ofSMD01. Captured132402 flashOFF4000x3000/69mm equivalent, overview restored. GPU report runtime/inspection/smd01_recovery_20260908_132402/20260908_132425_543863 completedUNKNOWN; timestamped provenance records user-normal seating and sourceSHA, no training.
- SMD01SEATING? persists after restoration: rawy-0.765338 versus frozen lowerbound-0.706172 (0.05917mm beyond in algorithm units), area4404.5px,outline0.559,PatchCore0.129. This new normal control passes the position corroboration and disproves complete resolution of normal-placement false warnings. Do not relabel it defective or widen threshold from this one case. Pixel-to-mm output is not measured seating height/clearance.
- SMD03 candidate cleared without requested repositioning; transverse magnitude0.71914mm versus prior0.856mm. Repeat sensitivity remains, no physical defect assertion. No model/code/threshold changes, server restart/upload/DB write or robot/conveyor/gripper motion. Further analysis should separate registration/pose variation from true component displacement rather than repeatedly ask for same normal pose.

## 2026-09-08 fresh SMD01 lip defect verification

- User acknowledged placing onlySMD01 on socket lip. Captured132035 flashOFF4000x3000/69mm equivalent; overview restored. Current GPU report runtime/inspection/smd01_lip_validation_20260908_132035/20260908_132108_768224 completedUNKNOWN. Timestamped source/reportSHA and limited user-intent label preserved in placement_provenance.json; no training or height measurement.
- SMD01SEATING? (displayPOSITION?) detected with area4513px,outlineconfidence0.208,PatchCore0.29416 and rawy-1.26993mm. Both area/appearance and existing signed-position corroboration true; new abstention rule retains this actual controlled defect. Previous fresh normal had0candidates. One pair is not general accuracy certification; no authoritativeFAIL promotion.
- AdditionalSMD03POSITION? at transverse0.856mm versus0.840mm display boundary; requested unchanged, not relabelled defective. Needs separate repeatability/physical truth review. No thresholds/code/models changed, no server restart/upload/DB write or robot/conveyor/gripper motion; camera capture and inference only.

## 2026-09-08 fresh post-change SMD01 observation

- Captured fresh131643 S22 flashOFF4000x3000/69mm equivalent after user continuation; unchanged placement assumed from preceding normal-seating confirmation, not independently re-labelled. Managed overview restored. GPU output runtime/inspection/smd01_fresh_validation_20260908_131643/20260908_131741_747610 completedUNKNOWN with0rendered candidates.
- SMD01 area_appearance_trigger=false and position_corroborated=false on this capture. Therefore this fresh observation is consistent with no warning but does not itself exercise or prove the new abstention gate; prior saved121448 replay did. Seven unpromoted auxiliary pose flags remain exposed in JSON/report (HBM06/07/08,IND02,PM02,SMD01/03). No-candidate is not PASS or evidence that all25 inspections are validated.
- No new thresholds/model/code changes, training, upload/DB write, server restart, robot/conveyor/gripper motion. Actual camera capture and GPU inference only. Further meaningful validation is a controlled physical SMD01 defect, not repeated normal captures counted as independent accuracy.

## 2026-09-08 SMD01 area-only seating nomination abstention

- Changed only SMD01 area-plus-appearance seating nomination: it now also requires the existing signed-position small_lip_candidate evidence. No numeric threshold, RGB preprocessing, learned weights or fused authority changed. Area-only response is retained per slot as smd01_lip_evidence_review UNKNOWN/ADVISORY_ONLY with original area_appearance_trigger and position_corroborated flags. This is an abstention from unsupported height inference, not a new height detector or PASS override. Other SMD slots, weak-outline path, missing/rotation/large-position checks remain unchanged.
- User-normal121448 image rerun through current GPU pipeline: runtime/inspection/smd01_corroboration_20260908/current_replay/20260908_131122_339722; displayed candidates1->0, fusedUNKNOWN preserved and ambiguous area evidence retained. No new capture. This image informed the change and is a development regression, not independent validation. Historical archived-provider/current-rule controls retain3normal SMD01 no-candidate and2defect SEATING candidates; controls.json preserves source hashes. Other historical inductor outcomes in that artifact are old-provider results, not current model measurements.
- Added tests for confirmed normal area response and displaced response; existing synthetic area-without-position test now asserts abstention rather than unsupported seating nomination. Full hybrid/export regression287passed. Runtime reduction may miss height-only seating defects with in-range2D position; uncertain evidence remains available, no claim of complete defect coverage. No training, camera changes, server restart, upload/DB write or robot/conveyor/gripper command.

## 2026-09-08 SMD01 normal seating false advisory confirmed

- User explicitly confirmedSMD01 properly seated in latest121448 scene. Updated only that scene's placement provenance with normal seating; preserve original report and no automatic training. VRM04 restoration label remains unchanged; no propagation to earlier images.
- Traced displayedPOSITION? to SMD_LIP_SEATING rule, not generic0.75mm pose or signed-y rule. Normal sample outlineconfidence0.50033,maskarea4486px,PatchCore0.10735 exceed0.20/4400/0.10 thresholds. Archived normal142746 already has4494px area withscore0; controlled defects141847/144104 have4644/4711.5px and0.39857/0.15459. This explains a nonexclusive area plus low appearance threshold producing a false seating candidate; it does not measure height or establish a replacement threshold across model/lighting changes.
- Saved smd01_false_advisory_review.json beside provenance with exact reportSHA and comparison paths. No runtime/code/threshold/model change, recapture, inference, robot/conveyor/gripper command, restart/upload or DB write. Current finalUNKNOWN retained; warning remains unresolved rather than hidden by relabelling.

## 2026-09-08 VRM04 normal restoration paired result

- User acknowledged restoringVRM04 to normal. Captured121448 flashOFF4000x3000/69mm equivalent; managed overview restored. GPU inspection completed at runtime/inspection/vrm04_restored_20260908_121448/20260908_121643_501643. Input/reportSHA and bounded placement label archived in placement_provenance.json; no training or pin/surface truth inference.
- Under unchanged thresholds VRM04RIGHT? cleared: right excess[4.31667,4] in previous right-shift capture becomes[0.15476,2]px. This pair supports responsiveness to placement, not resolution of prior115529/120334 normal-placement false warnings or measured1mm clearance. VRM04 stateCORRECT0.97826; final boardUNKNOWN.
- SMD01POSITION? remains the only rendered candidate; five other auxiliary pose flags remain disclosed. SMD01 is not relabelled defective without physical confirmation. No model/code/threshold change, server restart, external upload, DB write or robot/conveyor/gripper motion; camera capture and inference only.

## 2026-09-08 VRM04 paired right-shift capture

- User acknowledged instruction to move onlyVRM04 against its right wall. Captured120934 flashOFF,4000x3000,69mm equivalent; overview restored. GPU report runtime/inspection/vrm04_right_control_20260908_120934/20260908_121038_689975/hybrid_report.json completedUNKNOWN. Hashed input/report and bounded user-intent labels preserved in placement_provenance.json; physical clearance/height and pins/surfaces unverified.
- Boundary RIGHT? excess increased from normal[2.83297,2] / repeat[2.33207,2] to[4.31667,4]px. VRM04 POSITION? detected, but existing guard also flags normal controls; no claim of resolved discrimination. ClassifierCORRECT0.99384 and auxiliary pose0.27013mm show why these cannot independently assert acceptable process clearance. AdditionalSMD01POSITION? appeared despite requested unchanged placement; not automatically relabelled defective. Needs comparison on normal restoration.
- No model/threshold/contract changes, training, server restart/upload or robot/conveyor/gripper motion. Actual commands limited to camera capture and GPU inference. This is a paired development observation, not final PASS/FAIL validation.

## 2026-09-08 VRM normal warning sensitivity and input hardening

- Added audit_vrm_guard_tradeoff.py and tests: hashed historical reference/intent reports, deduplicated scene-slot pairs, fixed guard sensitivity1/2/3/4px, no runtime threshold selection. Historical30LEFT_SEATED controls yield0flags throughout;7RIGHT_SHIFT controls yield7/7/6/6. Reference overlap prevents independent accuracy claims. Fresh reserved image remains excluded from fitting;2px would suppress its warning but is not deployed based on that observation. Artifacts runtime/inspection/vrm_guard_tradeoff_20260908.
- Repeated S22 capture without requesting repositioning:120334 flashOFF,4000x3000,69mm equivalent; overview restored. GPU report normal_repeat_20260908_120334/20260908_120419_032091 remainsUNKNOWN withVRM04 POSITION? only. Right excess changes[2.83297,2] to[2.33207,2]px; same right-edge coordinate. Persistent reference/boundary mismatch is more plausible than one-frame jitter, but physical wall clearance not measured. Repeated unchanged placement assumed, not independently relabelled; pins/surface truth remain unspecified. Auxiliary pose flags7->6, not certified normal outcomes.
- Parallel worker hardened boundary evaluate: malformed/empty/nonfinite/negative-margin/overflow inputs abstain UNKNOWN with no codes; valid decisions/thresholds unchanged. Main updated pure-function audit probe dependencies and added sensitivity tests. Final hybrid plus export regression285passed. No authoritative promotion, training, robot/conveyor/gripper command, server/API change or upload. Camera capture only, no transport configuration change.

## 2026-09-08 parallel tooling and fresh normal placement control

- Completed two parallel offline tasks: HBM white-row profile candidate/CLI with byte-bound input hashes and synthetic tests, and a bounded validation-label registry (257 observations, 84 hashless, no independent exact-model validation). HBM candidate always remains UNKNOWN/ADVISORY_ONLY and is not wired as an authoritative runtime pin provider. Artifacts: runtime/inspection/parallel_completion_20260908; existing HBM pin availability remains unchanged.
- Added SHA-bound sequential saved-image batch runner, immutable source checks, partial progress, timeout and owned-process-group cleanup including parent SIGTERM. Two saved development replays completed (23.87s/21.16s), preserving expected VRM candidates and UNKNOWN. Code/config fingerprints are not complete model asset identity. Final hybrid plus export regression:272 passed; real synthetic SIGTERM child-reaping test included. No authority promotion or training occurred.
- User subsequently asserted all components normally placed. Captured flash OFF S22 3.5x optical photo at115529 (4000x3000,7mm/69mm equivalent), saved timestamped ROI; managed overview paused and restored successfully. Ran current GPU hybrid inference into runtime/inspection/normal_control_20260908_115529/20260908_115608_277397. Alignment0.986, finalUNKNOWN; rendered candidate only vrm_04 POSITION?. Seven auxiliary pose flags remain disclosed in the report, not counted as confirmed defects. No displayed candidate is not PASS.
- VRM04 warning comes from the separate learned boundary RIGHT? guard, not absence or classifier rotation: stateCORRECT0.97758, auxiliary position0.37581mm within its0.75mm heuristic, angle0degrees. Boundary right excess2.83297/2px exceeds1px guard relative to historical left-seated references. This is not measured socket-wall clearance; retain as a false-warning control against user normal-placement assertion, not evidence to relabel the board. No threshold widening based on one capture. User assertion covers placement/presence, not independently verified fine pin/surface condition. Preserve fresh image for validation, not automatic training.
- No robot, conveyor drive, gripper command, server restart, API/token change, external upload or DB write. Camera capture only; no camera transport/quality configuration change. Remaining limitations: independent defect/normal validation, unavailable pin checks, physical1mm clearance and height metrology. Report and raw diagnostic flags remain advisory.

## 2026-09-08 parallel release verification and axial wrap fix

- User explicitly requested parallel verification/finalization due to time. Two disjoint workers implemented bounded presence/direction and geometry release audits with tests; main handled final-decision/export review, integration and grouped logging. Artifacts runtime/inspection/parallel_release_20260908/{presence_direction,geometry}/summary.json and consolidated release_review.json with source hashes. Reused reports remain development evidence, repeated observations not independent trials. No automatic authority promotion.
- Geometry worker reproduced an actual pure-function axial-wrap bug:reference+89/sample-89 with3degree margin emittedROT? although axis difference2degrees. Main fixed vrm_boundary_advisory.axis_limit_side using modulo180 reference-relative bounds, with ambiguous spans abstaining; actual11degree wrapped displacement retained. Four new wrap tests and updated geometry probe verify fix. Pre-fix geometry artifact preserved; no observed production occurrence claimed. Position/angle margins, slot coordinates, models and UNKNOWN/advisory authority unchanged.
- Consolidated referenced saved report has106ADVISORY_ONLY stages,8UNAVAILABLE HBMpin stages,5DISABLED experimental VRMseating stages and0authoritativeFAIL votes. This does not count119defects. Autonomous confirmed release remains NOT_RELEASED: independent calibration/validation absent within reviewed scope; right-wall1mm and height not measured. Existing candidate visualization/JSON+PNG continue. Added docs/INSPECTION_RELEASE_REVIEW.md describing scope-specific validation and no promotion from scores or software tests.
- Final hybrid plus export regression247passed. No new GPU inference/capture, running server restart, API/token/route change, DB write/upload or robot/conveyor motion. Main source change is wrap fix only; new audits are offline. No user relabelling or physical measurement requested this turn. Further finalization requires scoped independent evidence, not weakening UNKNOWN to meet the deadline.

## 2026-09-08 empty groove reference feasibility

- Follow-up visualization: render_vrm_gap_comparison.py places the saved registered crops beside same-frame learned body contours (green) and historical groove x reference (cyan), four matched panels; body_groove_comparison.jpg in finalv2 folder. Visually inspected: cyan line does not reliably coincide with the visible inner socket edge in these occupied captures. Therefore the22/11px values must not be promoted to physical clearance; cross-capture reference bias, shadow and surface-height effects are not resolved. This is visualization only, no detection/threshold/production change or equipment command.

- Added offline audit_vrm_wall_repeatability.py reusing existing groove-profile diagnostic and current global registration. Saved empty134637 plus complementary empty141311/141603 provide two observations perVRM. Right dark-groove repeat ranges for01..05:2,0,0,1,0px. This does not identify the physical inner wall or certify0–2px measurement uncertainty. Learned providers/runtime unchanged.
- Compared reference groove x with existing boundary mask maximum x from170142/185803: VRM02 gap22.03->11.03px;VRM03 gap21.03->11.03px. This supports a relative rightward change in these images, not absolute1mm clearance verification. No mm conversion, new tolerance or PASS/FAIL provided; gap intervals represent reference repeat spread only, excluding unknown mask/optical/surface error.
- Final artifact runtime/inspection/vrm_wall_repeatability_20260908_v2/audit.json and paired-slot empty_groove_comparison.jpg. Initialv1 visualization was inspected;v2 corrects column pairing and adds gap comparisons, preservingv1. No camera capture, model training, actual inference of new part masks, server restart, robot/conveyor command or upload. Existing cached stage geometry used; no claim physical socket wall is validated.

## 2026-09-08 VRM position versus clearance diagnosis

- Inspected current saved reports and boundary implementation; no fresh inference/capture required.170142VRM02POSE? comes from estimated longitudinal offset1.0181mm versus radial tolerance0.75mm, with transverse0.1456mm, angle0deg and noRIGHT? boundary signal.185803VRM02/03 rightward boundary excesses are4.37/6px and4.45/8px, respectively, relative to learned left-seated references, not measured socket walls. Current boundary code explicitly has no1mm metrology authority.
- Added audit_vrm_position_causes.py and2passing tests; artifact runtime/inspection/vrm_controls_20260908/position_causes.json separates reference-corrected centre offsets, pixel boundary excess and required right-wall1mm. Actual wall clearance=null/UNKNOWN, including when no boundary warning exists. Do not reinterpret historical flat seating as current clearance certification or suppress longitudinal warning solely from a presence label.
- No thresholds/models/production display changed, no camera/robot/conveyor/server/DB action. Next justified geometry improvement needs socket-wall reference and uncertainty validation rather than weakening0.75mm from these cases. Existing errors remain advisory; no physical clearance verification claimed.

## 2026-09-08 extended VRM present regression

- Replayed170142 and185803 saved photos through current full25-slot GPU pipeline after context corroboration. Eight explicitly PRESENT labels, historical image SHA verified, context available8/8, false MISSING?0/8. Added audit_vrm_present_regression.py with exact report/slot cardinality and provenance, no overwrite; artifact runtime/inspection/vrm_controls_20260908/extended_normal_summary.json. No independent accuracy claim.
- Other displayed evidence remains:170142VRM02POSE?;185803VRM02RIGHT?/SEATING?,VRM03RIGHT?/POSE?. These are not certified clear normal-position results. Historical physical seating and current process-clearance policy differ;185803VRM02 explicitly has right-wall gripper-interference review. No position threshold change from presence labels. Both fused boards UNKNOWN.
- No model/decision change, live capture, server restart, upload, DB write or robot/conveyor command. Current missing corroboration retained; residual position indications need separately labelled geometric/process evaluation. This grouped record reports saved-image regression only, not new hardware validation.

## 2026-09-08 corroborated VRM missing advisory

- Reused frozen central55/context130 original-RGB EfficientNetB0+logistic presence candidate (SHA b5e1675d2b9c72ea330a5dea48911f26342e871664d7b7b9abf0d1b8b07ced43), no refit or learned preprocessing change. Eight saved photos,32 explicitly labelled instances:21PRESENT/11EMPTY agree at binary0.5. Reused development/previous holdout observations, not independent accuracy; one EMPTY probability0.1627 does not satisfy stricter display gate. Preserved corrected labels and did not equate presence with normal seating.
- Added vrm_presence_advisory.py and wired separate optional per-slot diagnostic into main. Existing primary UNKNOWN low-confidence EMPTY with confidence[.80,.90), context available/finite original-RGB P(PRESENT)<=.10 and valid alignment/nonblocked capture can add MISSING? only. Existing primary0.90 threshold, weights, all stages, fusion and authority unchanged. No override of PRESENT/CORRECT, no pose assertion, no confirmed defect. Local cached backbone only, validated method/shapes/classes/finite parameters; absence/error becomes unavailable and other providers continue. CPU batch for5slots; thread setting restored. Optional artifact remains in runtime, so transfer packaging requires explicit inclusion; no automatic download.
- Full GPU saved-image integration replay142337 -> corroborated_replay/20260908_110219_537590 now displays VRM01/03MISSING?, retains04POSE?/05MISSING?. Normal134016 -> corroborated_normal/20260908_110337_500255 has no VRM candidates. Source hashes and all existing stage dictionaries identical to pre-change reports; both finalUNKNOWN. Three-panel defect PNG visually checked. Artifacts runtime/inspection/vrm_controls_20260908/context_*.json and README links.190 hybrid tests passed, including13 new corroboration guard tests; tests are software regressions, not model accuracy.
- No camera capture, live server restart, robot/conveyor command, DB write or external upload. Only missing-candidate display/diagnostic behavior changed; unverified corroboration never enters production votes. Remaining limits: small correlated historical sample, uncalibrated probabilities, optional model portability, and runtime latency not separately benchmarked.

## 2026-09-08 VRM presence and position control replay

- Replayed four saved S22 photos with current full25-slot GPU pipeline: September5 141311,141603,142337 plus September7 134016. Label provenance from vrm_presence_context_holdout_20260905.json and explicitly corrected latest-normal audit_vrm_mixed_false_positive.py; did not infer pose normality from PRESENT or mix physical seating with later gripper-clearance policy. Three early label scenes lack historical image hashes; current source/replay hashes verified, historical immutability not claimed.
- Presence15 labelled instances:11matching,4abstentions,0opposite decided states. EMPTY8:5EMPTY,3UNKNOWN (VRM01 in141603/142337 andVRM03 in142337), raw EMPTY confidence0.832634/0.846235/0.875977 below deployed0.90; these have no MISSING? display. PRESENT7:6CORRECT,1UNKNOWN (rotatedVRM04, rawCORRECT0.842463). Independent pose still flags that rotatedVRM04 with POSE?. No threshold lowering or model training performed.
- User-confirmed normal VRM03/05 in134016 have zero displayed advisory candidates. Raw generic pose03PASS/05FAIL; suppression is existing policy, not proof raw geometry is correct. All4board outcomes UNKNOWN. Identified next scoped issue as low-confidence empty-slot coverage, particularlyVRM01; held-out presence evidence required before changing gate/weights.
- Added audit_vrm_current_controls.py with label config hash, current source validation, exact report/slot cardinality, per-task outcomes/reasons/confidences and provenance. Seven tests passed distinguishing abstention, presence and pose. Artifacts runtime/inspection/vrm_controls_20260908/audit.json and README.md link current reports. No live capture, server restart, upload, DB write, robot/conveyor motion or runtime inspection policy change. Small reused controls do not establish deployment accuracy.

## 2026-09-08 current normal inductor control replay

- Replayed five saved S22 photos (20260906:183151,183239,183328,175316,184949) through the current full25-slot GPU pipeline, sequentially to limit resource contention. Evaluated only eight previously explicitly labelled normal inductor-direction instances; did not relabel mixed-scene inductor02 or other slots. Exact source hashes verified against the control audit.
- All eight normal orientation stages PASS, zero advisory codes on those eight slots, zero missing controls. All five whole-board fused statuses UNKNOWN. This is reused development regression, not independent accuracy or production PASS certification; no weight, threshold, fusion or camera setting changed. Together with the preceding two defect replays, this supports retaining the current inductor direction rules on this bounded set, not tightening them from stale historical misses.
- Added summarize_current_control_replays.py: exact-hash joins, duplicate replay/slot rejection, missing-control accounting, hashes and provenance preserved, separate advisory/stage/fused outputs. Three new tests plus eight prior control tests passed (11 total). Artifact: runtime/inspection/confirmed_controls_20260908/normal_current_summary.json, linked from its README. No new capture, robot/conveyor command, server restart, upload or DB write. Remaining work is other defect tracks and independent capture-condition validation.

## 2026-09-08 provenance-aware historical control regression

- Added audit_confirmed_controls.py and eight passing tests: explicitly documented17 slot/task controls, source image/report hashes, duplicate guard, source-label provenance, reused-development split, abstention separated from PASS/FAIL, non-overwriting output. No unlabeled slot is inferred normal; generic 2-D pose is not used to certify physical seating. This is archived-provider/current-advisory replay, not current-model accuracy. Labels come from prior explicit-control audit sources, not new visual guesses.
- Artifact runtime/inspection/confirmed_controls_20260908/audit.json includes17 controls, zero exclusions. Historical inductor orientation:8 normal PASS,2 defective FAIL,2 defective incorrectly PASS. SMD01:3 normals unflagged by current advisory rules and2 seating defects retain SEATING? on archived evidence; all5 generic raw pose FAIL values are explicitly NOT_COMPARABLE to seating truth.
- Ran actual current full25-slot GPU inference on the two historical inductor misses without capture: source172527 -> current_replay/20260908_104203_525257 and source174052 -> second_replay/20260908_104413_853430. Each source hash matches its historical report. Current inductor02 orientation now FAIL/ADVISORY_ONLY with direction candidates, confidence0.447324 and0.479883; both fused boards remain UNKNOWN. Thus the historical misses do not justify lowering current thresholds. No model, production decision rule or weight changed; current normal false-positive performance is not measured by these two replays.
- Eight unit tests passed; this is tool behavior verification, not inspection accuracy. No robot/conveyor command, camera capture, live server restart, upload or DB operation. README in the artifact directory links both JSON/PNG results and coverage gaps. Presence/position/pins/cracks and corrected VRM process-clearance versus seating labels still need separate coverage; no complete validation claim.

## 2026-09-08 parallel subsystem hardening and offline regression runner

- User authorized parallel improvements across implemented features. Four disjoint workers handled camera, conveyor, API/export and hybrid inspection; main handled robot numeric guards, integration review, software runner and grouped logging. Preserved all pre-existing changes, current model weights/valid-input thresholds, S22 slot-relative RGB pipeline, interlocks, topic/API/ID contracts, camera settings and teammate token/address. No live process takeover/restart, physical capture, dependency install, DB write, upload, robot or conveyor command.
- Hybrid: reject empty/incomplete required stage sets, duplicate/anonymous/mismatched25-slot sets and nonfinite votes. HBM pin checks now explicitly UNKNOWN/UNAVAILABLE (previously omitted); not replaced with a falsely validated provider. Invalid pose values cannot claim normality or contaminate shared-bias estimation. Malformed classifier class/order/probability/threshold data, YOLO reports and PatchCore calibration/crop failures are isolated so independent checks still run. Board-edge heatmaps crop rather than compress off-board evidence. Added44 regressions; hybrid159passed. Existing candidate display rules/weights unchanged; no inference accuracy claim.
- Camera: S22 snapshot refuses missing/shutdown/stale(>.20s)/invalid-age frames and preserves source stamp. GoPro recovery/close serialized, retry waits interruptible, decoder pipes closed and read errors recover instead of killing the worker. Optical shell validates existing supported settings before device access; abort exits and releases only owned pause/lock/camera resources.65mocked/synthetic camera tests passed. No transport-resolution/zoom change or real-device validation; driver-blocked V4L2 shutdown and best-effort EXIF checks remain limitations.
- Conveyor: finite/fresh heartbeats and motion clocks required; ready=false immediately latches stop rather than disappearing between control ticks. Duplicate active same-station request no longer injects stop/restart or extends deadline; lost interlocks still fault. Duplicate publisher detection accounts for remapping and identical node names. Zero/future/stale timestamps, decode failures, delayed processing and invalid geometry cannot refresh readiness; rejected frames clear consecutive evidence without clearing latched stops.123ROS-package tests passed with plain callback harnesses/mocks, no Node initialization/publishers. Monitor-only retains pre-existing zero-speed HOLD behavior, not passive monitoring. Source clocks must agree; physical stopping remains untested.
- API/export: detached response snapshots, worker-start reservation cleanup, durable-before-visible completion and failure cleanup prevent partially published results. Persistence failure closes further admission; cancelled runner cannot launch capture. Report/hash/raw archive derive from one byte snapshot; copied source ROI hash checked. Reuse verifies manifest/metadata/images/raw report, IDs/MIME and existing ZIP contents. Package references reject traversal/symlinks, legacy multipart/archive consume verified bytes. Strict flag/slot/UUID validation added; auth callbacks tested without store/body access. ROS bundle preflight cleans context on initialization/destruction failure.84integration tests passed including temporary loopback. API routes/token/JSON+PNG/production authority unchanged; local records remain trusted, checksums not authentication, snapshots consume memory proportional to package size.
- Robot numeric guard added to four existing approach/descent/cycle workflows: reject NaN/Inf/bool/malformed XYZ, timestamps, relevant depth/size data and nonfinite CLI limits before existing comparisons; current TCP pose finite check before command construction. Finite limits/calibration/confirmation semantics unchanged.57robot/tray tests passed, no actual robot/camera calls. This addresses invalid-input bypasses, not certification of all robot safety/lifecycle behavior.
- Added scripts/run_offline_checks.py: eight allowlisted software suites, bounded parallelism/timeouts, explicit optional mock loopback, missing dependencies not PASS, new report/log directories, no private device env sourcing or model/device launch. Source audit AST/bash-n only. Final runtime/software_checks/20260908T012722Z_4c4de5ed/report.json:494Python tests (159hybrid+84API+65camera+123ROS+57robot/tray+6runner),2JS passed;191Python/106shell syntax clean. First in-progress run failures and sandbox socket denial resolved; only final integrated report is authoritative regression evidence. This is software verification, not equipment readiness or held-out defect accuracy.
- Separate permitted host-GPU saved replay completed at parallel_hardening_20260908/saved_replay/20260908_102726_366114, source Sept7 172349 hash matches previous turn. All25surface scores identical, same4advisory candidates (GPU DIR,HBM03 MISSING,SMD01 SEATING,VRM05 RIGHT/POSE), finalUNKNOWN/25UNKNOWN/0confirmed.13unavailable stage entries mean8HBM pin plus5already-disabled experimental VRM seating; PatchCore25/25available. Three-panel output reviewed. review/ contains comparison and unbound test-only JSON/PNG/viewer; no fresh capture. Fine lip/height, HBM pin reliability, crack generalization and definitive PASS remain outstanding. Source ROS install symlink confirmed read-only; coordinated idle restart and teammate physical end-to-end trial are still needed. See docs/SOFTWARE_REGRESSION_CHECKS.md.

## 2026-09-08 capture quality and evidence integrity hardening

- Completed bounded improvements without new captures or model fitting. Preserved S22 fixed25 geometry, original learned RGB inputs, active weights/component thresholds and advisory authority. Extracted the existing static-board registration mask unchanged and added conservative photo triage against its reference. Provisional policy s22_static_board_quality_v1 uses masked128px cells: Laplacian ratio<.18 with contrast<.70, contrast<.30, brightness outside.35–2.5, or added clipping>.12. Invalid/unusable quality evidence or gross degradation forces effective board/slotsUNKNOWN while preserving raw stages/pre-quality decisions; no-gross-issue is not PASS and uncalibrated quality cannot certify PASS. Reference/mask hashes retained. Does not replace stale-frame checks or qualify local crack focus, height or fine shadows; no automatic recapture added.
- Added evidence_audit (every raw stageFAIL and candidate-promotion visibility) and provider_health to report image, JSON and archived viewer. Missing/invalid/non-finite PatchCore outputs become UNKNOWN/UNAVAILABLE, not zero-anomaly results. Disabled providers are explicitly listed too: final replay shows5 pre-existing disabled experimental VRM seating stages, not5 newly failed components; PatchCore is available25/25. No experimental seating candidate was enabled/disabled by this work. Previously suppressed PM02/SMD04 raw pose signals remain advisory and are now inspectable without changing displayed candidate nomination.
- Corrected export authority handling: only explicit AUTHORITATIVE stage evidence on a valid, unblocked FAIL board/slot can become confirmed. Invalid/missing/disabled authority and self-labelled candidate authority cannot be promoted. Added RIGHT?→POSITION_ERROR and ROT?→DIRECTION_ERROR aliases; preserve selected primary reason and existing external enum. New result.diagnostics carries quality/raw/provider/pose diagnostics; older immutable records may omit it and remain not-evaluated. API routes/token/IDs/idempotency and separate JSON/PNG downloads unchanged. Strict receiver parsers must allow optional additions; no teammate live integration claim. Updated handoff documentation and removed stale direct-upload/ZIP instructions from the main Vision README.
- Quality replay:8 saved source photos produced no gross-warning,24 artificial blur/black/white variants flagged24/24. Artifact runtime/inspection/quality_guard_20260908/quality_audit.json. These are coarse-rule regression checks, not defect accuracy or independent photographic validation. Two initial sandbox inference attempts had unavailable GPU and incomplete outputs; host nvidia-smi and permitted real-GPU replays confirmed the device works. No driver change. Failed sandbox reports remain diagnostic artifacts, not final performance results.
- Final actual-GPU replay: source s22_inspection_roi_20260907_172349.png, baseline hybrid_fixed_slot/20260907_172359_755455, final quality_guard_20260908/final_gpu_replay/20260908_101433_940821. Source SHA matched; all25 PatchCore scores identical (absolute delta0), four displayed candidates unchanged: GPU direction, HBM03 missing, SMD01 seating, VRM05 right/pose. FinalUNKNOWN/25UNKNOWN/0confirmed remains. New VRM05 export correctly uses POSITION_ERROR. Three-panel PNG visually checked. final_review contains comparison.json and unbound/test-only JSON+PNG pair plus viewer/index.html; this is saved-image replay, not current-board capture or a production inspection.
- Verification:154 Python tests passed across hybrid inspection/export/archive/API, including temporary loopback HTTP roundtrip, authority/quality gates, missing maps and legacy fields;2 JS viewer tests passed; modified Python files compiled. No live server restart, camera/transport change, robot or conveyor motion command, DB write, real upload or retraining. Fine VRM lip/height discrimination and crack/pose generalization remain unresolved; no claim of improved recall from unchanged model scores. Diagnostic details: docs/INSPECTION_QUALITY_AND_DIAGNOSTICS.md.

## 2026-09-08 non-disruptive server bundle and recorded-result viewer

- Added run_conveyor_vision_server.sh and integration/server_bundle.py to supervise the unchanged ROS conveyor remote and request-driven Vision HTTP entrypoints as separate processes. Default monitor-only, explicit --execute --confirm-motion for guarded motion, trusted-LAN bind0.0.0.0:8766, existing fixed token/environment/state directory retained. No camera launch, API/schema/topic rename, arrival-only duplicate capture, DB write, direct upload, interlock bypass or automatic restart. Existing process/inspection lock/port/ROS-service detection refuses takeover; shutdown signals only owned session groups, and either child exit stops its owned peer. New launcher/docs are additive; currently running legacy entrypoints need no replacement.
- Read-only --check on the actual host passed with ROS domain5 and HTTP8766 available; neither equipment server was started. Initial sandbox transport restriction was retried with permission, not treated as a camera/server defect. Preflight discovers ROS services and probes bind availability; it does not certify camera quality, physical station position or FR5 clearance. A future idle, coordinated switchover and actual teammate end-to-end test are still required; no zero-downtime process adoption is claimed.
- Expanded archive_demo_case.py with an embedded offline HTML viewer: actual verdict/summary cards, unchanged three-panel PNG with fit/native/zoom controls, searchable findings and expandable evidence/all-slot decisions, downloads and recorded-time/provenance. COMPLETED/image-ready/PNG signature/size/hash validation and HTML escaping enforced. Archived the existing Sept7 manual pair4bf88dbb-5981-4bfa-9fca-4eda51b40c0a in new runtime/inspection/portfolio_demo/recorded_20260907_172349_v2; original JSON/PNG retained byte-for-byte. ActualUNKNOWN,25UNKNOWN slots,4advisory candidates,0confirmed defects remain unchanged. Headless browser1440x1500 screenshot reviewed; this is a recorded example, not a live inspection or performance claim.
- Verification:52 Python integration tests passed (23 bundle lifecycle/ownership/port tests,29 archive/export/API tests including temporary-loopback request/pull);12 existing conveyor interlock tests and2 JS viewer tests passed. Shell syntax/Python compilation passed. Tests used inert child workers and mock inspection data, not motion or physical capture. No live server restart, model/threshold/fusion-authority change, camera capture, robot or conveyor command. All existing checks remain enabled; unresolved results retain UNKNOWN/ADVISORY_ONLY.

## 2026-09-07 portfolio recorded-case presentation and transport checks

- User retained current checks/results and prioritized portfolio demonstration over further model experiments. No scope removal or authority promotion. Added integration/archive_demo_case.py: unchanged completed JSON/PNG pair, hash/size verification, no-overwrite archive, escaped static HTML and provenance. Recorded-example label and actual decision/authority retained; no claim of general accuracy or delivery success.
- Archived existing172349 manual pair4bf88dbb-5981-4bfa-9fca-4eda51b40c0a to runtime/inspection/portfolio_demo/recorded_20260907_172349, actualUNKNOWN/25UNKNOWN slots/4advisory candidates. PNG viewed; original JSON/PNG bytes retained. Not a fresh capture, current-board inspection, or production-bound result.
-20 archive/export/API non-socket tests and1 local temporary HTTP roundtrip test passed (authentication, accepted-vs-completed,UNKNOWN preservation,PNG retrieval,integrity and obsolete ZIP rejection). Mock runner, not teammate/live equipment verification. No API restart,camera action,training,robot/conveyor command or runtime criterion change. Initial test import issue corrected before final successful run.

## 2026-09-07 seating measurement reassessment

- Reviewed latest failure report and fixed fusion contract; consulted primary OMRON examples of black-on-black extraction and height-based lift/coplanarity inspection. Wrote docs/vrm_seating_measurement_review.md distinguishing XY/in-plane pose from true corner lift, evidence gaps, validation requirements and scope limits. External industrial examples are context, not proof of KSMC camera impossibility or guaranteed performance of an alternative sensor.
- Recommendation only: stop repeated tuning against consumed failures; investigate calibrated socket-relative geometry within current hardware, keep unresolved seating UNKNOWN. Additional view/height setup or removing a required inspection item needs explicit agreement; neither was performed.1mm right-wall clearance preserved as a lateral requirement, not a height or all-around threshold.
- No new capture, training, runtime rule/contract/API change or motor command. This is an engineering review, not a completed seating detector. Primary-source links and exact local counterexamples are recorded in the review.

## 2026-09-07 new-pair contact training and reserved validation

- Reviewed explicit user-labelled development191820 FLAT/192042 SEATING for candidate training; updated only those archive records to development_reviewed/training_allowedtrue. Added opt-in --contact-plan loading with source hashes, split permissions, physical-group exclusion and original RGB shared crop.192342/192557 remain validation/training_allowedfalse; prior194959/184100/183823/184132 remain excluded. Same fixed20epoch CPU tail-finetune settings, no validation-based tuning or checkpoint selection.
-86 training records; diagnostic agreement86/86,all-flat validation10/10,earlier fresh validation2/4,oldholdout4/5,retrospective18/22. Reserved new pair1/2: normal192342 SEATING score.202502,lip192557=.178817 (wrong order). Earlier larger184132 lip now.519479, but known subtle184100=.003784 and194959=.001207 still missed. Candidate REJECTED; apparent improvement on one reused failure does not justify deployment.
- Artifacts runtime/inspection/vrm_contact_tail_new_pair_20260907/{candidate_tail_state.pt,manifest.json,evaluation.json}. Training ingestion recorded only for development pair, validation untouched. Review hashes in training manifest refer to pre-ingestion review record; later ingestion fields are appended provenance.3 tests passed; additionally checked86/2 split counts and new validation group/source hash exclusion. No capture, active model/threshold/API change or robot/conveyor commands. No reliable micro-lip discrimination established; repeating this same validation to tune thresholds would contaminate it.

## 2026-09-07 new contact development capture pair

- Captured user-instructed VRM05 normal left-wall flat191820 and lower-left lip192042 as separate physical placements, flashOFF optical4000x3000/focal7mm. Overview restored after each; host preflight found no active inspection/capture child. No motor command or API restart.
- Archived fixed VRM05 crops and source/crop hashes under runtime/inspection/vrm_seating_pairs; alignment scores.9773773/.9790975. Crops viewed for capture review, but physical seating labels derive from explicit user instruction/acknowledgment, not image-only height measurement. Only VRM05 labelled, other slots unknown; development_pending_review and training_ingestedfalse.
- contact_collection_191820_plan.json reserves next newly lifted/reseated normal and newly placed lip for validation before capture; all repeated exposures of a physical placement must remain in its split. Same board/component remains a generalization limitation. No model inference/fitting or criterion changes on this pair yet. Historical failure regression images remain outside training.
- Added explicit validation split option to existing archive helper (default unchanged, training_allowedfalse for both modes). Captured newly lifted/reseated normal192342 after user acknowledgment, flashOFF4000x3000; overview restored, alignment.9771763. Stored validation metadata/crop and viewed crop, no model inference or training. Collection plan records normal captured, new lip pending. No motor/API action; visual review is not physical height certification.
- Completed reserved validation lip192557 following explicit new-placement instruction/ready reply, flashOFF4000x3000/focal7mm, overview restored, alignment.9781243. Fixed crop reviewed; label remains physical-placement acknowledgment, not height inferred from pixels. Collection plan now has development191820/192042 and validation192342/192557, each FLAT/SEATING. Verified4 distinct source hashes/physical-scene IDs, image/crop hashes, split labels and training_allowedfalse/ingestedfalse. No inference on validation or training yet, no criterion/runtime/API/motor change. Four records are only two paired same-component setups, not broad independent accuracy evidence.

## 2026-09-07 contact coverage and tail-finetuning comparison

- Audited base candidate coverage:76 training crops contain only8 SEATING examples from2 physical VRM01/02 setups;10 validation crops are all FLAT from2 setups. Prior10/10 validation therefore measures normal controls only, not defect recall. This limits coverage but is not asserted as the unique failure cause.
- Extended contact trainer with opt-in verified earlier VRM05 development crops:8 extra training images from4 placements and4 fresh-validation images from2 separate placements; sidecar hash/label/source/split and group separation checked.84 training samples total. Known194959/184100/183823/184132 excluded from fitting. Frozen-contact augmented variant: fresh validation3/4, oldholdout3/5, retrospective controls17/22; known lip194959=.008097,184100=.048099; currentnormal=.118401/currentlip=.023327. Rejected.
- Added opt-in ContactTail: frozen early B0 RGB features, trainable later B0 blocks and ordered8-window linear head, fixed20epochs AdamW lr1e-4/decay1e-4/batch8/seed20260907, pretrained BN statistics held fixed. No evaluation-based checkpoint selection or threshold fitting. CPU final variant:train84/84,all-flat validation10/10,fresh validation2/4,oldholdout4/5,retrospective17/22 at diagnostic.5. Known lip194959=.000101,184100=.000738, currentnormal=.001748/currentlip=.016489. Critical failures remain; rejected, no runtime promotion. Training fit does not establish generalization.
- Artifacts runtime/inspection/vrm_contact_candidate_with_vrm5_20260907 and vrm_contact_tail_candidate_20260907 (candidate state, manifest,evaluation); runtime_enabledfalse/validatedfalse.3 tests passed for exact RGB/window extraction, invalid input and tail/head backprop contract. No capture, API restart, operating threshold/model change, robot or conveyor commands. Reused failure controls are regression evidence, not blind tests. Do not keep tuning against the same failures or claim reliable micro-lip detection.

## 2026-09-07 fixed RGB contact classifier candidate rejected

- Added train_vrm_contact_candidate.py: eight fixed96x96 RGB windows from the existing shared256 slot crop, frozen ImageNet EfficientNet-B0 pooled features concatenated in fixed spatial order, balanced logistic C1 head. CPU only, existing76 train records exclusively; checked crop hashes and disjoint physical train/validation groups. Reserved194959/184100/183823/184132 never fitted. No fresh pair ingestion, CLAHE, per-part registration or parameter search.
-113 total feature rows:76train,10validation,5historical holdout,22retrospective VRM05 pose controls. Diagnostic0.5 agreement76/76,10/10,4/5,17/22 respectively; selected/reused controls are not independent deployment accuracy. Known194959 lip score.011112,184100 subtle lip.049460; fresh normal183823=.016193,lip184132=.005337. Candidate still misses critical defects and reverses the fresh pair. REJECTED for runtime promotion despite validation10/10.
- Saved candidate.npz, evaluation.json, manifest.json under runtime/inspection/vrm_contact_candidate_20260907, runtime_enabledfalse/validatedfalse/ADVISORY_ONLY.2 synthetic tests passed for exact fixed RGB extraction and invalid shape rejection. No active model/threshold/API change, capture, robot or conveyor command. Freezing generic features plus this training set did not resolve contact-state generalization; these results do not prove all learned approaches or RGB inspection impossible.

## 2026-09-07 fixed contact-window appearance audit

- Added audit_vrm_contact_pixels.py for eight fixed32x32 corner/edge windows on registered VRM05 crops, original grayscale and locally applied CLAHE tracks kept separate. No per-part alignment, learned-input modification or segmentation mask dependency. Replayed same20 historical and2 fresh scenes with source hashes/alignment checked, excluded same-source normal references. Windows are nominal geometry locations, not measured physical contact points.
- Historical normal maximum-nearest-window MAE ranges raw.012037–.048303,CLAHE.027462–.080113. Historical subtle184100 lip scores.033555/.070366, overlapping normal ranges again. Fresh normal183823 scores.029102/.054519 and fresh184132 lip.093413/.126279. Thus pixel contact evidence distinguishes the larger fresh change but does not rescue the known subtle miss with these metrics; illumination/print texture remain confounders. Per-window nearest references may mix different normal scenes; no operational threshold fitted.
-3 tests passed: original input unchanged, spatial translation retained, clipping rejected. Output runtime/inspection/vrm_seating_pairs/contact_pixels_audit.json. No capture, training, runtime/API/threshold change or robot/conveyor command. UNKNOWN/ADVISORY_ONLY. These results do not prove that all image-based methods are impossible, but do not justify micro-lip acceptance using this diagnostic.

## 2026-09-07 full-contour nearest-normal stress check

- Added audit_vrm_full_contour.py, reusing symmetric raster boundary distance/IoU utility. Compared20 historical labelled VRM05 masks and2 fresh paired masks to16 historical normals, source/self excluded, shared raster offset only (no per-part pose correction). Weight/source hashes checked. Existing2 boundary metric tests passed. Output runtime/inspection/vrm_seating_pairs/full_contour_audit.json.
- Historical normal nearest-boundary p95 range1–6px and best-IoU range0.926863–0.989741. Historical subtle184100 lip has p95=4px,IoU=.952035, inside both normal ranges. Other3 historical pose failures have p95=7/9/10px. Fresh183823 FLAT2px/.977555,184132 SEATING18px/.835315. Full contour improves evidence over independent extrema but does not separate the known subtle miss from normal variability using either scalar metric alone. No joint-score optimization or implied physical-height proof.
- No camera action, training, threshold/runtime change, API restart or robot/conveyor command. Retrospective selected evidence only; UNKNOWN/ADVISORY_ONLY remains. Existing predicted contours cannot yet support a reliable micro-lip acceptance criterion; more replays of these scalar geometry metrics should not be presented as completion.

## 2026-09-07 historical normal envelope stress check

- Added audit_vrm_normal_envelope.py and3 passing synthetic tests. Reused frozen320 unique-mask saved outputs for20 explicitly pose-labelled VRM05 scenes (16 normal,4 FAIL), source hashes checked against current files/manifest. Built descriptive per-edge envelope from16 normal scenes; each historical normal excluded itself during its comparison. No threshold fitted or active rule changed. FAIL labels preserved as pose failures, not all relabelled seating.
- Fresh183823 FLAT lies inside historical envelope;184132 SEATING exceeds top by4px and bottom by17px. Thus the fresh movement is not solely a difference against one reference. However historical184100 confirmed subtle lip lies fully inside the same envelope, and4 historical normals show leave-one-out excess1–2px. The envelope alone cannot establish reliable subtle-lip detection or a calibrated socket clearance. Cross-scene extrema can also form combinations not physically valid as a normal pose.
- Artifact runtime/inspection/vrm_seating_pairs/normal_envelope_audit.json. Remains UNKNOWN/ADVISORY_ONLY; no capture, training, runtime/API change or robot/conveyor command. This is retrospective selected-control analysis, not independent validation or solved defect detection.

## 2026-09-07 fresh pair boundary displacement evidence

- Extended probe_vrm_lip_sampling.py with explicit timestamp:label scenes (historical defaults unchanged). CPU replayed frozen320 and640 on183823 FLAT/184132 SEATING VRM05, five artificial +/-1px crop windows each, near-identical mask grouping only.320 provided unique boundaries10/10, within-scene extent range<=1px.640 normal had one missing and one ambiguous sample, so its pair evidence is unavailable;640 not promoted.
- Added compare_vrm_pair_displacement.py: preserves fixed-frame displacement and reports range of extrema differences, not fitted thresholds, mm clearance, height or PASS/FAIL.320 lip-minus-flat edge ranges left[-1,0],top[15,15],right[-5,-4],bottom[22,23]px. Clear relative movement is observable on this pair despite classifier miss, but one normal placement is not the socket-wall geometry or complete allowed envelope. Does not resolve actual lip height or prove normal false-positive performance.
- Three synthetic tests passed: translation retained, missing boundary not component absence, unchanged boundary not PASS. Artifacts boundary320/report.json, boundary640/report.json, boundary_displacement.json under runtime/inspection/vrm_seating_pairs. No additional capture, training, threshold/runtime/API change, or robot/conveyor command. Remains offline UNKNOWN/ADVISORY_ONLY.

## 2026-09-07 paired miss export-path audit

- Replayed both fresh frozen spatial candidates on the held-out183823 FLAT /184132 SEATING VRM05 pair, CPU only. Native feature/head versus exported TorchScript maximum score error2.6077e-7, source-image hashes matched. No evidence that export or runtime preprocessing mismatch caused this pair's miss.
- CandidateA scores0.080632/0.003408; candidateB0.085902/0.002169 (flat/lip). Both reverse the required ordering, so a monotonic high-score defect threshold cannot accept this normal while rejecting this lip. This narrows investigation to learned evidence/generalization but does not establish a unique root cause or image-only height observability. No score inversion, threshold fitting, training ingestion, active provider change, capture, API restart or robot/conveyor command.
- Added audit_archived_vrm_pair.py; parity/hash/order assertions passed. Artifacts normal_spatial_check.json, lip_spatial_check.json, pair_failure_audit.json under runtime/inspection/vrm_seating_pairs. Other VRM slots have no new truth labels and were not counted as correct. Further improvement requires a new evidence/model approach evaluated on retained controls, not promotion based on this pair.

## 2026-09-07 fresh paired seating capture and frozen check

- After explicit instruction and user ready reply, captured flash-off S22 optical183823 (4000x3000,focal7mm); overview restored. Read-only preflight saw API alive but only COMPLETED request and no active inspection child; no server restart or motion command. This is manual evidence collection, not API completion.
- Added archive_vrm_seating_scene.py for single-target user-labelled fixed1.5x integer crop plus hash/provenance. Archived183823 VRM05 FLAT based on user instruction/acknowledgment, alignment0.9837045966. Crop visually viewed; no image-only height certification. Other slots unlabelled, whole-board normalfalse, development_pending_review, training_allowedfalse/ingestedfalse. Output runtime/inspection/vrm_seating_pairs/s22_inspection_roi_20260907_183823. No model/threshold changes; awaiting corresponding physical lip placement.

- Completed corresponding flash-off184132 capture after user's ready reply to lower-left lip placement instruction; archived VRM05 SEATING with alignment0.9832436520, same fixed crop geometry. Viewed both crops; physical label follows user placement acknowledgment, not image-only height measurement. No other-slot labels inferred.
- Added offline check_archived_vrm_pair.py and ran frozen candidate on CPU with physical presence assumed only for diagnostic scoring. SEATING score normal183823=0.0806323, lip184132=0.00340768: ordering is wrong and the actual lip is missed at diagnostic0.5. Both provider outputs remain UNKNOWN/ADVISORY_ONLY. This fresh pair disproves reliable generalization of this candidate to the requested lower-left lip; no threshold adjustment, retraining, runtime activation or PASS claim. JSON: runtime/inspection/vrm_seating_pairs/frozen_pair_check.json. Pair is not ingested for training. No robot/conveyor motion commands or API restart.

## 2026-09-07 boundary error against existing polygon labels

- Added audit_vrm_label_boundary_error.py with symmetric raster contour distance and extremum errors.2 synthetic tests passed (identical polygons,3px translation,invalid polygon). Compared same10 existing normal-only test crops with frozen320 last and640 best, CPU20 predictions, unchangedconf.25, original labels/weights hashed. Best-IoU oracle matching is evaluation-only; no runtime candidate selection from ground truth.
-320 boundary-p95 median3/worst4px, absolute boundary max worst7.2111px, extremum error median2.3522/worst4.4364px.640 boundary-p95 median2.6180/worst6px, absolute boundary max worst8.9443px, extremum median3.2159/worst6.3627px. Selected-case sampling stability did not translate into universally closer boundaries;640 not adopted. Approximate normal-only labels and reused tests do not establish physical1mm accuracy or subtle-lip sensitivity.
- Artifact runtime/inspection/vrm_label_boundary_error.json. No label fitting/threshold changes, active model change, camera/robot/conveyor/API action. Further repeated evaluation of these same examples should not be called independent validation or evidence of a resolved detector.

## 2026-09-07 dual-provider boundary evidence separation

- Added compare_vrm_boundary_providers.py and5 passing tests. Same scene/slot/source hash required; crop origins mapped into board coordinates without averaging/recentering. Missing segmentation returns boundary unavailable, not component missing; distinct candidates remain ambiguous; even identical boundaries retain UNKNOWN/unvalidated geometry. No fitted acceptance threshold or active fusion change.
- Compared115 saved rows from original320 last and candidate640 best with source SHA verification:104 paired single boundaries,3 ambiguities,8 unavailable pairs (includes empty slots; not8 detection failures). Paired maximum-per-edge discrepancies min1/median2/p905/max9px. Artifact runtime/inspection/vrm_dual_provider_comparison.json. Two-model agreement alone cannot establish actual1mm clearance or lip height. Candidate masks may be diagnostic evidence, never replacement presence/authoritative pose verdict.
- No capture, training, API restart, robot/conveyor commands or runtime model changes. This is offline evidence fusion behavior and retrospective disagreement analysis, not final micro-lip detection.

## 2026-09-07 expanded 640 boundary regression

- Extended saved-scene boundary validator with opt-in imgsz640,CPU and conservative duplicate grouping; default legacy320/GPU behavior preserved. Records raw central count and unique count, keeps distinct competing boundaries UNKNOWN instead of selecting largest when dedup mode enabled. Source hash/partition guards unchanged.
- Ran frozen640 best candidate across23 saved development scenes,115 VRM slots, excluding dataset/adaptation scene sources.92 explicitly PRESENT:89 unambiguous boundaries,2 no candidate(164343VRM03,150517VRM04),1 distinct competing boundary(165642VRM05).6 EMPTY:0 candidates.17 remaining slots have UNKNOWN presence labels and are not counted as correct. Saved old320 last report on same labelled scope has92/92 central candidates and0/6 empty responses; old primary selection semantics differ, but two new no-detection regressions are clear. Normal164343 overlay viewed directly.
-6 mask-dedup/scene-validator tests passed. New report under segmentation/runs/vrm_boundary_640_candidate_20260907/saved_scene_validation. No contour truth for these scenes, no measured1mm/height claim; retained development data are not blind accuracy. Candidate NOT promoted despite earlier selected-case stability improvements. No new training/capture, API restart, motor command or active model/threshold change.

## 2026-09-07 near-identical mask deduplication candidate

- Preserved all central mask candidates in sampling artifacts and reran640 candidate on3 controls. Normal181938 double masks had raster IoU0.999953/0.999027 and respective extrema differences[0,0,0,0]/[0,1,0,0]px. Therefore these specific ambiguities are near-identical duplicate predictions, not evidence of two distinct part/socket boundaries.
- Added vrm_duplicate_masks.py for diagnostic-only complete-link grouping:IoU>=.995 and extremum delta<=1px, highest-confidence representative, no chaining across dissimilar boundaries. These numerical duplicate tolerances are not measured assembly tolerances or independently calibrated production policy. Enabled only by probe --deduplicate; live provider untouched. Original candidates/groups remain in report.
-3 unit tests passed for exact duplicates, distinct edges retained, singleton/empty and malformed input. CPU15 replay predictions yielded unique candidate in each trial after deduplication; normal extent range[0,1,2,1],subtle[1,0,0,0],historical[0,1,0,0]px. Report runtime/inspection/vrm_lip_640_deduplicated/report.json. This resolves the sampled duplicate ambiguity but does not establish physically correct boundaries, clearance or seating detection accuracy; still ADVISORY_ONLY, not promoted.
- No new capture, GPU training, API restart, robot/conveyor command, label or active threshold change.

## 2026-09-07 isolated 640 boundary retraining

- Added explicit --imgsz320/640 to existing isolated trainer for train/test/preview and provenance, plus explicit weights selection in sampling probe. GPU initially idle; user-approved separate candidate trained40epochs (~0.054h),imgsz640,batch8,patience15 from frozen negative_v1 last. Dataset v4 unchanged108train/10val/10test; three retrospective sampling controls SHA-checked absent from dataset. No known holdout injection. Existing dataset/scene tests6 passed.
- Candidate runs/vrm_boundary_640_candidate_20260907 best SHA5c608446d99b16246ff3840773111b0164ee95ede3a90bf242b1b65e37a3de44. Normal-only reused test mask mAP50-95=.967, not defect/seating accuracy. Active six-class hash unchanged, runtime_enabled=false. Dataset/provenance retained by trainer.
- CPU15 sampling predictions at640:subtle184100 extent range[1,0,0,0]px and historical194959[0,1,0,0]px, compared with old320[1,1,2,0]/[1,0,6,1]. However normal181938 central candidate counts[2,1,2,1,1] make2/5 inputs ambiguous; no stable range reported. Historical confidence also varies.2784–.7941. Partial coordinate stability improvement is not correct-boundary proof or successful lip detection. NOT_PROMOTED due normal ambiguity and no independent metric boundary/seating qualification.
- Results runtime/inspection/vrm_lip_sampling_retrained640/report.json. No camera, API restart, robot or conveyor command; completed GPU training process exited. No active criterion change, candidate stays isolated.

## 2026-09-07 boundary inference resolution ablation

- Extended frozen CPU sampling probe with explicit320/640/960 input size and isolated output plus per-call elapsed time. Reused identical3 saved sources,5 input-window offsets each, unchanged negative_v1 last weights/conf.25/retina_masks. No labels, training, camera or active settings changed.
-640 and960 each yielded0 central candidates in all15 predictions. Repeated320 reproduced prior5/5 detections per source and extent ranges[1,0,1,0],[1,1,2,0],[1,0,6,1]. Thus enlarged inference input alone is rejected; no detection is not a normal verdict or zero measurement. Same source crops are interpolated, not higher optical resolution. Training320-to-inference-scale mismatch is a possible explanation, not established causality.
- Reports:runtime/inspection/vrm_lip_sampling_640,vrm_lip_sampling_960,vrm_lip_sampling_320_repeat.45 offline CPU predictions this turn, no runtime update, GPU training, API interruption or robot/conveyor commands. Micro-lip qualification remains unresolved; higher-resolution training and independently reviewed boundary labels would require separate validation rather than larger runtime imgsz alone.

## 2026-09-07 learned boundary input sampling sensitivity

- Reviewed existing annotation provenance and previous adapted/negative candidate work to avoid retraining the same rejected experiment. Existing three adaptation polygons are assistant-reviewed approximate body boundaries, not metrology ground truth. No label changes or holdout ingestion.
- Added probe_vrm_lip_sampling.py and ran CPU15 predictions with frozen negative_v1 last checkpoint, conf.25,imgsz320. Normal181938/subtle184100/historical194959 VRM05 fixed crops tested at unchanged origin and +/-1px x/y input-window shifts. Predicted coordinates mapped back into the same fixed crop; no object alignment, image enhancement, model fitting or live criteria change.
- Full five-sample extent ranges[left,top,right,bottom]px:normal[1,0,1,0],subtle[1,1,2,0],historical[1,0,6,1]. The known historical missed-defect right boundary is sensitive to sampling even when every sample yields one central candidate. This is artificial input-window sensitivity, not physical movement, measured uncertainty certification, independent accuracy or a proposed new cutoff. Store report/source/checkpoint hashes in runtime/inspection/vrm_lip_sampling_sensitivity/report.json.
- No new capture, GPU job, server interruption or motor command. Active models unchanged. A confident mask alone must not establish exact clearance; independent boundary truth and measured repeatability remain prerequisites for any stability-based runtime guard.

## 2026-09-07 explicit lip boundary evidence probe

- Inspected saved same-view VRM05 normal181938, subtle-lip184100 and historical lip194959 images. Both normal and defects show a dark lower gap; appearance alone was not used to change physical labels. Extended existing boundary consensus probe with explicit cross-date image paths and slot filtering; padded montage rows and checked image write. No criterion or model activation.
- Ran unchanged raw/CLAHE multi-band edge probe on10 slots across181938/184100 and three explicitVRM05 controls. For normal181938, subtle184100 and historical194959:band-peak spread63/22/52px; raw-versus-CLAHE median-edge disagreement9/10/3px. These are estimator inconsistency in crop pixels, not physical clearance or part displacement. Candidate rectangle often follows a competing socket/part edge; lower disagreement in194959 does not prove correct boundary. Not suitable for independent FAIL or PASS.
- Artifact runtime/inspection/vrm05_three_seating_boundary_controls/comparison.jpg and report.json visually reviewed. Initial .venv_obb lacked sklearn; reran successfully using existing .venv_patchcore without installation. No new capture, model fit, active threshold, API restart, robot/conveyor command. Need independent boundary/seating evidence rather than relabel these reserved cases or fit a cutoff to them.

## 2026-09-07 frozen fresh seating regression comparison

- Resumed offline VRM work without interrupting teammate API tests. Added audit_fresh_seating_regressions.py:13 explicit controls (8 user-reviewed seating controls,4 fresh reserved exposures from2 placements,1 historical miss). Verified available source-image SHA256, unique non-train matching rows and evaluation hashes. No refitting, threshold search or runtime promotion.
- At existing diagnostic0.5 plus-session/fresh candidate has2 missed seating defects and2 flat-seating warnings; seating-only/fresh has5 misses and0 flat warnings. Two common misses:184100VRM05 scores0.485386/0.032922;194959VRM05 scores0.226286/0.016315. Five disagreements. Hence voting/OR of these two candidates still misses2 known defects; merely switching models trades sensitivity for warnings. These are retrospective controls, not independent accuracy; flat-right-wall seating labels do not override separate process-clearance errors.
- Artifact runtime/inspection/fresh_seating_regression_comparison.json. Existing candidate remains disabled/advisory; no camera, robot/conveyor, network or server action. Further work must improve boundary/height evidence or independent defect training, not tune the reserved missed cases into passing validation.

## 2026-09-07 persistent API credential and pending DHCP reservation

- Persisted existing team-shared token in ignored config/private/vision_api.token (parent700/file600); token not recorded in logs/docs. Dedicated API launcher environment loader prefers saved64-hex token, preserving current client credentials across restarts. Both API launchers load it; other ROS launchers do not. Shell syntax and secret-free load check passed; git check-ignore confirmed exclusion. No running process restart, capture, robot/conveyor command or external transfer.
- Read-only host network check:main wlo1 DHCP192.168.11.4/24 via192.168.11.1, MAC40:D1:33:FA:16:A8; GoPro secondary10.5.5.113 unchanged. IP pinning NOT completed:router DHCP reservation required; pool/config/admin access unavailable. Did not set a potentially conflicting manual address or reconnect the live network. Handoff documents exact reservation pair and pending state.

## 2026-09-07 fresh manual JSON PNG handoff

- User requested fresh teammate sample. Manual optical capture172349 (4000x3000,flashOFF) and hybrid172359_755455 completed exit0; overview restored. FinalUNKNOWN,25 UNKNOWN slots,4 advisory findings,0 confirmed defects. No motion or external delivery.
- Added prepare_manual_handoff.py to reuse actual API result preparation without inventing production IDs. Verified PNG copy SHA256, wrote exactly JSON+PNG under runtime/inspection/team_json_png/4bf88dbb-5981-4bfa-9fca-4eda51b40c0a. test_only=true, MANUAL_FILE_PAIR, UNBOUND, job_id/unit_id=null,image.path=null because no API request exists. Local full archive is outside the share folder, no ZIP created. This validates file preparation from a fresh real image, not physical HTTP/Sequencer integration. No model/threshold change.

## 2026-09-07 JSON and annotated PNG transfer

- Replaced ZIP HTTP evidence with GET inspections/{id} JSON and authenticated GET inspections/{id}/image returning02_annotated_report.png. JSON preserves overall decision,25 slots, named findings/details, confirmed-only defects and advisory authority; image descriptor has MIME/size/SHA256. Old /evidence route404; old persisted ZIP records remain local and advertise image unavailable rather than stale download links. Request IDs, single-flight, station gate and model authority unchanged.
- Added create_archive=false exporter path for API use (including package reuse): full original/raw/heatmap metadata remains local, but no new ZIP is built by API. One request-owned annotated PNG is copied without changing pixels; hash checked before HTTP download. Offline legacy ZIP exporter remains available; no existing evidence deleted.
-22 pytest tests passed, including authenticated localhost JSON/PNG roundtrip, removed ZIP route, corrupted PNG rejection, no-archive preparation/reuse,25-slot UNKNOWN/advisory retention and legacy record handling. No camera capture, motor command, DB write or remote upload. Team contract updated in team_handoff/vision_sequencer_api/README.md; running server requires restart to load changed code. Physical Sequencer acceptance still pending.

## 2026-09-07 actual capture and inspection smoke test

- User authorized real capture. Existing camera/ROI processes active; read-only ROS checks found inspection stop_trigger=true but /conveyor/moving had no sample within10s and no remote server process was observed. Request API precondition was not bypassed or forged. Full request-driven physical integration remains unverified.
- Executed manual run_triggered_board_inspection.sh once, event runtime/inspection/manual_api_capture_test_20260907.json. S22 flash OFF, actual optical4000x3000/focal7mm/35mm69mm image s22_tele_3p5x_20260907_170534.jpg; fresh ROI170534 and hybrid run20260907_170544_597609. Overview released and restored successfully. Pipeline exit0, registration0.9856879948, finalUNKNOWN,4 advisory slots:GPU direction,HBM03 missing,SMD01 position,VRM05 position. Report image visually reviewed; these remain unconfirmed candidates, not production defects.
- Actual-result offline exporter succeeded:db_outbox/INSP-20260907-170534-F1F6C43567.zip,UNKNOWN,4 findings,deliveryNOT_REQUESTED. No synthetic production IDs, API request, DB/server upload, robot/conveyor command, model or threshold change. Existing camera settings retained. Next physical API test needs genuine fresh conveyor stopped heartbeat in addition to arrival; not a reason to fabricate status or start armed motion service without authorization.

## 2026-09-07 Sequencer request and evidence pull backend

- Added authenticated asynchronous POST request / GET state / GET ZIP API in integration/inspection_api.py. Sequencer UUID inspection_id/job_id and positive unit_id are persisted before capture. Identical retries return existing state; conflicting IDs and concurrent new requests return409. Interrupted records restart FAILED without recapture. Admission and pre-capture checks require fresh arrived=true/moving=false samples held0.35s; these are software prerequisites, not a physical safety guarantee.
- Existing hybrid contract and candidate authority unchanged. COMPLETED+UNKNOWN remains uncertain; FAILED denotes execution failure. Evidence packaging failure preserves completed decision with evidence.ready=false. Exporter supports request-issued UUID; source report/candidate images and metadata remain archived. Confirmed-only result summaries use slot_code/defect_type. ZIP SHA256 verified before serving.
- Removed automatic MainServer upload from one-shot pipeline. Default conveyor inspection wrapper now starts request backend, arrival-only behavior requires explicit --legacy-arrival-trigger. Shared process flock prevents concurrent legacy/API auto triggers. API inherits lock into pipeline child and terminates child process group on timeout/shutdown. No motion service calls, DB access, model updates, or camera setting changes.
- Verification:20 pytest checks passed including local HTTP auth/accept/query/evidence roundtrip, duplicate/restart/UNKNOWN/busy/not-ready/freshness, request UUID export, existing exporter and mocked pipeline regressions. Bash syntax passed. Loopback socket test required sandbox escalation; no actual photo, robot/conveyor command, teammate integration or deployment occurred.
- Handoff:team_handoff/vision_sequencer_api/README.md. Prior direct-upload handoff README marked SUPERSEDED; historical patch/archive retained. Restrictions: trusted LAN or TLS proxy, single process, no API cancellation/retention daemon, no physical timing guarantee, manual latest-producing scripts must not run concurrently. MainServer-to-Sequencer endpoint is team-owned. Actual ROS/S22/Sequencer acceptance remains required before production use.

## 2026-09-07 fresh seating candidate bridge and actual provider checks

- Resumed seating work after file-receiver handoff. Contract reread. Separate seating-only+fresh candidate `vrm_seating_only_fresh_vrm5_20260907` trains84 existing/development crops only; fresh validation2/4 (right-lip misses), historical4/5. Rejected, not substituted for the earlier plus-session+fresh candidate. No validation ingestion or runtime threshold tuning.
- Extended existing exporter with explicit --source (default unchanged), exported earlier114-train plus-session+fresh4x4 candidate to its own integration_bridge. Frozen source SHA256089f34972eeded50f6240dd1085ed7d74aa4706cd3efa3a098e9dbd651ea62df. Synthetic trace logit error0. Metadata remains runtime_enabled=false, validated=false, sentinel thresholds0/1; no active provider replacement.
- Added/executed check_fresh_vrm_bridge.py:12 real fixed crops, production VrmSeatingClassifier preprocessing and actual VrmStateClassifier presence gating in memory only, diagnostic .5 threshold. Max score difference1.19209e-7. Fresh normal144354/144420 yield no seating nomination; right-lip144819/144846 yield SEATING? through actual presence gate. Weak presence returns UNKNOWN; fusion always UNKNOWN. Results integration_bridge/fresh_provider_check.json. This is not a full-board deployment test or universal seating coverage; historical misses still apply. No new camera/robot/conveyor command or production configuration change.

## 2026-09-07 MainServer file-only receipt and optional automatic export

- Reviewed remote Main_Server&DT commit1c1c56519a294a0f15a044bc0629e3a1d823b9f2 in isolated /tmp clone. Existing XLSX/report worker is present, Vision ingress absent. Prepared patch touching existing MAIN_SERVER/server.py and API registry only; no remote push, DB migration, Unit/Job writes, mail or production action. Handoff `team_handoff/vision_file_receiver` contains patch, receiver tests and Korean application guide. New route POST/api/v1/vision/inspections reuses existing HTTP server; authenticated multipart,64MiB cap, relative-path/role/hash/signature checks, private staged files/fsync/rename, same-content idempotency and409 conflicts. Single process per root; no full image decode, DB identity verification, retention daemon or public-internet hardening claim.
- Existing Vision exporter now accepts UUID job_id and positive integer unit_id/null, refuses mismatched reused package IDs, checks raw report integrity, rejects redirects and requires matching stored/inspection_id/key/production_applied=false ACK. UNKNOWN/advisory remains unchanged. No fabricated production IDs. MainServer receipt binding remains UNBOUND/UNVERIFIED, never permission for automatic countermeasure issue.
- Existing triggered_inspection_once.py default now current hybrid25slot launcher/reports, with report-image identity check. Optional KSMC_VISION_EXPORT=1 packages exact result and optionally sends to KSMC_VISION_ENDPOINT; default off. Context file snapshot optional/unverified; production-bound lifecycle handshake remains unimplemented. Delivery LOCAL_ONLY/STORED/PENDING_RETRY separate from inspection status. Existing local outbox supports explicit same-report retry; no auto retry daemon. No camera settings, motor/interlock logic or stop lines changed.
-16 tests pass: receiver storage/auth/path/hash/conflict/concurrent duplicate/disk failure, actual sender-localhost receiver roundtrip, IDs/redirect guards, pipeline freshness and delivery-error separation. DB/ROS modules stubbed in receiver tests; no team DB/live server/Unity/end-to-end conveyor test. Python compilation and reverse patch applicability check passed. Initial sandbox socket failure rerun with local-network approval. No physical capture/robot/conveyor command issued. Real server URL/token and team patch application still required; no live transmission enabled.

## 2026-09-07 fresh VRM05 controlled training and right-lip validation

- Completed six physical scenes/twelve captures: normal-left143009/143100, lower-leftlip143324/143438, normal-reseat143855/143922, upper-leftlip144137/144204 for development; independent normal144354/144420 and right-cornerlip144819/144846 for validation. User explicitly identified final corner as right (upper/lower unspecified). Sidecars preserve labels only forVRM05 and repeated-scene split grouping; no whole-board normal labels. Original RGB fixed-slot crops, flashOFF4000x3000/69mm, overview restored; no robot/conveyor commands.
- Extended offline evaluator with opt-in --fresh-vrm5 and separate output requirement, fixed explicit six sidecars, source/sidecar hashes, duplicate fresh-source rejection, registration validation, training exclusion for validation, physical-scene split guard. Added8 development crops to existing106 train only. Fresh4 validation crops never fitted. `vrm_seating_fresh_vrm5_20260907` contains model, exact fresh_manifest and crops. Syntax checked; new right-lip crop visually inspected. No production model or threshold changes, no authoritative vote.
- New candidate at unchanged diagnostic .5: fresh normal .077687/.008804 and right-lip .998482/.978039 correctly separated. This is TWO physical validation placements with repeated exposures, not four independent placements or production accuracy. Train114/114, old normalvalidation10/10. Historical194959VRM05 still missed .226286; historical subtle184100VRM05 .4854 also below cutoff; old flat-right-wallVRM02 warnings persist. Mixed-session96/100 not proof of seating performance. Candidate stays offline, not wholesale promotion; existing UNKNOWN preserved. Fresh data helps the new test but does not establish universal lip detection.

## 2026-09-07 seating training coverage and required physical controls

- First requested normal-left development placement captured143009/143100 after user reports all VRMs pushed left. Same physical scene, two repeats; sidecar `runtime/inspection/vrm_normal_left_20260907_143009.json`, only requestedVRM05 FLAT label, no whole-board normal ingestion. First full ROI visually inspected: mixed GPU inversion/HBM vacancy still visible, so whole-board normal training forbidden. Frozen model first frame gives no VRM warnings, VRM05 .00000411; diagnostic only. FlashOFF,4000x3000/69mm, overview restored after both captures. No model/training or robot/conveyor command. Next physical placement: only VRM05 lower-left subtle lip.

- Direct manifest count for vrm_seating_v3:68 flat/8 seating train crops,10 flat validation,4 flat/1 seating holdout. Eight seating crops come from only two physical_scene_id groups and VRM01/02; no VRM05 training seating. This is limited coverage, not eight independent defect placements. Prior plus-session training adds generic placement defects, not equivalent verified VRM05 subtle seating modes.
- Prepared `config/vrm_seating_capture_plan_20260907.json`: fresh flat/lip paired development placements, then independently reseated normal/lip validation; two repeat shots per physical placement kept together. Scope only explicitly confirmed VRM05, other slots unlabelled, old hard regression controls remain excluded from training. Physical intervention now required for first normal-left placement. Plan is not executed or automatically ingested; no new labels/photos/model changes claimed. Existing optical setup retained, no robot/conveyor command.

## 2026-09-07 expedited finer-grid candidate rejected

- User requests rapid completion. Ran frozen B0 early/final7x7 logistic C1 on existing106 explicit training crops only, separate artifact `runtime/inspection/vrm_seating_multiscale7_20260907`. No new capture, holdout training or production model replacement. Train106/106, validation10/10; historical holdout4/5. Mixed session96/100 is not independent seating accuracy and does not override hard controls.
- Known subtle-lip184100 VRM05 score .0503 misses at frozen .5 cutoff; normal seating185803 VRM02 .8793 still warns. Historical194959 VRM05 remains a miss. Finer spatial pooling did not resolve the problem and is rejected for deployment. Preserve existing UNKNOWN/advisory operation rather than promote based on aggregate agreement or tune on known test defects. No camera, robot or conveyor commands; no live criterion change. Limited optical seating sensitivity remains unresolved, not completed.

## 2026-09-07 explicit seating controls and label provenance correction

- Read full holdout scene metadata:184100 VRM03 FAIL has explicit additional user physical review (very slight lip), not merely an assistant-inferred collateral label. Earlier suggestion that this label might be stale was not substantiated; preserve it. VRM02 in184100/185803 is physically flat against the right wall while separately marked process POSITION_ERROR for gripper clearance. These are compatible task-specific facts, not a label contradiction or unconditional normal assembly.
- Added `audit_seating_controls.py`, eight explicitly labelled slots across four source images181938/183451/184100/185803, verifies image hashes and exact model/source association, fails on missing evidence. Comparison artifact `runtime/inspection/seating_explicit_controls_20260907.json`: old plus-session6/8, seating-only6/8. Old misses two flat VRM02 seating controls; seating-only misses two subtle-lip controls (184100 VRM03/05). Equivalent totals hide different failure modes. Repeated/development controls, NOT independent accuracy; historical194959 miss remains outside this eight-control subset and is not forgotten.
- Preserved separate lateral-process metadata, disabled training/promotion in artifact. No production labels, thresholds/models, camera or robot/conveyor commands changed. Initial audit correctly stopped because the old evaluation predates added scenes; resolved using source-hash-checked frozen per-scene reports, not fabricated entries. Neither candidate qualifies for unconditional deployment.

## 2026-09-07 seating-only training ablation rejected

- Reread fusion contract. Existing plus-session candidate merges historical seating with rotation/translation placement labels. Ran existing `evaluate_vrm_spatial_seating.py --multiscale --pool-size 4` WITHOUT session training, separate output `runtime/inspection/vrm_seating_only_multiscale_20260907`. Frozen B0 features + logistic C1;76 existing train crops only, no reserved validation/holdout ingestion, no image transformation change. Original active artifacts untouched.
- Train76/76, validation10/10, historical holdout4/5 agreement at preexisting .5 diagnostic cutoff. Mixed-session evaluator prints84/100, but that set mixes rotation/translation/seating and includes potentially stale collateral-slot labels (184100 VRM03); do NOT present it as seating accuracy. Explicit user-labelled controls: normal185803 VRM02 score falls from .880559 to about .0082, eliminating that warning; lip183451 VRM05 .563 flags; subtle lip184100 VRM05 .0645 now MISSED. Thus removing session training reduces one false warning but worsens known subtle-lip sensitivity. Candidate rejected for runtime promotion; no threshold tuning to reverse this outcome.
- This is a completed negative ablation, not a deployed improvement. No camera capture, robot/conveyor motion or production model changes. Remaining need is label/task separation and additional discriminating features/training coverage; preserve hard controls outside training and correct collateral labels only from explicit physical truth.

## 2026-09-07 seating model path and promotion blocker audit

- Active provider reads `slot_classifier/models/vrm_seating_candidate/vrm_seating.json`: runtime_enabled=false, DEVELOPMENT_ONLY_FAILED_CROSS_SCENE_REGRESSION, explicit blocker normal VRM01 false seating nomination in mixed145130. This is an intentional guard, not accidental loss of model loading. The previously successful frozen multiscale model is a separate artifact `vrm_multiscale_seating_plus_165057/candidate.npz`, SHA256 f27f5fc842dade6e48c1accb39243391b3e1b8289ea0d3d13a857e864a398002; do not conflate the two or blindly flip metadata.
- Replayed frozen model without fitting on four original images; outputs `runtime/inspection/vrm_seating_model_audit_20260907`. Current134016 user-confirmed normal VRM03/05 scores .00000872/.00000297, no warnings. Historical subtle-lip184100 VRM05 .623486 flags at existing diagnostic .5 cutoff. Known defect194959 VRM05 .262353 still MISSED. Normal185803 VRM02 .880559 still false warning (under recorded seating truth; later gripper-clearance policy is a separate criterion); normal VRM03/05 .136908/.036510 do not flag. Thus neither lower cutoff nor wholesale model restoration is justified. Scores are uncalibrated, not defect probabilities. Historical data/development reuse is not independent validation.
- Initial .venv_obb execution failed for missing sklearn; reran successfully in existing .venv_patchcore without installing dependencies. No runtime integration, criterion change, training, capture or robot/conveyor commands. Next model work must retain known hard normal/defect controls and distinguish seating appearance from lateral process-clearance criteria. Current final UNKNOWN retained.

## 2026-09-07 VRM05 confirmed lip replay exposes existing misses

- Full current GPU inference on preserved20260905 sources181938(normal),183451(lip),184100(user-confirmed subtle lip), outputs `runtime/inspection/vrm05_subtle_regression_20260907`. VRM05 has no candidate in all three: one normal agreement and TWO confirmed defect misses, not successful validation. Native184100 VRM05 crop visually inspected; physical labels follow prior user clarification, not current image inference.
- Candidate replay with new disagreement predicate disabled STILL yields no VRM05 candidate in all three. Thus these misses predate that abstention, not caused by it. Corrected radial offsets .53650/.38481/.23687mm all below .70 advisory gate. Current PatchCore scores .62424/.58449/.60310 do not separate this normal from lip defects with a simple high-score cutoff. Presence predicts CORRECT for lip183451, boundary uncertain; seating stage explicitly DISABLED (`VRM_SEATING_CANDIDATE_NOT_RUNTIME_ENABLED`). Historical frozen seating scores .028589/.987525/.623486 from prior record are a DIFFERENT model/path, not current PatchCore scores.
- No runtime threshold, model, authority or training changes. Final UNKNOWN remains; no camera/robot/conveyor commands. Next work is audit the previously evaluated seating model and why it was withheld, then test normal and known historical misses before any advisory integration. Do not simply enable an unvalidated model or lower threshold on these defect examples.

## 2026-09-07 VRM disagreement abstention regression

- Extended offline candidate-only replay via `audit_vrm05_abstention_history.py`:338 historical reports,13 changed reports covering9 unique input images; zero other-slot candidate changes. Artifact `runtime/inspection/vrm05_abstention_history_20260907.json` preserves before/after lists. Includes known left-seat160026 and current confirmed-normal134016; other historical images lack independently reconfirmed VRM05 truth and cannot be counted as correct suppressions. Historical versions/repeated images and absent boundary stages limit this audit: it does NOT establish subtle-lip sensitivity. No runtime criteria or model changes, capture or motion in this follow-up.

- Added VRM05-only calibrated-centroid nomination abstention when presence predicts CORRECT and a confident (>=0.90) independent boundary has no codes and all three position features remain inside its existing reference uncertainty. Missing, nonfinite, weak or out-of-envelope evidence cannot invoke this rule. This is measurement disagreement, NOT normal certification: raw pose, common-bias correction, UNKNOWN fusion and other defect branches remain intact. The shared-bias estimator itself is NOT repaired; no part-local realignment or model training was performed.
- Three saved-image GPU replays completed under `runtime/inspection/vrm05_disagreement_regression_20260907`. Current user-confirmed-normal VRM03/05 scene134016 (report140032_445508) now displays only GPU direction, HBM03 missing and SMD01 position; rendered report visually inspected. Prior right-lip scene20260906_171520 (140057_312602) retains VRM05 RIGHT?/DIR?/POSE? and VRM03 POSE?. All-right scene20260906_155131 (140119_947897) retains RIGHT? for all five VRMs. These retained/development examples are not independent generalization evidence; small real offsets inside boundary uncertainty can still abstain.
- Hybrid, boundary and disagreement unit tests:78 passed. Contract authority remains ADVISORY_ONLY; no absent nomination means PASS. No fresh camera capture, robot or conveyor command was issued. Remaining work: stable board-based metrology/common-bias diagnosis and independent near-boundary false-negative validation before authoritative decisions.

## 2026-09-07 VRM mixed-scene false-positive diagnosis

- Implemented one-native-pixel RIGHT? boundary guard after `audit_vrm_boundary_pixel_guard.py` replay: fixed deployed reference controls retain0/30 left-seat nominations and7/7 right-shift nominations. Repeated/development observations, not independent physical1mm accuracy. Both centroid and extreme-edge exceedance must be>1px beyond existing bounds+margin; <=1px abstains UNKNOWN, never PASS. Rotation and model/ref geometry unchanged. Evidence now records right_excess_px/right_pixel_guard_px. Latest confirmed-normal VRM03 excess[.4376,1] no longer nominates. Hybrid/boundary suite75 passed. Full original134016 GPU replay `vrm_pixel_guard_integrated_20260907/135228_106731` retains GPU direction/HBM03missing/SMD01position, removes VRM03, still flags VRM05. VRM05 correction issue NOT fixed. No new capture, motion or training; fusion contract reread, ADVISORY_ONLY retained. No margin change to physical PM1 clearance policy.

- User confirms VRM03/05 fully normal/not close toPM1 in134026. Compared prior zero-candidate132341 with mixed134026 via `audit_vrm_mixed_false_positive.py`, artifact `runtime/inspection/vrm_mixed_false_positive_audit_20260907.json`. VRM05 raw centre changes[-.00630,+.03740]mm, but shared bias changes[-.05761,-.17135]mm; current radial.82810 vs counterfactual old-bias.64735 crosses.70 nomination gate. Estimator uses component-wise median over confidence>=.50 components, not fixed board features; membership changes (HBM03 removed, SMD04/VRM04 enter). Thus correcting from variable part population is a demonstrated contributor to this FP. Do not deploy previous-frame frozen correction, which would introduce stale/order-dependent state.
- VRM03 right-boundary centroid shifts+.92148px and extreme edge+1px; exceeds respective max+margin by only.43761px/1px. Its ordinary pose is within limit. Both boundary estimators derive from one mask; current strict comparison is sensitive to tiny mask/reference changes. True wall clearance is not measured. No permissive margin change made without prior right-shift defect regression.
- Read-only report/code audit plus standalone offline calculation; no camera, robot/conveyor motion, model or runtime criterion changes. Existing mixed GPU/HBM/SMD ground truth retained; no whole-board normal label. Next implementation requires reference-stable correction and boundary uncertainty treatment with retained true-defect controls.

## 2026-09-07 SMD01 missing-YOLO outline fallback

- User explicitly confirmed VRM03/05 in latest134026 are fully normal and not PM1-side close; prior extra flags now confirmed FALSE POSITIVES for these slots, sidecar saved. Mechanisms differ: VRM03 boundary model centroid94.996px and right edge159 exceed learned left-seated envelope; ordinary auxiliary pose0.3406mm/0deg and stateCORRECT0.98665. VRM05 ordinary pose radial0.8281mm crosses0.70 advisory gate primarily due corrected longitudinal_y0.7810mm (x0.2754mm), not proof of PM1 clearance; raw_y-0.18415mm minus shared bias-0.71621 and slotreference-0.2489 yields+0.78096mm. StateCORRECT0.98703, boundary itself UNCERTAIN. Do not label these true faults or train whole mixed board normal. No criteria changes pending reference/bias regression. User confirmation, not image speculation, supplies physical truth.

- First fresh post-fallback mixed capture134016/report134026_750188 detects expected GPU DIRECTION?/HBM03 MISSING?/SMD01 POSITION?. Independent SMD contour valid, spread0.511px, CLAHE support0.9959, raw_y-1.67967mm, PatchCore0.581664. Full visualization inspected. VRM03/05 additional POSITION? persist and physical truth remains unconfirmed; do not call whole mixed result clean. Final UNKNOWN, same physical placement repeat, no criteria/model changes or training. Flash off, overview restored, no robot/conveyor motion. Next isolate remaining VRM flags without shifting them before physical confirmation.

- Integrated guarded independent SMD01 measurement only when auxiliary pose reason is YOLO_AUXILIARY_CANDIDATE_MISSING and board alignment is valid. Fixed180x140 window follows existing slot geometry; no recentering/rotation. Raw-bright thresholds100/130/160 cross-check body consistency; local grayscale CLAHE2.0/8x8 Canny50/120 corroborates contour within2px (>=.60 support). Reject multiple >=500px bright regions, small/unresolved body, edge touching, oversized body>45%, invalid shape/dtype and centroid spread>3px. These engineering gates are not calibrated probability or lift metrology. Original learned RGB unchanged.
- Separate `smd01_outline_evidence` exposes measurement without overwriting failed/missing YOLO evidence or adding PASS authority. Presence>=.90 + PatchCore>=.10 + same frozen signed-y interval are still required; missing/invalid evidence and poor alignment cannot nominate. Uses existing SEATING? -> POSITION? advisory display only. Other components unchanged; final UNKNOWN retained.
- Guarded measurement resolves20 retained normal/defect crops; six image tests pass (body preservation, blank, fullbright, multiple bodies, tiny glint, bad window). Hybrid + previous small-lip + image suite82 passed, then additional independent-gate test passed in11-test small-lip suite (83 distinct tests across these suites). Full original-image GPU replay: mixed132808 in `smd01_independent_integrated_20260907/133738_730173` now detects GPU direction/HBM03 missing/SMD01 position; SMD01 raw_y-1.68438mm, CLAHE edge support1.0, spread0.464px. VRM03/05 additional position candidates remain unconfirmed, not labelled correct. Normal132331 replay133803_383849 has zero candidates. Mixed visualization directly inspected. No new physical trial after fallback integration yet. No camera, robot/conveyor motion or training in this change. Single-object reflections could still resemble a body; this is limited advisory recovery, not a certified surface/height detector.

## 2026-09-07 SMD01 small-lip advisory integration

- Offline independent bright-body probe `probe_smd01_independent_outline.py` resolves native fixed-window SMD01 contours in20 labelled retained images including mixed132818 where YOLO has no candidate. Raw-gray thresholds100/130/160 consensus centroids spread0.24–1.10px; mixed0.464px at local[103.518,50.886]. This shows missing segmentation does not imply absent optical outline. All cases within3px probe consistency, no claimed calibrated confidence/height; empty/fullbright synthetic rejection and source-preserving body-centre tests3/3 pass. Result `smd01_independent_outline_probe_20260907.json`. Probe remains OFFLINE: not a production fallback, no new runtime criteria or training/capture/motion. Needs ambiguous/multiple bright-object rejection and contract-compatible local OpenCV corroboration before use; no false claim that current live miss is fixed.

- IMPORTANT mixed prospective trial132808/report132818_028086: expected GPU180/HBM03empty/SMD01upperlip. GPU DIR? and HBM03 MISSING? detected, but SMD01 MISSED after integration because YOLO auxiliary candidate absent (poseUNKNOWN/confidence0/no coordinates). Presence0.98283 and PatchCore0.540598 (slot exceedance fraction0.9877) indicate appearance evidence but no independent geometry for supplemental gate. Native crop inspected; do not treat missing segmentation as no part or normal, and do not claim three-defect success. Additional VRM03 RIGHT?/VRM05 POSE? need physical truth verification; not relabelled confirmed errors. Preserve observation sidecar and exclude from normal training. No rule changes in this trial. Final UNKNOWN, flash off, overview restored, no robot/conveyor motion. Remaining failure mode: independent non-YOLO pose/outline fallback needed for strongly changed SMD appearances; presence/anomaly alone does not prove lift height.

- First fresh post-integration live capture132331/report132341_467727 completes with zero advisory candidates across25 slots; SMD01 PRESENT, score0, raw_y0.00633mm, final UNKNOWN. Native SMD01 crop inspected. This confirms no nomination on the current restored scene, not authoritative all-board PASS or additional physical labels. Flash off, overview restored, no robot/conveyor motion. No further model/rule changes or training.

- Integrated `smd01_small_lip.py` into candidate display only. SMD01 requires PRESENT>=0.90, outline>=0.20, PatchCore>=0.10 and signed raw-y outside frozen[-0.706171743866015,+0.4333002412865324] nominal-mm envelope (development normal extrema plus0.25mm margin from prior sensitivity sweep). This is NOT socket clearance/calibrated metrology. Existing common-bias corrected measurements and all old rules remain unchanged; no part-local alignment, normal training or other-slot change. Missing/invalid/nonfinite evidence cannot activate the new branch. Existing candidate maps now show the original PatchCore evidence when nominated; no artificial heatmap fill. Internal SEATING? maps to user POSITION? only, not a claim of measured lift height.
- Rule metadata is included in inspection JSON, all authority ADVISORY_ONLY. Final fusion PASS/FAIL remains unchanged and UNKNOWN here. Raw registered RGB learned inputs and fixed-slot contract retained; contract reread. Raw-frame calibration sensitivity and limited geometry/lighting coverage remain limitations.
- Tests76/76 pass; saved-evidence integration replay19/19 expected (10 normal,9 defect, repeated/development placements included), raw stages unchanged, all other-slot semantic codes unchanged. Not19 independent accuracy trials. Full original-input GPU runs under `runtime/inspection/smd01_integrated_full_20260907`: formerly missed120931 now POSITION?/SEATING? in131920_674802, normal131057 remains no SMD01 candidate in131945_771783. Defect visualization directly inspected; slot box and actual anomaly map visible. No current camera capture or robot/conveyor motion during integration. No claim of production-ready PASS or universal small-lip coverage.

## 2026-09-07 Pose display audit visibility

- Lower-lip restoration131057/report131107_594576 completes the prospective upper/lower/restoration sequence: no SMD01 live nomination and no supplemental nomination at any frozen margin, raw_y-0.02839mm/score0. No refit or training. Latest four prospective captures (upper repeat, restore, new lower defect, restore) match intended SMD01 candidate behavior for offline supplement; this is limited scene validation, not calibration of final PASS/FAIL. Native crop reviewed; supplemental branch still not live. Flash off/overview restored/no robot or conveyor motion. Stop requesting unchanged normal repeats for this sequence; any subsequent implementation must retain advisory authority and document nominal raw-frame reference sensitivity.

- Prospective opposite-side SMD01 lower-lip trial130750/report130800_689089: current live rules already nominate POSE?/SEATING? -> POSITION?, mask4892.5, score0.146912, outline0.49720, presence0.99796, raw_y+0.96042mm. Frozen supplemental sweep also nominates at all four margins without refit. This is one new opposite-side defect placement, unlike prior same-placement repeat; cannot establish full coverage. Sidecar preserved, native crop reviewed. Supplemental rule remains offline; no live threshold/model changes or training. Flash OFF, overview restored, no robot/conveyor motion, final UNKNOWN.

- Frozen small-lip sweep prospective capture checks: unchanged upper-lip121819/report121829_086609 and restored-normal122054/report122104_842085. No refit: all four preexisting margins.20/.25/.30/.35 nominate repeat defect (raw_y-0.81575mm, score0.265935, outline0.45883, presence0.99947); none nominate restoration (raw_y-0.26379, score0). Live unmodified code misses repeat defect and shows no SMD01 nomination on normal. Thus supplemental rule has one same-placement repeat and one new restoration check, not independent defect geometry validation; remains OFFLINE, final UNKNOWN. Candidate-validation sidecars preserved, native crops reviewed, no normal training admission. Flash off, overview restored, no robot/conveyor motion. Still need independent lip-placement evidence before live adoption; do not claim live miss resolved.

- Small-lip alternative evaluated OFFLINE in `audit_smd01_small_lip_candidate.py` on8 explicit normal and7 defect current-report samples (includes repeats and latest motivating miss). Supplemental branch combines PRESENT>=.90, outline>=.20, existing SMD01 score>=.10 with raw signed-y outside normal envelope; no large-mask condition. Nominal margin sweep.20/.25/.30mm produces0normal flags and7defect nominations with existing rules; .35mm loses latest defect (6/7). This narrow sensitivity and normal-defined envelope are not calibrated clearance or independent accuracy; newest defect motivated design. Output `runtime/inspection/smd01_small_lip_candidate_20260907.json` preserves all cases and margins, no selected live threshold. Fusion contract reread; no runtime/model/input-normalization changes, no capture or motion. Current live miss remains unresolved. Need new same-condition repeat/independent placement validation before considering deployment; do not claim fixed based on development sweep.

- IMPORTANT fresh upper-lip SMD01 trial120931/report120941_804840 misses advisory nomination despite user preparation as a clearly lifted defect. Final UNKNOWN is retained, NOT PASS, but absence of SMD01 POSITION? is a detection failure against this trial label. Presence0.99883, auxiliary confidence0.37611, mask4250.5px², PatchCore0.217639, raw offset[1.4574,-0.7665]mm, common correction[-0.0222,-0.7233]mm yields transverse-0.04316mm. Generic seating gate excludes confidence>=0.30 and score<0.25; SMD01 specific lip gate requires mask>=4400, so independent anomaly evidence is suppressed by outline conditions. Historical12-capture nomination agreement did not establish generalization. Preserve new scene outside normal training, no threshold/model edits. Native crop inspected, flash off and overview restored; no robot/conveyor motion. Need validate seating fusion beyond large-mask examples and assess nominal/common-bias geometry, not just lower mask threshold on this one image.

- Fresh SMD01 left/right normal-boundary controls completed, sources120408/120647 and reports120417_894943/120657_287426. User prepared each after explicit fully-seated/no-lip instructions; physical height not independently measured. Both have PRESENT confidence0.9979/0.9977 and no SMD01 nomination, with final UNKNOWN. Corrected offsets left[0.5522,0.8574]mm/right[1.2397,0.6423]mm remain nominal-scale advisory values, not certified wall clearance; no per-slot reference calibration. Native crops inspected, user-observation sidecars preserved, neither added to training. No threshold/model changes. Flash off, optical3.5x4000x3000, overview restored, no robot/conveyor motion. These new placements support no false nomination on two normal lateral boundaries but do not test new lip defects; existing VRM candidates are outside this SMD01 label.

- Extended current original-image GPU replay completed for six further documented Sept4 SMD01 captures: seating140856/141001, normal restoration142332/142427, mixed seating143229/143450. Labels are grounded in the Sept4 grouped log, not inferred from model output. Two normals have no SMD01 nomination; all four defects retain SEATING? (mixed pair additionally POSE?). `summarize_smd01_extended_replay.py` checks expected inputs/duplicates/completeness and preserves source SHA256, pose and surface evidence in `runtime/inspection/smd01_extended_replay_20260907/summary.json`; six complete/matched, script compile passes. Combined selected original-image replay set now has six normal captures without SMD01 nomination and six seating captures with nominations. These include repeated captures of the same physical placements and development/calibration examples, NOT12 independent trials or production accuracy. Final UNKNOWN throughout; no thresholds/model changes, fresh capture, or robot/conveyor motion. Existing same-placement repeatability is supported; new physical boundary placements and lighting conditions remain unqualified.

- Completed current GPU inference on all three archived explicitly normal SMD01 original inputs (Sept6_205808, Sept4_101935, Sept4_142508), outputs `runtime/inspection/smd01_normal_original_replay_20260907`. All three have no SMD01 advisory nomination; latest fresh restored normal114134 also has none. Together with two original-input defect replays, selected development sample outcome is four normals without SMD01 nomination and two defects nominated POSITION?. This is per-slot display regression, not board PASS or independent accuracy: uncalibrated raw pose/fusion remain UNKNOWN. No additional training or threshold adjustment needed to preserve these examples. No camera capture, robot/conveyor commands, or runtime mutation. Same-data replay work for this six-scene subset is complete; repeating it is not additional validation. Remaining qualification requires independent boundary/lighting cases and a calibrated geometry reference, not a nominal-centre threshold fitted to these examples.

- Current-model replay of original SMD01 seating-defect inputs140754/143333 (Sept4) completed on GPU, results `smd01_original_current_replay_20260907/20260907_115127_087657` and`115217_340508`. Both retain POSITION? display: first SEATING? (area4644, confidence0.324, PatchCore0.398569), second POSE?/SEATING? (transverse1.258675mm, area4711.5, confidence0.470, PatchCore0.154592). This confirms the two historical defects remain nominated by current independent seating gates; does not validate new directional thresholds. Latest restored-normal report114134 has no SMD01 nomination, but raw pose remains uncalibrated and final UNKNOWN. Earlier diagnostic replay used already-aligned input (`smd01_current_seating_replay_20260907/115015_332802`); excluded from original-input conclusions because of repeated registration. No deletion, camera capture, movement, or runtime change. Current hybrid unit suite66/66 passed. Stop treating an undisplayed auxiliary raw FAIL as a confirmed user-facing defect; retain independent seating evidence and explicit UNKNOWN rather than widening tolerance to force PASS.

- Signed-axis follow-up `audit_smd01_directional_limits.py`: six same explicitly labelled development reports, four normals/two seating defects. Corrected normal x0.8466..1.3828mm,y0.2583..0.8576mm; defects extend below/above signed-y normal envelope by1.1283/0.4010mm. Thus absolute transverse magnitude discarded useful direction (the earlier0.0123mm gap is not the signed-envelope gap). However leave-one-normal-out envelope expansion reaches0.3838mm in y, leaving only0.0173mm against the weaker defect's0.4010mm margin. Raw-frame y gaps1.0852/0.5816mm with normal expansion0.3092mm look better on this tiny set, but shared-bias removal cannot be disabled based on these mixed-date historical measurements. Horizontal defect margins0.0555/0.0832mm also fall below normal variability. No deployable tolerance or certified clearance follows. Saved `runtime/inspection/smd01_directional_limits_20260907.json`; three synthetic tests pass for signed sides, leave-one-out, input preservation, inside point, and insufficient data. No capture, motion, runtime criteria, calibration or model changes. Next calibration must evaluate signed-axis geometry together with independent seating evidence, not radial distance alone or a fit to these six labels.

- SMD01 centroid root-cause audit (`audit_smd01_centers.py`, output `runtime/inspection/smd01_center_comparison_20260907`): compared three explicitly normal historical scenes, two seating defects, and the fresh restored normal using saved segmentation evidence and native fixed-window bright contours at thresholds100/130/160. Directly inspected six-row overlay. Segmentation-vs-bright centroid differences0.32–2.50px; latest1.17–1.42px, despite low segmentation confidence0.114. This does not explain the latest15.45px horizontal nominal-reference displacement by centroid noise alone. Latest raw displacement[1.3426,-0.3074]mm, shared correction[-0.0402,-0.7606]mm gives[1.3828,0.4532]mm, radial1.4552mm against0.75mm; no per-slot reference calibration exists. Evidence implicates nominal-reference/tolerance suitability as an unresolved contributor, NOT a proven wall distance or segmentation-only error. Both defects remain spatially distinct in these selected images, but no calibrated separation/generalization is established. Offline run passed dimension checks and produced complete six-row JSON/image; no runtime changes, training, extra capture, or motion. Fusion contract reread; UNKNOWN retained. Do not just raise radial threshold or subtract current normal centre, which could hide real displacement.

- Fresh matched SMD01 empty/restored pair captured flash OFF: reports113623_037536 and114134_401329 (sources113613/114124). Restored inspection completed successfully, overview restored; no robot/conveyor motion commands sent. Empty nominated SMD01 MISSING?, restoration removed that nomination; VRM03 RIGHT? and VRM05 POSE? remain advisory in both scenes. Restored SMD01 still has an undisplayed auxiliary pose flag; absence of a displayed candidate is not PASS. Added offline `compare_smd01_empty_restored.py`, checked canonical dimensions and identical180x140 coordinates at1181,1014. Output `runtime/inspection/smd01_empty_restored_20260907/comparison.png` directly inspected, empty left/restored right, nearest-neighbor display only. Presence contrast is clear, but left inner-wall vs print/shadow boundary remains ambiguous. Do not promote wall-clearance geometry or train this pair to force a position pass. No model, runtime decision threshold, normalization, or camera configuration changed; final UNKNOWN retained.

- Multi-row left-wall attempt `audit_smd01_left_continuity.py`:12 height strips per archived empty crop, retains up to3 dark-band candidates per strip and counts near-vertical support. Leading candidates9/12 vs8/12,8/12 vs7/12, and8/12 vs8/12 remain competitive. Overlay directly inspected: some continuity belongs to diagonal print texture, not wall; repeated support cannot certify inner edge. No selection promoted. Synthetic known-band continuity/source-preservation/blank checks pass. `runtime/inspection/smd01_left_continuity_20260907` preserves alternatives. Existing-image methods exhausted sufficiently to request a current fixed-camera empty SMD01 capture (remove only SMD01), followed by matched normal restoration if usable. New capture is a reference-quality check, not a guaranteed fix. No runtime model, criteria, capture, or motion changed in this audit.

- Signed dark-band follow-up `audit_smd01_wall_pairs.py` pairs falling/rising gradients with a darker interior, retaining three alternatives. Same three empty sources, no part-local normalization. Interior-facing candidate spreads top2/bottom1/right3px improve repeatability, but LEFT27px is worse; direct overlay inspection shows competing texture/shadow boundaries. Thus neither a full calibrated socket polygon nor physical-clearance rule is available. Two synthetic checks pass (known band pair, blank rejection). Result `runtime/inspection/smd01_wall_pairs_20260907`; no live criteria/model/capture/motion changes. Repeated edges are not proven inner-wall edges, and the left edge must remain unresolved rather than substituted from assumed symmetry.

- Empty-only wall candidate experiment `audit_smd01_wall_consensus.py`: manually bounded search regions from empty-reference review, median absolute raw-gray gradients along straight sections, two spatially separated candidates retained per side. No assembled labels used to fit reference; same rectangle transferred without part-local alignment to the five labelled crops. Across three empty images, strongest-edge spreads left12/right2/top9/bottom5 native pixels; therefore this is NOT stable certified inner-wall geometry. Candidate overrun in normals reaches9px, defects13/23px, and separation is not adequate evidence given reference uncertainty. Comparison `runtime/inspection/smd01_wall_consensus_20260907/comparison.png` directly inspected. Synthetic four-edge locations, input preservation, blank rejection pass; missing-reference/edge guards added. No runtime criteria, heatmaps, model, physical clearance values, capture or motion changed. Do not deploy a threshold fitted to this five-image gap; inner-vs-outer edge ambiguity remains.

- Archived SMD01 empty reference search found three explicitly EMPTY presence records in component_presence_v1 (20260902_195651_061650/200538_659117/201241_794262). `audit_smd01_empty_reference.py` verifies all source SHA256 hashes and re-registers whole boards using current board-level registration; scores0.978631/0.978872/0.978446. Identical native crop origin1181,1014 and180x140 window matches outline audit. Original/CLAHE/edge comparison directly inspected at `runtime/inspection/smd01_empty_reference_audit_20260907/comparison.png`: empty recess perimeter visible, but inner/outer wall and diagonal print lines produce multiple competing edges. These are usable reference images, not validated wall coordinates or physical clearance. Presence label does not certify geometric edges. No per-part alignment, retraining, capture, movement, or runtime change. Next is repeat-consistent wall candidate extraction before overlay on labelled assembled scenes.

- SMD01 outline follow-up: `audit_smd01_outline.py` crops the same180x140 native-pixel window around nominal slot coordinates from five archived registered boards. Original/bright-contour/locally CLAHE Canny panels saved in `runtime/inspection/smd01_outline_audit_20260907/comparison.png`, directly inspected. Raw brightness thresholds100/130/160 each find a near-center body contour in all five scenes; contour extents vary by a few pixels with threshold. Bright body extraction is plausible on these examples but socket-wall edges compete with shadows/print texture. BLUE BOX IS NOMINAL COMPONENT ROI, NOT MEASURED SOCKET WALL; it must not define physical clearance. No calibrated height/seating/position decision can be inferred from these panels alone.3 direct synthetic checks pass (rectangle outline, source preservation, empty rejection). No runtime or model changes, new capture, or motion commands. Next prerequisite is verified empty-socket wall geometry/reference aligned to board landmarks, rather than fitting part pose to nominal boxes.

- Follow-up `audit_pose_normal_defect_separation.py` compares five explicitly labelled historical SMD01 scenes (three normal/two seating defects), not all25 slots. All five raw pose statuses FAIL, while existing advisory rules retain zero normal candidates and both known seating candidates. Normal radial displacement0.885–1.302mm overlaps defect1.176–1.472mm; raising a single radial tolerance cannot separate these observations. Transverse normal max0.857649 vs defect min0.869963 leaves only0.012314mm development separation, not a validated metrology margin; no threshold selected. Defect angles both0deg, so seating is not equivalent to angle error. Historical surface fields include zeros and different source dates; this is saved-evidence replay, not current-checkpoint inference. Output `runtime/inspection/pose_normal_defect_separation_20260907.json`; no runtime rule/model changes, capture, or motion. Current auxiliary mask-centroid distance must not be treated as calibrated physical clearance. Remaining calibration needs slot-edge/part-edge evidence and explicit normal-vs-seating labels, not automatic promotion of all raw FAILs.

- Audited latest105640 raw stages vs operator nominations. Seven auxiliary pose FAILs (HBM01/04, PM02, SMD01/03/04/05) do not meet the separate confidence/margin/type-specific overlay rules. They are not authoritative defects and must not be interpreted as PASS merely because no colored candidates appear. No physical tolerances or candidate thresholds changed.
- Added non-mutating `build_pose_display_audit`, additive JSON `pose_display_audit` with raw measurements/limits/confidence and undisplayed slot IDs, and an operator header stating the number of undisplayed auxiliary pose flags and that no candidate does not mean PASS. This exposes the discrepancy; it does NOT solve underlying measurement calibration or certify either threshold family. No heatmap suppression changes, raw FAIL rewriting, provider-authority promotion, or fusion change.
- Saved-evidence replay preserves latest zero candidates,105248 I1 direction plus VRM position candidates, historical SMD01 SEATING, and mixed SMD01 POSE/SEATING + SMD03 POSE + SMD05 MISSING. Full saved-image replay111100_767566 under `runtime/inspection/pose_display_audit_20260907` shows seven undisplayed flags, zero candidates, final UNKNOWN; image directly inspected. No new capture or motion commands.78 tests pass, including raw-input preservation and legacy renderer size compatibility (initial size regression corrected).
- Completion blockers remain: all providers unverified/advisory, GPU reference pin visibility, HBM dedicated pin provider excluded for false positives, PM/SMD independent orientation uncalibrated, VRM seating disabled/boundary uncertain, most surface thresholds unavailable. Next is validation/calibration of a unified physical pose decision, not changing UNKNOWN to PASS or assuming diagnostic raw FAIL is ground truth.

## 2026-09-07 Morning normal Inductor model update

- Post-promotion physical direction/recovery pair: capture102220/report102229_916188 flags only I2 DIR?/SURFACE? (I2 score0.487202, I1 normal-marker score0.188928). After requested normal restoration, capture102437/report102447_213116 has zero candidates, both marker checks direction-OK, I1 score0.149257 and I2 score0.198271. Both report images directly inspected; no fitting or threshold change from these samples. This demonstrates one morning small-rotation/recovery cycle, not certified defect coverage. Final UNKNOWN remains; flash-OFF capture/overview restoration only and both motion-command fields false.

- User confirmed normal placement and repositioned the inductors before capture100753/report100803_015945. Added ONLY I1/I2 crops from that new scene, not whole-board crops or the earlier mixed morning scenes. Existing36 originals/252 images plus2 originals and12 photometric variants gives38 originals/266 fit images. Training manifest records exact sources and SHA256. No geometry changes, runtime color correction, new defect labels, or other component training. Fusion contract re-read; original registered RGB and ADVISORY_ONLY remain.
- Added `train_inductor_morning_candidate.py` and `validate_inductor_morning_candidate.py`. New isolated memory bank reuses frozen feature weights only. Active Inductor root is now `runtime/inspection/patchcore/inductor_morning_candidate_20260907/models`; previous model preserved. Existing pass_max0.402317/fail_min0.439108 remain unchanged. Normal heatmap baseline recomputed with the new checkpoint on the existing22 development normal crops, not copied as final calibration. GPU/HBM/VRM/PM/SMD providers, geometry/direction rules, and heatmap gates unchanged.
- Development replay:22 normal crops, zero above fail_min (max0.403738, one may remain gray);79 defect crops all above fail_min, minimum0.444961. Weakest is held-out direction crop20260906_175326_427204_inductor_02: only0.005853 above the unchanged fail threshold, a limited margin, NOT certified robust recall. No new microcrack qualification; trainer uses a portion of old test data for validation.
- Three separate post-fit physical normal captures100946/101306/101504, none in training, produced full reports101143_605652/101316_478812/101513_985583 under `inductor_morning_candidate_validation_20260907`. First is candidate replay of separately captured100946, not an additional fourth capture. I1 scores0.188641/0.164912/0.267053; I2 scores0.132770/0.122806/0.220656. All three have zero advisory candidates and both marker checks direction-OK, but final UNKNOWN and unresolved VRM boundary uncertainty. Last two visualizations inspected directly. Near-time repeats of same physical parts are not independent production validation.
- Pre-fit morning094826 replay: I1 old0.461236 -> new0.360386, I2 known direction defect old0.875125 -> new0.834367. Earlier095642/100101 and three holdouts compared using both checkpoints, with SHA check excluding all training images (`inductor_morning_score_comparison_20260907/comparison.json`). Old I1 on three holdouts0.409545/0.342810/0.379400. No threshold relaxation. Final default-path full replay101843_009748 on saved094816 confirms exactly I2 DIR?/SURFACE?, I1 no candidate, and final UNKNOWN; image inspected. This replay is not a new physical capture.
- Promoted only the Inductor default after these checks;77 hybrid/marker/boundary tests passed after the default change, including GPU-root isolation. Capture operations used existing flash-OFF telephoto settings and restored overview; no robot/conveyor commands, stop-line changes, or camera-setting modifications. Model performance under future sunlight and different parts remains unqualified. Next useful physical test is a small known Inductor direction defect under the same morning light, followed by restoration, rather than more unchanged-normal fitting.

## 2026-09-07 Morning photometric correction audit

- Added offline-only `audit_inductor_photometric_correction.py`. Read the fusion contract; production learned inputs remain original registered RGB. No runtime normalization, geometry transform, model/threshold change, or new normal-label assignment. Reference is the median channel-wise p95 of 36 non-augmented training crops; diagnostic channel gains bounded to 0.9–1.1. This content-dependent white-surface proxy is not a calibrated illuminant estimator.
- Replayed 22 development normal and 79 development defect crops, plus six unlabelled morning crops from reports094826_340451/095642_786832/100101_684903, with the active checkpoint. Existing development counts remain 0/22 normal flags and79/79 defect flags, before/after gain correction at unchanged0.439108. These are development replays, not independent production qualification or microcrack validation.
- Morning I1 scores raw->corrected:0.461236->0.468469,0.414137->0.423566,0.395899->0.396065. Correction does NOT resolve the morning flag and was rejected for deployment. Result `runtime/inspection/inductor_color_gain_audit_20260907/comparison.json`. Direct checks passed for source-pixel preservation, unchanged dimensions/dtype, bounded gain, and identity at matching reference.
- Earlier morning-vs-evening crop measurements showed similar I1 mean grayscale (~78) and near-zero saturated fraction, so sunlight/overexposure alone is not established as root cause. Recent full inspection100101 has no advisory candidates and both marker checks direction-OK, but final UNKNOWN; prior morning094826 did flag I1. No claim of resolved instability. Morning source labels require explicit physical-normal confirmation before training; mixed/uncertain scenes must not enter normal fit wholesale.
- This correction audit used saved images only, sent no robot/conveyor commands, and changed no camera settings. Remaining work: verified morning normal acquisition with separate evaluation captures and retained known-defect regressions; exposure/color compensation alone is insufficient on these samples.

## 2026-09-06 Confirmed normal I1 and SMD1 correction

- Final default replay212420_294167 on saved211912 confirms only I2 DIR?/SURFACE? and the selected Inductor model; GPU remains strict_v4. This is a replay, not another fresh trial.
- User explicitly confirmed I1 and SMD1 in205818_570243 are within normal range; I2 remains CCW direction defect. Do not relabel the full mixed image normal. Fusion contract read; no local geometric normalization or authority changes.
- SMD01-only advisory transverse nomination limit0.84->0.90mm, based on confirmed-normal0.857649mm with small display headroom. Other SMD slots retain0.84; raw CAD pose status, measurements, independent angle/presence/seating evidence stay unchanged. Report metadata exposes slot-specific limit. This is not a certified physical tolerance expansion. audit_smd01_normal_margin.py replays five selected stored-evidence reports: three normals no candidates, two known lip defects retain SEATING? (one also POSE?). This deliberately does not erase the0.846–0.870mm historical seating defect: independent seating evidence still flags it. Fresh physical near-boundary defect validation remains limited. Regression covers normal boundary, larger displacement, unchanged raw FAIL, and existing SMD04 behavior.
- Separate Inductor candidate trained36 source normals/252 photometric variants including ONLY explicitly confirmed I1 from205808. Manifest retains source; same-image I2 not added. Training paths remain original registered RGB with no runtime normalization; no blur or spatial augmentation. Dataset development22 normal max0.402317,79 defect min0.475899; frozen advisory pass_max0.402317/fail_min0.439108. Trainer test partially used for validation; no independent manufacturing/microcrack qualification. New candidate under runtime/inspection/patchcore/inductor_confirmed_i1_candidate_20260906/models.
- Fresh211735/211823/211912 reports211745_078085/211833_441041/211921_969211 all have exactly I2 DIR?/SURFACE?, no I1/SMD1 candidates. I1 scores0.203754/0.324437/0.407506; third is GRAY ZONE (above pass_max, below fail_min), not a normal PASS. I2 scores0.720961/0.846924/0.803163. No fresh image enters training/calibration. Same-image previous-model comparison and validation.json under runtime/inspection/inductor_confirmed_i1_live_20260906 records three_fresh_trials_passed=true; this means candidate behavior matched expected slots, NOT final PASS. Third full report directly inspected. Previous model on third normal I1 gives0.534264, above its0.431645 advisory limit.
- Promoted this Inductor appearance root only after fresh checks; other model roots unchanged. No heatmap paint/hide rules changed.77 hybrid/marker/boundary tests passed. Physical S22 capture/overview pause-restore only, no robot/conveyor commands; camera parameters/stop lines unchanged. Overall UNKNOWN remains, including unresolved low-confidence providers. Limits: normal I1 still has a gray-zone observation, future placement/light/part variations and surface defects remain unqualified; do not describe all intermittent false positives as universally solved. Final default replay recorded below.

## 2026-09-06 Restored Inductor2 appearance repeatability

- Fresh CCW I2 trial205808/report205818_570243 detected I2 DIR?/SURFACE? score0.718328, but also I1 SURFACE?0.610222 and SMD1 POSITION? transverse0.858mm versus0.840 gate. User was instructed to change only I2: untouched-part flags therefore represent suspected false positives, not confirmed new defects. I1 orientation remains ambiguous. This new trial disproves general repeatability beyond the earlier clean three captures; do NOT describe the Inductor false-positive issue as fully resolved. Raw result and visualization retained; no threshold/model changes or motion commands. Final UNKNOWN.
- Post-promotion physical checks: fresh205248 normal board produced zero candidates (I1/I2 scores0.327477/0.298119). User then rotated ONLY I2 slightly clockwise; fresh205534/report205544_170369 produced one candidate slot I2 with DIR?/POSE?/SURFACE?, score0.819523, strict marker-axis error10.981deg and inner-edge error14.324deg (image-derived, not measured mechanical angle). I1 has no defect candidate but orientation BLACK_MARKER_DIRECTION_AMBIGUOUS/UNKNOWN, so do not call it a fully validated PASS. Both reports visually inspected. Final UNKNOWN; no training/threshold changes, no motor commands. This new physical direction trial is separate from saved regression replay.
- Final default replay205004_319296 on saved204738 capture confirmed the promoted Inductor root with zero candidates; GPU root unchanged.76 regression tests passed. This replay is not counted as another independent capture.
- Read inspection_fusion_contract before changes. User restored GPU/I2 normally; I2 surface-only false positive after normal restoration is the target, not an orientation-rule relaxation. Extended isolated training/validation scripts with explicit restored-I2 and repeated-normal source options. Normal202933 I2 is used for fit; separate203108 I1/I2 retained for development evaluation. No mixed-scene rotated I2 enters normal training.
- First restored-pair candidate (34 source normals with six photometric variants each) failed fresh203905/203954/204043 validation: second I2 score0.428742 above0.424118; first/third no candidates. validation.json records three_fresh_trials_passed=false; this model was NOT promoted. A premature commentary saying both first trials were clear was immediately corrected after reading second report. Preserve this failure, not just clean repeats.
- Next isolated restored-repeat candidate adds ONLY I2 from unchanged-normal203954 (report204004_286842); source recorded in manifest and excluded from subsequent fresh validation.35 source images/245 augmented training images. Pixelwise brightness/gamma/WB only; no spatial transformation or blur, no change to runtime original-RGB input. Model root runtime/inspection/patchcore/inductor_restored_repeat_candidate_20260906/models. Development22 normal max0.379776,79 defect min0.483514; advisory pass_max0.379776/fail_min0.431645 and normal heatmap baseline frozen before fresh trials. These scores are checkpoint-specific, not accuracy probabilities. Old test data partly used by trainer validation; not independent production metrics or microcrack qualification.
- New captures204602/204650/204738 (reports204611_720294/204659_911873/204748_504834) all zero total candidates. I1 scores0.268598/0.359682/0.372672; I2 scores0.271722/0.240347/0.233638. Same fresh crops with previous active model give I2 scores0.456642/0.362960/0.319974: first reproduces old false candidate. No new photos used for fit or threshold adjustment. validation.json under indcutor-restored experiment's actual folder runtime/inspection/inductor_restored_repeat_live_20260906 records three_fresh_trials_passed=true. Third full visualization directly inspected; no forced heatmap hiding/filling changes.
- Existing small-CW defect174052 replay with candidate under indcutor direction experiment's actual folder runtime/inspection/inductor_restored_repeat_direction_replay_20260906/20260906_204852_681098 retains I2 DIR?/SURFACE? (score0.510781, BLACK_MARKER_INNER_EDGE_ROTATION_WRONG). Other saved direction samples score0.750309/0.483514/1.0 above frozen threshold. These are saved regression tests, not newly placed physical defects.
- Promoted only Inductor appearance default after three fresh trials and saved direction replay; GPU/other model roots, position/direction/pin rules, camera settings and stop lines unchanged. All providers remain ADVISORY_ONLY and final UNKNOWN; zero candidates does NOT assert PASS. Older checkpoints preserved. Six actual flash-off3.5x captures across two candidates, overview restored, no robot/conveyor commands or interlock changes. Limits: same physical parts/current indoor conditions; future lighting, normal placement variation and surface cracks remain unqualified. Final default-entrypoint and test results recorded below.

## 2026-09-06 Inductor normal-appearance refresh and three fresh trials

- Subsequent normal-restoration check: user restored GPU and I2, leaving other parts untouched. Captures202933/203108 (reports202943_105443/203118_756503) both clear GPU/I2 direction candidates; I1 scores0.320069/0.232148, no I1 candidates. I2 initially SURFACE? score0.401108 just above frozen0.400774, second0.338922 with zero total candidates. Thus normal-restored I2 still has intermittent surface false-positive behavior; the earlier I1 improvement is NOT proof that both inductors are robust. No threshold/model changes or automatic training promotion from these captures. Final UNKNOWN, no motion commands; overview restored. First and second report images inspected. Keep this observed failure, not just the successful repeat, in future regression.
- Investigated recurrent user-confirmed normal I1 SURFACE? while I2 remains reversed. AF/AE-lock UI diagnostic showed the legacy focus tap on adjacent background; an explicit73/44-percent portrait-screen override correctly placed the lock on the board (screenshot inspected). I1 still scored0.494361 with board focus; focus-only did not resolve it. Diagnostic overrides remain opt-in, capture defaults unchanged; no claim of fixed ISO/WB across app restarts.
- Isolated photometric-only candidate trained32 normal crops plus six pixelwise gain/gamma/WB variants each (224 images). No blur, per-part shifting, rotation, recentering, or runtime color normalization. Normal-max0.625430 versus defect-min0.436125 overlaps; this model was NOT promoted. Next isolated candidate adds ONLY user-confirmed normal I1 from195041_935881 (capture195031); the entire source scene is excluded from evaluation, I2 never enters normal training.33 source crops/231 augmented images; frozen extractor weights only reused from trusted old checkpoint, memory bank fitted anew. Manifest/provenance and comparison retained under runtime/inspection/patchcore/inductor_current_normal_candidate_20260906. Adjacent-time same-part images are not independent production data.
- Development evaluation:20 normal crops max0.369263,79 controlled/direction-defect crops min0.432284. Frozen advisory pass_max0.369263/fail_min0.400774, normal visualization baseline computed from20 development-normal crops. This is a new model's scale, not a blind increase of the old threshold. Original test data partially participate in trainer validation; development figures are not held-out production metrics. No labeled microcrack qualification. Classification/orientation/position/pin paths and fail-safe UNKNOWN authority preserved.
- Fresh, excluded-from-training captures201823/201955/202105: I1 scores0.296994/0.251040/0.255220 and no I1 candidate in all3; I2 scores0.992951/1.000000/0.979062 and DIR? retained in all3, GPU DIR? also retained. Same fresh crops with previous checkpoint give I1 scores0.621349/0.476347/0.590392 (old false-positive range), isolating a model contribution rather than just camera improvement. Reports/validation.json under runtime/inspection/inductor_current_normal_live_20260906. First/third full visualization directly inspected. No forced-red fill or new heatmap hiding; existing fixed-baseline rendering retained.
- Promoted ONLY this Inductor appearance model as the default advisory provider. Explicitly decoupled GPU default from Inductor constant: GPU still pcb_components_strict_v4. Old checkpoints preserved for rollback. Added regression for model-default separation. Fixed live launcher's misleading hardcoded report paths for custom-output trials. Bash syntax checks and hybrid regression suite run in this work; final verification recorded below.
- Final default-entrypoint replay202328_160540 (latest202105 image, not an additional capture) confirms GPU model unchanged, new Inductor root selected, only GPU DIR? and I2 DIR?/SURFACE? candidates, I1 unflagged.76 regression tests passed; both modified shell launchers pass bash -n. Fresh-trial validation.json reports three_fresh_trials_passed=true with all motion-command fields false. This is a scoped advisory model promotion, not authoritative defect qualification.
- Limits: current-placement I1 repeatability improved, not a guarantee for daylight, other physical specimens, surface cracks, or all25-slot accuracy. VRM boundary uncertainty remains visible and is NOT PASS. All final fusion results remain UNKNOWN. Actual S22 still captures and overview pause/restore performed; NO robot/conveyor motion commands, no interlock changes. Runtime tensor inputs remain original registered RGB; weak models remain ADVISORY_ONLY.

## 2026-09-06 Board mounting-hole registration diagnostic

- User confirmed VRM1 genuinely moved and its position flag is correct;195725 observation sidecar records this, not an assumed VRM false positive. I1 remains user-confirmed normal.
- audit_board_hole_registration.py compares four fixed outer board holes against normal183328 in already globally aligned images184949/194324/195716. Matching51px templates within81px windows, NCC>=0.85 guard; visually inspected landmark overlay. Observed residuals0–1px, not a large global registration failure. Diagnostic whole-board homography leaves I1 anomalies: active1943240.569897->0.593320,1957160.493809->0.465885; candidate0.536870->0.547994 and0.485060->0.479572. No part-local pose correction deployed. Raw-camera landmark tracking not implemented by this experiment; residual optical/parallax effects remain possible.
- Native JPEG EXIF: normal183328 ISO160 versus194324/195716 ISO200; all1/60s,F2.4,focal7mm,zoom3.5; exposure mode0 and white balance0 indicate automatic modes. This confirms acquisition settings are not fully fixed, not that ISO alone causes the defect response. Existing color-only diagnostic also failed to restore normal score. Next controlled investigation: capture exposure/WB/focus stability, rather than another scalar-threshold increase.
- Diagnostic results under runtime/inspection/patchcore/board_hole_registration_audit_20260906/audit.json.12 crop inferences succeeded, both models unchanged. No new capture, normal training promotion, camera settings, thresholds or robot/conveyor commands. I1 false positive unresolved; candidate remains unpromoted.

## 2026-09-06 Frozen-setting three-capture repeatability failure

- Captured195031/195120/195209 with existing flash-off3.5x optical workflow and default active models into inductor_capture_repeat_20260906. User instructed not to move parts. All three distinct image hashes and25-slot reports confirmed, overview restored after each. I1 scores0.416295/0.463570/0.636743; all surface candidates despite intended unchanged normal I1. I2 direction and VRM1 position candidates persist in all three. GPU180 direction detected2/3; first WHITE_DOT_NOT_UNAMBIGUOUS. No claims that direction fix is fully robust or that global final UNKNOWN is PASS.
- summarize_inductor_repeat.py saved summary.json and directly inspected side-by-side I1 crops. White centroid224px input (118.84,127.71)->(119.75,128.27)->(121.72,132.48); white medianBGR233/240/237 ->229/235/232 ->227/234/231. These show input/registration variation, not independently measured physical displacement. Camera optics/exposure and ROI alignment contributions remain unseparated; cannot claim autofocus alone is responsible.
- Frozen thresholds/models; no training data promotion, preprocessing change, or robot/conveyor motion command. Capture protocol unchanged. Current normal input variation can exceed known defect scores, so raising a scalar appearance threshold is not a supported fix. Next diagnostic should compare native-image fixed-board landmarks and rectification stability before another model retraining cycle.

## 2026-09-06 Inductor capture drift counterfactual diagnosis

- Added offline diagnose_inductor_capture_drift.py; compared original PatchCore crops from normal183328, earlier184949 and current194324. Saved image grid and diagnosis.json in runtime/inspection/patchcore/inductor_capture_drift_20260906. Directly inspected original crops and grid. In224px input, current white-region centroid differs from normal by(+3.66,+4.15)px; white area10880->10544, medianBGR(230,235,233)->(226,233,230), Laplacian variance18.24->16.05. These are image statistics, not physical displacement/focus calibration. Whole-board registration scores remain high0.985/0.982/0.981; high global score alone does not establish local crop equivalence.
- Diagnostic-only experiments matched white-region gain and/or translated current crop toward old centroid. Active score current0.569897 -> color-only0.561952, shift-only0.440981, both0.443214; normal0.257917. Candidate current0.536870 -> color-only0.529295, shift-only0.540187, both0.536314; normal0.242460. Thus simple brightness matching does not explain/fix the response; translation affects active model but does not restore normal and does not help candidate. Residual shape/texture/view/capture differences remain; exact causal attribution unresolved. Do not claim camera autofocus or actual part movement proven.
- NO counterfactual preprocessing deployed: per-part translation would risk hiding real position defects. No threshold/model/normal-data/camera changes or hardware commands.12 saved-crop predictions completed successfully across two models. Diagnosis is not a corrected production inspection or independent performance evaluation. Candidate remains unpromoted; I1 false positive remains open.

## 2026-09-06 Candidate criteria frozen and fresh-scene validation failed

- Prepared isolated candidate decision_thresholds: pass_max0.297810, fail_min0.347635 (development midpoint), ADVISORY_ONLY.15 normal crops (old8 + recent7) now explicitly development calibration, no longer claimed independent holdout. Generated candidate-specific pixel/score calibration with existing calibrator. Main generic p99 fallback now runs only when fail_min absent, avoiding dual display rules. Active defaults unchanged;75 regression tests pass.
- Fresh flash-off3.5x capture194324,4000x3000; overview restored. Candidate override report194334_346601 in hybrid_inductor_candidate_validation: GPU direction and I2 direction detected, but I1 surface candidate score0.536870>0.347635 persists. VRM1 position candidate also present. Assumed unchanged physical setup from requested trial; no new operator confirmation of VRM1 pose. This trial FAILS the candidate no-false-positive objective; candidate NOT promoted and thresholds NOT raised after seeing it. Candidate final UNKNOWN.
- Same fresh source replayed with default active model in hybrid_inductor_active_comparison/194511_785095 for direct comparison; no hardware motion or additional capture. Saved reports preserve all evidence. No claim of certified crack performance, production PASS, or resolved I1 false positive. Candidate settings remain isolated development artifacts. No robot/conveyor commands or camera configuration changes.

## 2026-09-06 Isolated Inductor appearance candidate experiment

- Created train_inductor_appearance_candidate.py and isolated output runtime/inspection/patchcore/inductor_appearance_candidate_20260906. Training32 good crops = existing30 plus both explicitly confirmed normal182507 slots. Original8 test-good/70 controlled defects retained for trainer evaluation; separate recent7 normal and4 direction-defect crops never passed to trainer. Manifest includes source/destination/hash/split. No exact train/eval duplicates; checked original source-scene stems with no overlap. Same physical parts and temporally adjacent normal captures remain a dependence limitation.
- Initial training stopped because offline ImageNet cache was unavailable. Added optional backbone_checkpoint parameter to trainer (default behavior unchanged), loading ONLY model.feature_extractor weights with strict matching from active v1. Old memory bank, thresholds and fitted state are not loaded. New memory bank trained successfully without downloading weights. Existing deployed files/model selection untouched.
- Re-predicted identical89 evaluation crops with both checkpoints. Active normal_max0.402272, defect_min0.423793; candidate normal_max0.297810, defect_min0.397460, zero sampled defects below normal maximum. Problem I1 heldout184949 scored0.297810 in candidate; reversedI2 remains1.0. Scores are model-normalized, so gap magnitudes are not directly comparable as accuracy improvement. Training validation includes a subset of old test data; recent holdouts excluded from trainer but already used for diagnostic development, not a fresh production certification set. No certified surface-crack coverage.
- All75 hybrid regression tests passed. Candidate is NOT deployed; it has no promoted runtime thresholds/normal calibration yet. Need candidate-specific calibration and new frozen-setting verification before operational replacement. No camera capture/configuration or robot/conveyor motion commands. Active I1 display is therefore unchanged pending candidate deployment validation.

## 2026-09-06 Inductor appearance score audit

- Added reproducible audit_inductor_appearance.py; reran deployed v1 checkpoint on8 held-out good and70 controlled-defect crops, then incorporated8 explicitly selected recent normal-slot report scores and4 recent user-confirmed I2 rotation defects. Outputs under runtime/inspection/patchcore/inductor_appearance_audit_20260906/audit.json. Old-good max0.314046, recent-normal max0.402272; old-defect min0.499968, recent rotation min0.423793. Observed all-case gap0.021522; no sampled overlap, but this is a narrow empirical gap, not validated future separation.
- A hypothetical0.45 appearance threshold would suppress the known normal flag but miss one recent rotation appearance response. Independent direction checking still exists; the audit does NOT claim total fused miss. Dataset labels are controlled defects/rotations, not certified microcrack coverage. Same physical parts and related scenes limit independence. Recent normal score shift is observed; lighting/pose/model sensitivity causation not established.
- No display/decision threshold, model weights, training data, heatmap, authority or camera changes. I1 surface false candidate remains unresolved; no PASS/FAIL promotion. No new capture or robot/conveyor command. Script executed successfully with78 fresh predictions; remaining12 scores read from identified reports. Next candidate work should compare a separately versioned normal-appearance model/calibration using independent holdouts, not keep increasing the current threshold to fit one crop.

## 2026-09-06 GPU neighbour-dot exclusion and unresolved Inductor surface response

- Direction trial184949 has GPU/I2 at180deg, other parts requested unchanged. Original184959 report missed GPU: neighbouring HBM pin at crop x30.21 competed with true GPU dot atx381.59, margin0.03307<0.04. Inspected full GPU crop. GPU orientation now restricts dot centres to the physical fixed slot by excluding the known .22 context margin (.22/1.44 inset), not by rotating/translating the part. HBM logic and winner thresholds unchanged. True reversed-dot margin now0.090889; two saved normal GPU controls182507/183328 retain advisory PASS. A trial raw-brightness filter was rejected and removed because it shrank legitimate dots or retained the competing pin.
- Full replay185709_784818 shows GPU DIRECTION?, I2 DIRECTION? and I1 SURFACE?; visualization inspected.75 tests pass including synthetic neighbour exclusion and captured GPU controls. Final UNKNOWN, no authoritative promotion.
- I1 remains a false surface candidate under the user-reported unchanged normal placement: score0.402272 exceeds display gate0.370965. Added non-decision spatial diagnostics to PatchCore reports. I1 fixed-slot peak0.397702 equals whole-crop peak, with7.01% of slot pixels above normal pixel baseline0.296183; therefore merely removing crop padding cannot fix it. I2 reversed peak0.782894 and88.20% above baseline. No further threshold increase, spatial suppression, map alteration or training change was applied; the actual I1 false positive is UNRESOLVED. Need independent normal-variation/defect validation before calibrating appearance thresholds; cannot claim the generic surface detector is validated.
- No new capture, robot/conveyor motion or camera configuration changes during this work. Existing observation sidecar184959 preserves physical trial truth. Raw maps/scores and uncertain provider outputs remain available.

## 2026-09-06 Missing-slot display precedence

- Empty GPU184155 had MISSING? plus spurious DIR? from a background white feature. Display categories now prioritize MISSING? alone whenever a missing candidate exists, for all component types. Raw codes/details/stage results remain intact (including the GPU direction conflict); this fixes explanation presentation, not the underlying detector or confidence. Presence uncertainty still blocks authoritative PASS; fusion unchanged. No heatmap recoloring or evidence removal.
- Same-source full replay184529_640890 shows GPU/PM3/I2 MISSING? only; saved visualization directly inspected. All73 tests pass including raw-code immutability and non-missing direction/position display preservation. Final UNKNOWN. No fresh capture, camera configuration/training change or robot/conveyor motion. Further independent defect validation remains required.

## 2026-09-06 Inductor white-top contamination fix

- Controlled missing follow-ups183708 and184155 covered HBM3/VRM3/SMD1 then GPU/PM3/I2 respectively. Each report has the three requested missing slots and no other-slot candidates. GPU184155 additionally reports a spurious DIRECTION? (WHITE_DOT_AT_UPPER_LEFT) on an empty slot; this cause conflict remains unresolved, not a clean all-reasons validation. Saved user-observation sidecars; no training or threshold changes. Final UNKNOWN, overview restored, no robot/conveyor motion. Heatmap code inspected: colors represent clipped per-pixel PatchCore normal-baseline exceedance within candidate slots, not missing confidence or artificial uniform missing fill. Different empty-slot colors therefore do not contradict the presence classifier's missing candidate.

- Follow-up frozen-setting live repeatability check: three new flash-off S22 captures183151/183239/183328, full reports183201_489371/183249_740026/183337_961766. Each reports zero advisory candidates and final UNKNOWN; three distinct input hashes confirmed. User requested unchanged normal placement; no training promotion or threshold/model changes. Overview restored after each capture; no robot/conveyor motion command. This checks same-placement short-term repeatability only, not independent part/lighting coverage or validated PASS authority. Second/third report images directly inspected. Next physical check: controlled missing parts with explicit slot truth.

- User explicitly confirmed source182507 Inductor2 normal. Old CLAHE-only bright segmentation included dark base/rim: white-top radius59.179px, strict marker area2071px, principal-axis error22.600deg and edge residual52.217deg. Actual crop was inspected; the black marker is on the white top, not the base.
- Added raw-gray>=135 corroboration to the existing local CLAHE/saturation white-top mask before morphology. No angle tolerance relaxation, no per-slot exemption, no alignment change and no retraining. Corrected I2 radius45.808px, marker516px, axis error1.600deg and edge residual7.217deg; orientation check now advisory PASS. I1 also advisory PASS. Original RGB remains the learned-provider input.
- Saved-crop regression: I2 user-confirmed rotation cases172527 (CCW),174052 and175316 (CW) still FAIL in the advisory orientation provider. CW inner-edge residuals12.212/12.368deg exceed the unchanged10deg limit; CCW axis error19.665deg. Added optional local-image regression test; all72 tests passed with fixtures present.
- Full same-source replay182910_880790 displays zero candidates; directly inspected three-panel output. Final UNKNOWN remains because providers are unverified; this single corrected normal image is not an independent accuracy benchmark. New unseen normal/defect captures and lighting coverage remain necessary. Raw evidence preserved. No camera configuration change, new capture, robot/conveyor motion or training-data promotion during this fix.

## 2026-09-06 Inductor marginal surface display gray band

- User confirmed I1 normal in source175316; HBM3 POSITION and I2 DIRECTION correct. Archived physical truth alongside original175326 report; whole scene is not normal-training data.
- I1 score0.330201 barely exceeded normal_p99=0.309138. Changed generic Inductor surface advisory visibility to a provisional 1.20*p99 display gate (0.370965), shared across both slots. This is an engineering gray band selected after this observation, NOT an independently validated defect threshold or model improvement. Raw scores/maps, existing cause checks, provider authority and UNKNOWN fusion remain intact. No slot-specific disabling, retraining or normal-data contamination. Weak surface defects in this band may lose the generic highlight; further unseen validation is required.
- Same-image full GPU launcher replay180300_919063 now produces exactly HBM3 POSITION? and I2 DIRECTION?; inspected the saved three-panel visualization directly. I1 no longer has an erroneous generic surface candidate. Score-based regressions retain advisory visibility for .423793/.463599/.5961/.7128/.9662 and reject .330201; these are gate tests, not fresh independent model evaluation. All71 hybrid/boundary/marker tests passed.
- No camera configuration change, fresh capture, robot or conveyor command. Final remains UNKNOWN; absence of a highlight does not certify PASS. Output: runtime/inspection/hybrid_fixed_slot/20260906_180300_919063/hybrid_report.png.

## 2026-09-06 Inductor clockwise edge and PatchCore advisory visibility fix

- Added an Inductor-only normal-p99 exceedance advisory nomination when no other cause already nominates the slot. Requires finite score/baseline and ADVISORY_ONLY available provider; does not manufacture fail_min or change fusion authority. SMD suppression unchanged. Existing direction/position cause retains concise label; PatchCore still supplies its real heatmap. Baseline exceedance alone is generic SURFACE? evidence, not a claim of rotation/crack.
- Added Huber line estimate of the dark marker's inner/right edge using its middle20–80% vertical extent. Eight earlier control captures gave median edge references87.3deg forI1 and85.6deg forI2. These per-slot provisional references share existing10deg axis candidate tolerance. Sixteen control observations remain unflagged (edge residual<=2.70deg); prior172527 counter-clockwise example has17.30deg residual and current174052 clockwise example12.93deg. They use one mask, not independent sensors. Pose truth for earlier VRM-session controls remains assumed unchanged, not newly individually certified; no physical angular accuracy claim.
- Actual full launcher replay174052 in175032_101097 now displays exactly HBM3 POSITION? andInductor2 DIRECTION? with underlying PatchCore evidence; image directly inspected. Principal-axis-only estimate was2.90deg, but edge residual12.98deg triggers the direction advisory. Prior175? intermediate run displayed duplicate SURFACE? alongside direction; final code only adds generic anomaly when no specific cause exists. Model weights and normal data unchanged. Final board UNKNOWN remains required.
- All71 hybrid/marker/boundary tests pass, including unavailable/nonfinite anomaly-gate rejection, SMD isolation, and synthetic both-direction rotations. No new capture or robot/gripper/conveyor commands; only saved174052 replay. Independent new normal and clockwise validation remains necessary, and normal-p99 display can expose false anomalies under changed illumination.

## 2026-09-06 Clockwise Inductor miss diagnosis

- Follow-up captures173817 and174052 completed with overview restoration, no hardware motion. First retained HBM3/Inductor2 direction candidates; second flagged only HBM3 position. User confirmed HBM3 position and Inductor2 slight CLOCKWISE rotation as actual defects in174052. Saved physical truth separately; no normal training ingestion.
- Verified previously retrained Inductor PatchCore strict-v4 remains configured (30 training normals,8 normal holdouts,70 controlled defects; v1 latest checkpoint). Latest score0.463599 is above normal p99 baseline0.309138, but controlled fail_min is null. build_advisory_candidates requires fail_min for surface-only nomination, so the existing candidate-gated heatmap hides this anomaly evidence. OpenCV fine axis measured2.896deg, below10deg, and also failed to nominate the slot. This is not evidence that the old model disappeared or lost all response.
- Diagnosis only: no new threshold/authority/model change. Normal-percentile exceedance does not identify rotation or certify a defect. Prior suggestion about marker side alone was not established for this scene. Next correction should distinguish advisory anomaly visibility from authoritative decision thresholds while validating clockwise marker estimation.

## 2026-09-06 Inductor fine rotation integration and simple cause labels

- Captured172527 flash-off3.5x and restored overview. Initial report172537 flagged HBM3 only; user clarified HBM3 was not restored and Inductor2 was deliberately tilted and definitely unacceptable. Saved separate user_observation.json; this is not a normal training scene. Original broad marker check allowed27.8deg centroid direction error under50deg tolerance, and circular segmentation axis was deliberately unchecked.
- Added strict connected dark-marker measurement inside the existing0.78-radius white-top interior, using local CLAHE plus raw dark-pixel corroboration. Computes the elongated mark's principal axis rather than the circular top or black base. Exploratory wider0.88-radius region contaminated measurements and was rejected. Earlier broad dark-pixel PCA was unstable and removed. Keep gross-direction check for180deg reversal; add10deg fine-axis advisory limit with elongation>=3, otherwise UNKNOWN when coarse direction alone looks normal. The10deg setting is provisional development screening, not physical angular metrology or production authority.
- Saved audit_inductor_marker.py replay:16 earlier reference observations have strict axis error0.11–3.53deg with no new direction flags (VRM-session controls assumed unchanged, not independent freshly confirmed inductor normals). Known171520/Inductor1 gross reversal remains flagged; current172527/Inductor2 has19.50deg axis error and is now flagged; currentInductor1 remains unflagged. No model training or defect normalisation. Independent future validation still required.
- Wired simple operator categories MISSING/POSITION/DIRECTION/PINS/SURFACE with deduplication; detailed RIGHT/ROT/SEATING and provider measurements remain JSON-only. Korean category labels included in JSON. Rendered same172527 image through actual launcher with all25 PatchCore slots; final173505_934413 shows exactly HBM3 andInductor2 DIRECTION? and their heatmaps. Directly inspected image. Final board remains UNKNOWN under locked advisory fusion.
- All70 tests and compilation passed. Existing synthetic round-dot direction test now correctly expects UNKNOWN because a round dot cannot certify fine-axis orientation; added synthetic elongated-marker rotation and blank-marker tests. No new capture during the fix, no robot/gripper/conveyor commands, no training/label overwrite. Earlier capture/aborted display rerun retained as history; final successful replay is the reported result.

## 2026-09-06 Live hybrid capture and user-confirmed causes

- Captured fresh flash-off3.5x S22 still171520 (4000x3000, focal7mm), extracted ROI, restored managed overview and ran all25 hybrid slots. Report171529_879920 completed UNKNOWN with11 advisory slots; original/heatmap/overlay directly reviewed. No robot/conveyor commands.
- User confirmed reported issues except clarifying VRM3 as LEFT socket lip seating and VRM5 as RIGHT socket lip seating. Recorded user_observation.json alongside immutable machine report. VRM3 POSE? and VRM5 RIGHT?/DIR?/POSE? localize concern but do not correctly classify lip seating; VRM5 rotation is not separately established. Remaining nine reported slot causes confirmed by user. Unlisted slots are not automatically labelled normal; this single scene is not a general accuracy metric.
- No model/threshold change or training ingestion. This capture is excluded from normal training. Height/cause recognition remains unresolved; preserve machine UNKNOWN and separate human physical truth for future evaluation.

## 2026-09-06 VRM boundary advisory integrated into live hybrid entrypoint

- Added hybrid_inspection/vrm_boundary_advisory.py and wired main.py; existing run_s22_live_hybrid_inspection.sh -> run_hybrid_fixed_slot_inspection.sh now executes it by default when YOLO is enabled and registration passes. Uses the frozen last.pt hash98572682... and eight saved reference reports, with source report hashes emitted for provenance. Five fixed1.5x slot crops use original registered color, imgsz320/conf0.25; ambiguous multiple central masks abstain. No part recentering, common-motion removal or changes to existing model weights/thresholds.
- New vrm_boundary stage always emits UNKNOWN/ADVISORY_ONLY. RIGHT? and ROT? extend existing candidate labels and enable the existing candidate-gated PatchCore heatmap; the footer lists all five VRMs and UNCERTAIN/UNAVAILABLE explicitly. JSON includes Korean reason text. Within-range or missing-mask results never grant PASS or authoritative EMPTY. Existing presence/seating/PatchCore votes are preserved, not overridden.
- Initial integration exposed a renderer argument error, corrected with a render regression test. Actual launcher uses .venv_patchcore without ultralytics; resolved via bounded120s subprocess in existing .venv_obb, temporary inputs cleaned after completion. Model/ref failure returns unavailable, not silent success. Full actual-launcher replay132330 completed with25 PatchCore scores and visible VRM4 ROT? plus VRM1/2 RIGHT? (these older positions are compared to the new left-seat target, not retroactively relabelled). Final three-panel image directly inspected. Earlier failed/unavailable runs are retained as diagnostic artifacts, not successful validation.
- Actual-launcher normal160026 replay yields zero new boundary candidates; right155131 yields RIGHT? for all5. Those two checks skipped PatchCore deliberately; full rotation check included it. All67 hybrid/boundary tests passed, including rendering and fail-safe fusion. Results under runtime/inspection/hybrid_boundary_{normal,right,full}_check; no new capture, robot/gripper/conveyor command, or persistent process. Reference artifacts and YOLO environment are required on this PC. This is integrated advisory functionality, not certified1mm, subtle lip-seating detection or autonomous assembly acceptance. Final provenance-only addition syntax checked after runs.

## 2026-09-06 Rotation evidence development audit

- Added audit_vrm_rotation_evidence.py comparing min-area-rectangle axis and filled-polygon moment principal axis. Both use the SAME frozen segmentation mask, so this is estimator consistency, not independent sensing. Axis differences wrap modulo180; near-isotropic masks are unavailable (1.1 eigenvalue ratio is numerical axis-confidence screening, not assembly tolerance).
- Eight normal reference captures include initial131407 and return132543 as well as six left-seat captures; evaluated normal scenes are excluded entirely. Normal angular ranges pooled across slots provide a descriptive uncertainty margin without defect-driven factor fitting. Forty normal observations produce no rotation candidates. Deliberate132330/VRM4 produces a rotation candidate (axes -14.15/-18.05deg relative to vertical); normal return132543 and subtle access-concern141441 remain UNKNOWN. One deliberate rotation is insufficient for performance claims, and subtle-angle detection is not established.
- Saved rotation_evidence_audit.json with per-row bounds and margins. Four rotation tests cover modulo180, known synthetic rectangle angles, translation invariance and missing/square ambiguity; all13 rotation/placement/robustness tests and compilation pass. No runtime authority/model change, capture, label edits, robot/gripper/conveyor commands. Preserve separate right-shift evidence for141441; neither absence of rotation evidence nor within-envelope implies PASS. Independent validation and vertical seating inspection remain outstanding.

## 2026-09-06 Broader placement robustness and scope validation

- Added validate_vrm_envelope_robustness.py with report/source hash checks and15 exhaustive leave-two-normal-capture-out folds (four remaining reference captures each). Repeated fold totals:150 normal observations yield43 within-reference,107 UNKNOWN, zero right candidates;105 repeated right-control observations all produce right candidates. These reuse30 unique normal slot observations and7 right controls, not255 independent tests. No further margin optimization performed.
- Audited six earlier captures separately. Two complementary removal controls preserve5/5 present masks and0/5 empty false masks; this is segmentation evidence only, not fused presence. Deliberate132330/VRM4 rotation (-12.513deg relative to131407) remains UNKNOWN in the horizontal rule. User-concern141441/VRM4 produces a right candidate, but historical normal-return132543/VRM4 also does: the newer left-seat target must not retroactively redefine those historical labels. Rotation and vertical seating need their independent stages; horizontal evidence alone cannot provide assembly PASS.
- Added four regression tests for full-scene exclusion, retaining simultaneous shifts of all five parts, missing-reference rejection and duplicate-reference rejection. All nine envelope/robustness tests and compilation pass. Wrote placement_robustness_audit.json and placement_candidate_validation_decision.json explicitly forbidding promotion or1mm claims. No camera capture, training, deployed threshold/model change, historical relabeling, or robot/gripper/conveyor command. Saved-data audit is complete; independent future capture validation and normal acceptance coverage remain outstanding.

## 2026-09-06 Uncertainty-aware placement development replay

- Added optional --uncertainty-aware mode to the isolated envelope replay. A right-shift candidate now requires both center X and rightmost contour to exceed the reference maximum plus the largest observed normal feature range across all five slots. The entire evaluated normal capture is excluded from both its reference bounds and pooled margin. This is a heuristic proposed after the known false alarm, not metrological uncertainty, a physical tolerance, or independent validation. No factor sweep against defects was performed.
- Saved placement_uncertainty_replay.json:30 requested/confirmed left-seat observations yield11 within-reference and19 UNKNOWN, zero right-shift candidates. Previous false candidate155607/VRM5 becomes UNKNOWN, not PASS. All7 known right-shift observations remain candidates. Five unlabelled intermediate observations yield4 candidates and1 UNKNOWN, with no truth assigned. Normal acceptance remains incomplete; absence of a right candidate does not validate angle, height, presence, or1mm clearance.
- Five unit tests passed (missing evidence, inside-not-PASS, dual-feature requirement, uncertainty boundary abstention, nonfinite/negative margin rejection), and compilation passed. Old replay artifact preserved. No deployed inspection/model/threshold changes, capture, training, label rewrites, robot/gripper/conveyor commands. The candidate needs independent validation before runtime authority; other inspection stages remain required by the fusion contract.

## 2026-09-06 VRM5 repeat residual diagnosis

- Compared previously rendered155607 and160026 original/outline strips directly and added probe_vrm_repeat_residual.py using saved original RGB images, existing board registration and diagnostic grayscale phase correlation. Source hashes verified; no inference retraining or coordinate correction. The probe uses fixed body-interior and adjacent-image patches; adjacent patches are not calibrated fiducials.
- VRM5 center shifted-2.774px and right edge-2px between saved reports. Body texture phase shift was-2.679px horizontally, while adjacent-image shift was+0.155px. Other adjacent patches shifted+0.045 to+0.653px. This does not support attributing the entire discrepancy solely to a global shift or segmentation jitter. Texture correlation remains affected by repeated print patterns/shadows; physical movement versus projection is not established, and user-confirmed left seating is preserved.
- The leave-one-out extrema envelope has insufficient support to reject this known acceptable sample. No ad-hoc extra margin, common component-motion subtraction, or normal-to-defect relabeling applied. Saved repeat_residual_155607_160026.json and compiled the probe successfully. Runtime remains unchanged/UNKNOWN. No new capture or robot/gripper/conveyor command. A validated acceptance boundary requires more than the current sample extrema; the diagnostic does not certify1mm clearance or lip seating.

## 2026-09-06 Empirical placement envelope replay

- User clarified inside width equals opening width but precise measurement is unavailable. Requirement metadata now preserves that statement, leaves calibrated contact width unknown, and does not assume a narrower bottom. No further precision measurement requested. Empirical placement screening is separate from1mm certification.
- Added isolated replay_vrm_placement_envelopes.py: verified frozen weight and source hashes; compares board-frame center XY and rightmost outline against saved left-seat envelopes, leaving each tested left capture out. No component recentering, physical scale fitting, or normal outlier deletion. Right controls produced7/7 right-shift candidates; left controls produced11 within-envelope,18 UNKNOWN, and1 false right-shift candidate (155607/VRM5, explicitly confirmed left by user). Approximate-middle5/5 are right candidates but remain unlabelled, not scored as defects. This is development replay, not independent accuracy.
- The false candidate prevents deployment of this naive envelope. Within-envelope never means PASS; orientation and vertical seating are not validated by these features. Three unit tests and compilation passed. Saved placement_envelope_replay.json; existing model, fusion thresholds and training labels unchanged. No capture, robot, gripper or conveyor command. Next improvement must handle registration/contour variability without erasing real all-VRM shifts; no margin was fitted merely to hide the false candidate.

## 2026-09-06 Socket top-opening clarification

- User confirmed the reported socket measurement is at the top opening. Recorded this provenance and unknown seated contact width in the isolated access requirement. The stored1.5mm clearance/.25mm offset calculations are opening-plane arithmetic, not evidence of usable travel or1mm gripper-height clearance. Left-flush placement intent and requested1mm right-wall clearance remain unchanged.
- Updated the metric audit to label opening-derived values explicitly and write a separate clarified artifact, preserving the earlier report. Wall profile is a possible explanation for the travel mismatch, not a confirmed cause. JSON parsing, Python compilation and saved-data audit succeeded. Runtime remains disabled/UNKNOWN; no new capture, training, label changes, robot or conveyor commands. Seated/contact-height dimensions and projection uncertainty still need verification.

## 2026-09-06 VRM metric consistency audit

- Added isolated audit_vrm_metric_consistency.py and metric_consistency_audit.json. The configured 139mm board width and 1600px registered image imply a nominal 11.5108px/mm. User-reported 12.5mm slot minus 11mm body implies 1.5mm full travel (17.266px), whereas saved left153918/right155131 masks show 8.658–10.358px (nominal 0.752–0.900mm). Predicted body widths128–130px correspond to11.12–11.29mm; therefore no forced scale fitting or endpoint normalization was applied.
- This mismatch does not invalidate user measurements: actual contacting height, opening versus seated width, complete endpoint contact, projection and segmentation uncertainty remain unresolved. All clearance decisions remain UNKNOWN and runtime disabled. Verified generated JSON and Python compilation. No new capture, training, deployed threshold/model change, or robot/gripper/conveyor command was issued. Next physical clarification is where the 12.5mm slot width was measured.

## 2026-09-06 Intermediate placement comparison handoff

- User explicitly reported difficulty precisely centering161036. Retained approximate-middle scene as unlabelled metric/pose evidence, never exact0.75mm or normal/defect training truth. Frozen candidate detects all5; center dx from153918 left=[9.52,7.44,4.02,6.22,8.78]px, versus right endpoint spans[10.33,8.66,9.90,9.86,10.36]. No inference of actual millimeter clearance.
- Added build_vrm_trial_view.py producing self-contained placement_comparison.html with three previously reviewed original/contour strips and per-slot horizontal changes. Explicit UNKNOWN1mm column and limitations separate positional observations from clearance decisions. Checked consistent checkpoint hashes, three embedded images, and compilation; browser rendering not exercised. No new camera capture, model/runtime change, threshold fitting, or robot/gripper/conveyor commands. Training remains forbidden for the approximate middle scene.

## 2026-09-06 Frozen translation trial range summary

- Added summarize_vrm_translation_trials.py and generated translation_trial_summary.json from six requested left-seated scenes152933/153345/153918/154722/155607/160026 and right155131 plus targeted153632VRM4/154508VRM2. Verified every source hash and identical frozen checkpoint; missing masks fail summary rather than becoming zero. Included lower-alignment154722 and user-confirmed-left155607VRM5; no convenient outlier deletion or shared component displacement subtraction.
- Left centroid x spans forVRM1..5=[2.796,2.422,3.342,1.984,4.018]px. Minimum right x minus maximum left x=[9.933,8.404,9.337,9.457,6.721]px. Observed endpoint ranges do not overlap in this selected dataset, including the VRM5 residual. These are descriptive ranges, not calibrated statistical uncertainty or a fitted rejection cutoff.
- Left/right end-position detection is supported in these trials, but intermediate placement near the actual1mm requirement remains unmeasured. Sparse right examples, repeated parts and unknown measurement error preclude deployment or1mm PASS/FAIL. Script compilation and source/checkpoint integrity checks passed. No capture, training, runtime configuration or robot/gripper/conveyor command; all evidence remains UNKNOWN/ADVISORY_ONLY.

## 2026-09-06 VRM5 left-contact clarification and recapture

- User confirmed VRM5 had already been left against the slot in155607. Added clarification without replacing raw coordinates or marking that capture defective. Recaptured160026 with existing flash-off workflow; overview restored, frozen inference all5 detected, strips directly reviewed.
- VRM5 dx versus153918 reference now+0.863px (previous+3.638), change-2.774px from155607. Other slots vs153918 within0.290px. This undermines interpreting the earlier residual as demonstrated right-placement defect; it does not isolate camera/contour noise versus subtle physical changes. No automatic threshold expansion, per-part offset, retraining or label ingestion.
- Sidecar retains UNKNOWN; no physical1mm gap or gripper safety assertion. No robot/gripper/conveyor motion, active model or camera configuration change.

## 2026-09-06 All-slot horizontal translation pair

- User requested grouped testing; captured155131 all-right and155607 all-left with camera/board/PM requested unchanged. Frozen candidate detected all5 in both; directly reviewed both original/overlay strips. Right vs153918 left reference dx1..5=[10.328,8.658,9.895,9.863,10.358]px. No subtraction of common component displacement.
- Return vsright dx=[-10.512,-8.453,-9.337,-9.457,-6.721]px; vsleft reference=[-0.184,0.205,0.558,0.406,3.638]px. Slots1–4 return within0.558px horizontally;VRM5 remains3.638px right of earlier reference. Alignment0.984608 at return. Do not force-align VRM5 or declare physical defect/contact from this residual. Physical left-wall placement confirmation remains needed for5.
- Sidecars retain UNKNOWN/no training ingestion; one paired physical setup is not ten independent trials or calibrated1mm evidence. Existing camera overview restored; no robot/gripper/conveyor motion or model/threshold/runtime updates. This pair supports observable all-slot translation, not absolute gripper clearance.

## 2026-09-06 VRM2 translation and return observation

-153632/153918 VRM4 sequence was followed by VRM2-only right154508 and left-return154722. Frozen candidate detected all5 in both. Right scene versus153918:VRM2 center+9.287px/right edge+9px/angle0deg; other-slot horizontal variation<=1.166px, with VRM3 angle variation2.386deg retained as uncertainty rather than removed.
- Return154722:VRM2 center-11.454px from right, -2.168px versus earlier left. Other slots also vary up to2.784px versus left reference. Alignment score0.971261 versus0.983710 baseline; capture rectangularity0.892 versus preceding approximately0.907. Both pass existing gates, but tighter metric repeatability is not established. Directly viewed strips; return direction observed, residual not asserted physical position error. No ad hoc recentering or pose normalization.
- Sidecars preserve UNKNOWN/no training/no runtime promotion. Existing flash-off camera workflow restored overview; no robot/gripper/conveyor movement commands. Further unchanged recapture is preferable before drawing a tight clearance conclusion from this lower-alignment frame. No thresholds or weights changed.

## 2026-09-06 VRM4 controlled horizontal translation and return

- Fresh153632 requested only VRM4 right within socket without rotation/lip seating; compared with153345 left reference. Five masks detected. VRM4 dx+9.668px, rightmost+10px, angle-0.167deg; other slots abs dx<=0.399px. This separates visible horizontal displacement from major rotation in this pair, without measuring physical wall contact.
- Fresh153918 requested only VRM4 left return. Five masks detected. VRM4 dx-9.975px from right scene, -0.307px from left reference; rightmost-1px and angle+1.014deg versus left reference. Other slots abs dx<=0.395px. Directly reviewed both original/overlay strips and preserved UNKNOWN observation sidecars. One controlled round trip does not calibrate mm scale, full wall clearance, all-slot behavior or collision safety.
- Frozen model/cutoff unchanged; no normal training ingestion or active runtime changes. Existing flash-off capture restored overview both times. No robot/gripper/conveyor motion commands. Further cross-slot validation can use VRM2 horizontal movement with other parts unchanged; no additional VRM4 threshold tuning from these frames.

## 2026-09-06 Left-seated reference and repeat capture

- Requested all VRMs left-seated without rotation/lip seating and foam mockup removed; captured152933. Resumed its interrupted inference only after checking output absence, without duplicate capture. Frozen last candidate detected all5, confidences0.97087–0.97896. Predicted centers move left3.47–8.46px versus141441; this is candidate geometry, not measured1mm clearance. Reference retained without normal-training ingestion.
- Captured153345 as a requested unchanged repeat. All5 remain detected (0.9692–0.9797); relative to152933, centroid displacement0.247–0.865px, absolute angle change<=0.585deg, rightmost contour change-2..+1px. Directly reviewed both original/overlay strips. One repeat pair is not a calibrated uncertainty bound; physical immobility is requested, not instrumented.
- Flash-off existing capture workflow restored overview. Frozen model,0.25 cutoff, registration and runtime unchanged; no robot/gripper/conveyor motion. No physical gap or final seating PASS claim. Next discriminating scene can move only VRM4 toward the right wall without rotation/lip contact, leaving others unchanged, to isolate slot-relative position from angle.

## 2026-09-06 Gripper mockup and left-flush placement clarification

- User clarified the intended mechanism: PMs are installed before VRMs; limited VRM-to-PM1 spacing creates potential finger interference, so VRMs should be placed against the left side inside their own sockets. The1mm requirement remains VRM-body-to-right-socket-wall, NOT body-to-PM1. Corrected the assistant's conflation of these two gaps without changing the original1mm requirement.
- The3T foam board in151941 is a finger mockup in the VRM-PM1 corridor, not a1mm gauge or an object inserted into the socket clearance. It does not establish actual finger dimensions or collision-free motion. Added assembly_context to the isolated requirement record.
- Reported11mm part/12.5mm socket implies nominal unrotated left-flush right gap1.5mm; the earlier0.25mm left offset described only minimum1mm feasibility, not the user's desired placement. No robot target update, wall contact command, automatic verdict, retraining, calibration claim or historical label changes. JSON verified; no robot/gripper/conveyor/camera commands in this clarification.

## 2026-09-06 Selected wall profile diagnostic

- Implemented offline row-wise tracking near user-selected x159 on two registered empty crops, y55..195, fixed experimental x152..167 search band. Raw grayscale and local CLAHE gradients compared without changing part coordinates. Directly reviewed profile/comparison.jpg.
- Raw/CLAHE track disagreement reaches12px and10px; raw spans7px and12px, older track hits search boundary5times. Such jumps cannot justify a stable wall slope or a correction of the4–5px occupied-contour discrepancy. No automatic smoothing/offset selected to force agreement, and no physical gap or collision verdict emitted.
- Script compilation and two saved-image runs completed. Outputs under socket_wall_probe/profile remain UNKNOWN/runtime disabled. Existing imagery does not supply an adequate metric edge reference for the1mm condition. A known1mm spacer/gauge at the real entry wall would provide an independent calibration scene; availability must be confirmed before requesting placement. No new capture, model/threshold change, or robot/gripper/conveyor command.

## 2026-09-06 User identified VRM4 wall line

- User selected line2 of the topmost panel in socket_wall_probe/comparison.jpg. Resolved against the saved candidate order: crop x159, origin(3,305), registered board x162, displayed y360..490. Stored source hash and exact annotation in config/vrm04_socket_wall_annotation.json. This overrides neither candidate ranking nor historical imagery; it identifies one reference edge only, not all five slot walls.
- Sanity comparison with saved predicted global rightmost extents: initial131407 x159 gives3px separation, return132543 x167 and current141441 x166 extend5/4px past the transferred reference line. These are projection/contour/reference disagreements, NOT proof of real penetration, negative physical gap or user misidentification. The selected line also covers only part of the wall vertically, not a calibrated lower-corner profile. No mm conversion or physical clearance verdict is justified yet.
- Annotation remains USER_IDENTIFIED_REFERENCE_EDGE_NOT_CALIBRATED, runtime disabled. Full wall profile, metric scale/uncertainty and height/parallax transfer remain unresolved. JSON and candidate-index/coordinate mapping checks passed; no active thresholds, learned weights, previous labels, captures, robot/gripper/conveyor commands changed.

## 2026-09-06 Socket wall repeatability audit

- Compared previously extracted empty-slot edge candidates using an explicitly diagnostic3px pairing band. CLAHE retains two pairs:151/149 and163/163; raw profiles retain151/149 only. Added probe_vrm_wall_consensus.py and two tests verifying ambiguity preservation and unmatched candidates. Tests passed; report socket_wall_probe/consensus.json remains UNKNOWN.
- Repeatability narrows candidates but cannot identify which visible edge is the physical gripper-entry wall at the relevant height. The second CLAHE-only edge must not be accepted merely because it repeats exactly. No conversion to1mm clearance or assertion that a reference part intersects a real wall. Required physical annotation/edge identity remains unresolved. No runtime/model/calibration changes, capture, or robot/conveyor/gripper commands.

## 2026-09-06 User measured VRM geometry preparation

- User reported VRM11x14mm/socket12.5x15mm. Stored representative user dimensions separately in vrm_gripper_access_requirement.json; CAD12x15mm history and active socket geometry unchanged. Scope/measurement uncertainty and per-slot variation remain unknown. Entry-side requirement stays1mm for all five VRMs, runtime disabled.
- Added isolated vrm_access_geometry.py rectangle projection calculation: horizontal/vertical half-extents include absolute sine/cosine terms, returning signed minimum wall gaps. Centered gaps are0.75mm horizontal/0.5mm vertical; nominal center shift -0.25mm gives right1mm/left0.5mm when unrotated. Rotation reduces available corner clearance. Equality at1mm has no measurement margin, and inside-slot geometry is separate from right access requirement.
- Outputs remain UNKNOWN/ADVISORY_ONLY even when nominal geometry meets the requirement. Four tests cover centered/offset geometry, mirrored rotation, outside-slot negative gap and invalid numeric inputs. No image-to-mm calibration, actual gap assertion, label rewriting, runtime threshold or robot/conveyor/gripper/camera commands. Next prerequisite remains trustworthy slot-wall coordinates and uncertainty before using the nominal calculation on photographs.

## 2026-09-06 User specified VRM socket entry gap

- User explicitly specified minimum1mm between VRM and socket wall for all five VRM slots, motivated by possible gripper interference with Power Module1. Stored separate vrm_gripper_access_requirement.json; applies to entry side, not all four sides. Right-side context comes from the discussed upright view; per-slot physical entry geometry remains uncalibrated.
- Existing CAD records total1mm clearance, centered0.5mm per side. An axis-aligned part would require zero opposite-side gap to provide1mm on entry side, leaving no nominal tolerance margin. This is not proof of feasibility in the printed assembly. Actual dimensions, wall/entry height and measurement uncertainty remain unknown.
- No runtime wiring, authoritative PASS/FAIL, automatic repositioning or historical normal-label changes. Requirement remains USER_REQUIREMENT_PENDING_METROLOGY, ADVISORY_ONLY/UNKNOWN until measurable and feasible. Contract unchanged. JSON parse and scope/value checks passed; no camera, robot, gripper or conveyor command issued.

## 2026-09-06 Empty socket wall feasibility probe

- Added offline probe_vrm_socket_wall.py using two saved empty VRM4 scenes and two occupied comparison scenes. Board-only registration preserved; local grayscale CLAHE2.0/8x8 used only for edge analysis and corroborated by raw gradients. Search band is explicitly experimental, not a calibrated wall definition. Source hashes and candidate profiles saved in negative_v1/socket_wall_probe/report.json.
- Directly viewed original/edge overlays. Strongest raw and CLAHE vertical-gradient candidate is crop x151 in older empty image, x178 in newer one; alternative candidates near149–151 and163 persist, but inner socket edge versus outer lip/shadow identity is unresolved. Strongest-edge selection is therefore unsuitable for physical clearance. Occupied comparison is drawn with unverified lines only; no gap in mm or PASS/FAIL was generated.
- Blank image and synthetic vertical step sanity checks passed. These tests do not establish real wall accuracy. No trained provider preprocessing, active thresholds, model weights, capture settings, or runtime pipeline changed. No new capture or robot/gripper/conveyor command. Required next evidence is a trustworthy physical wall/finger-entry geometry reference; existing gradients alone cannot authorize a gripper-access decision.

## 2026-09-06 VRM4 right-side access evidence

- User clarified141441: slight rotation inside the slot, lower-right edge against the right side, gripper entry clearance ambiguous. Preserved as process-access concern, not a confirmed lip-seating defect or measured collision; observation sidecar updated without changing raw model output or assigning training labels.
- Existing unity_socket_clearance.json provides CAD VRM11x14mm/socket12x15mm, nominal1mm total clearance and0.5mm center allowance. These values are not a measured gripper finger entry requirement or a calibrated visible socket-wall boundary. No automatic process FAIL threshold was introduced.
- Added offline probe_vrm_right_extent.py: compare registered predicted rightmost and lower-third rightmost polygon coordinates, including cut-line intersections, without per-part alignment. Relative to132543 normal-return reference,141441 right extent is -1px (166vs167); initial131407 is159px. Thus the current predicted contour does not distinguish this user-described access concern from the return example. Do not invent a clearance threshold to separate them or label the earlier frame defective automatically.
- Output vrm04_right_extent_20260906.json explicitly leaves measured wall and required gripper clearance null, statusUNKNOWN/ADVISORY_ONLY. Three rectangle/translation/intersection/degeneracy tests passed. Actual socket-wall measurement and gripper entry geometry remain prerequisites for quantitative gap judgment. No active model/threshold changes, captures or robot/gripper/conveyor commands in this work group.

## 2026-09-06 Frozen VRM rotation and return pair

- With frozen negative_v1 last and cutoff0.25, captured132330 requested VRM4 rotation and132543 requested only VRM4 normal return. Both used existing flash-off3.5x capture and restored overview; directly reviewed original/overlay strips, all five masks present in both frames. No retraining or runtime changes.
- VRM4 mask long-axis delta versus131407 initial capture: rotated -12.5129deg, returned -2.449deg (return change +10.064deg). Non-target slots change only0.102–0.651deg between the paired captures. Relative to initial capture, other reseated parts differ up to5.497deg, so these observations must not become a universal3deg rejection threshold. There is no physical angle ground truth or calibrated seating verdict.
- VRM4 confidence changes0.982177 rotated to0.680146 returned; it remains detected but demonstrates that confidence does not measure defect severity or normality. Return result is boundary availability, not final PASS. Per-capture observation sidecars preserve UNKNOWN pose and forbid training ingestion. No robot/gripper/conveyor movement commands, camera configuration changes or model promotion.

## 2026-09-06 Frozen VRM complementary empty checks

- Completed two controlled fresh flash-off3.5x captures with the unchanged negative_v1 last checkpoint and0.25 cutoff:131700 requested VRM2/4 empty (three remaining bodies);132000 requested VRM1/3/5 empty (two remaining bodies). Directly viewed both original/overlay strips and corroborated the requested presence patterns. Alignment scores0.987570/0.985592. Present scores131700:VRM1=.971820,VRM3=.976320,VRM5=.978136;132000:VRM2=.972176,VRM4=.978667.
- Both scenes produce masks for each present body and none for empty sockets: five present-slot observations detected and five empty-slot observations without false candidates across two physical scenes. Together with131407 all-present capture, three fresh scenes contain ten present and five empty observations; these are repeated physical components, not15 independent trials or production accuracy. No seating/rotation verdict is inferred.
- Isolated fresh reports retain UNKNOWN truth; observation.json sidecars record requested setup and visually corroborated presence without modifying raw inference. No data ingestion, retraining, threshold adjustment or runtime promotion. Camera overview restored after each existing capture workflow; no robot/gripper/conveyor motion commands. Detailed records grouped here after the complementary checks; next validation concerns deliberately rotated part boundaries and separately evaluated pose evidence.

## 2026-09-06 Frozen VRM candidate first fresh capture

- After requesting all five VRMs normally seated and receiving user readiness, captured S22 131407 with existing flash-off3.5x workflow. Verified4000x3000,7mm focal/69mm equivalent; overview pause/resume completed. No camera settings implementation changed or conveyor motion issued.
- Added --fresh-image to boundary validation: reject source hashes already in dataset or historical development scenes, preserve UNKNOWN truth rather than infer normal seating, use isolated no-overwrite output. Ran frozen negative_v1 last SHA98572682b1df4aef452d7d5727c3cf6acf6abc7e6d954fdce7a214046d6f10cc with unchanged0.25 confidence and fixed crops. Alignment0.987709; all5central boundary candidates, confidences VRM1..5=0.973729/0.976316/0.975967/0.977904/0.978957.
- Directly viewed original/overlay strip. Five visible parts have boundary candidates; this is not proof of correct seating or five independent trials. Physical labels remain UNKNOWN in report; no final PASS, training ingestion, or active model update. Output segmentation/runs/vrm_fixed_boundary_negative_v1/fresh_s22_inspection_roi_20260906_131407_last. Next controlled scene requests VRM2/4 removal with other three unchanged to check empty discrimination. No robot/gripper/conveyor motion commands.

## 2026-09-06 VRM checkpoint regression diagnosis

- Investigated the two normal-part misses without captures or retraining. probe_vrm_negative_regression.py reconstructs source-hash-verified fixed crops, compares best/last on the same23scene115slot development subset at diagnostic floor0.001, and preserves original registration. Directly reviewed both missed-part overlays: best has plausible boundaries but confidence0.21560 (185803VRM3) and0.2407 (143632VRM5), below unchanged0.25 cutoff. Last scores about0.7990/0.8930. No polygon truth is available for these scenes; visual plausibility is not boundary accuracy.
- Added explicit --checkpoint best/last options to saved-scene validation and adaptation-fit scripts; defaults unchanged and outputs separated. Repeated actual inference at0.25 with last:92/92 known-present central candidates,0/6 known-empty central candidates,17unknown unscored. This confirms the diagnostic result without relying on low-floor post-filtering. Normal-only automatic best selection did not choose the checkpoint with better observed development coverage; this is not a claim that last is universally better.
- Last training-fit checks: three reviewed rotation/translation masks IoU0.96901/0.96715/0.97006; all five training negatives yield zero candidates. Directly viewed training-fit comparison. These fit examples are not independent evaluation. Candidate last SHA-256=98572682b1df4aef452d7d5727c3cf6acf6abc7e6d954fdce7a214046d6f10cc.
- Retained last only as RETAIN_FOR_FRESH_VALIDATION_NOT_DEPLOYED, ADVISORY_ONLY in last_review_decision.json. Original best NOT_PROMOTED record preserved. Selection used previously reviewed development failures, so a fresh frozen-checkpoint trial is required; micro-lip/position judgment and full-board fusion are not validated by presence counts. No threshold change or runtime link update. Active six-class SHA remains2f50e85b98286c27579cd79102b8b4db24527b9e00ddc4d926a137cbbdf8b8a7. Six pytest tests and compilation passed. No camera, robot, gripper, or conveyor commands.

## 2026-09-05 VRM negative crop training and regression

- Prepared five original fixed empty-slot crops from 141311 (VRM2/4) and already-adapted 142337 (VRM1/3/5). Direct visual review found empty sockets and no discernible VRM bodies in these crops; existing user-confirmed scene labels supply presence truth. Review and SHA provenance are in segmentation/vrm_negative_review_v1. No pseudo-labels or fabricated empty images.
- Built dataset v4: 108 train crops including five explicit empty-label negatives; 10 val/10 test unchanged byte-for-byte. Whole 141311 scene newly excluded from development evaluation (142337 already excluded), leaving 23 scenes. Source hash partitions, exclusions and empty-label counts passed checks. These are supervised segmentation negatives, never normal PatchCore data. Normal val/test remain reused normal-only regression data.
- Trained isolated vrm_fixed_boundary_negative_v1 from adapted best, CUDA, 60 epochs/115.446 seconds, 320 px, batch8, patience20, unchanged confidence cutoff0.25. Best SHA-256 c308e196d335163d6b33ec5b5e0f2a828761910a3a5e59330bfb0645a959b27b. Normal test mask mAP50-95=0.975. Active six-class model hash unchanged.
- Same retained23scene/115slot comparison: original/adapted candidates each92/92 known-present central masks, new90/92. All three have0/6 empty central masks on this exact subset;17unknown slots unscored. New misses are physically normal VRM3 in185803 and VRM5 in143632. Directly viewed both complete crop strips; missing masks are visible regressions. These are mask-availability counts, not seating verdict accuracy.
- Training-fit-only: all five negative crops yield zero candidates, and reviewed VRM4/VRM1/VRM2 polygons now yield IoU0.96763/0.96563/0.96862 at unchanged cutoff. Directly viewed comparison. This improves fit on the adapted rotation and empty scenes but does not establish held-out improvement: the formerly false-positive141311 scene is now training and excluded.
- Decision NOT_PROMOTED in candidate review_decision.json. Existing runtime untouched; do not trade new normal-part misses for nicer training examples or lower thresholds after inspecting failures. Six pytest geometry/validation tests pass; builder/preparation compile and data-integrity checks pass. An initial unittest discovery ran zero tests and was replaced with the correct pytest run. No new capture or robot/gripper/conveyor motion. Next work remains robust independent presence plus boundary confidence/coverage, not production deployment of this candidate.

## 2026-09-05 VRM confidence failure diagnosis

- Added and ran offline probe_vrm_checkpoint_failure.py against adapted best and last checkpoints on the three training-fit examples, verifying crop hashes. Diagnostic prediction floor 0.001 exposes suppressed candidates only; deployed settings and the evaluation cutoff 0.25 are unchanged.
- VRM4 is not geometrically unlearned: best checkpoint's top candidate has mask IoU 0.95726 against the approximate reviewed training mask, but confidence 0.14674, below 0.25. Last checkpoint remains weak (top confidence 0.11230, IoU 0.96333), so simply replacing best with last does not resolve the miss. This corrects the interpretation of the earlier zero-IoU report: no mask survived its cutoff, rather than no internal boundary response.
- The previously observed empty VRM4 false candidate scores 0.32403. Therefore no single confidence cutoff can both retain this 0.14674 true training example and reject that higher-scoring empty example. Lowering confidence alone is not a solution. Dataset audit: 103 training crops, zero empty-label crops; absent-slot appearance was not explicitly supplied as negative boundary training. This is a data-coverage limitation, not proof that additional negatives alone will solve it.
- Result checkpoint_failure_probe.json is diagnostic/training-fit only, not independent validation. Script compilation and six CUDA predictions completed. No candidate promotion, threshold change, new capture, or robot/conveyor/gripper command. Next improvement requires explicit negative training examples with entire-source-scene exclusion from evaluation, while keeping independent presence evidence and the fixed-slot authority contract.

## 2026-09-05 VRM boundary adaptation training review

- Built fixed-crop dataset v3 from v2 with three explicitly reviewed adaptation masks: 103 train, 10 validation, 10 test crops. Source hashes and scene splits were checked; validation/test bytes are unchanged. All three adaptation scenes are excluded from subsequent scene evaluation. Defective poses remain defective and are not normal PatchCore training data.
- Trained isolated vrm_fixed_boundary_adapted_v1 from the previous boundary candidate on CUDA, 320 px, batch 8, up to 60 epochs, patience 15; stopped at 52 epochs (96.36 seconds). Best weights SHA-256: 0b3f3f4822bdd370dcde04493547181ee118cdd1323b3e70ae00100bb29469de. Normal test mask mAP50-95=0.97389; this reused normal-only test does not establish defect accuracy.
- On the same retained 24 development scenes (120 slots), both old and adapted candidates returned central masks for 95/95 known-present slots. Empty-slot false candidates regressed from 0/8 to 1/8: vrm_04 in 20260905_vrm02_04_empty_a, confidence 0.324. Seventeen unknown slots are not scored. These are central-mask availability counts, not calibrated presence or seating decisions; these previously inspected scenes are not a blind test.
- Training-fit-only IoU on the three reviewed masks: VRM4 rotation remains 0; VRM1 improves 0 to 0.956; VRM2 improves 0.888 to 0.975. Directly viewed the original/old/adapted comparison and empty-slot false candidate. Improvements on training images are not independent validation. Six existing geometry/validation tests and Python compilation passed; dataset integrity checks passed.
- Decision: NOT_PROMOTED. The rotation miss remains and empty-slot behavior regressed. No threshold relaxation or active model replacement. Outputs and provenance remain under segmentation/runs/vrm_fixed_boundary_adapted_v1. Active six-class weights unchanged. No camera capture, robot, gripper, or conveyor command was issued. Reliable seating/position judgment remains unresolved; the fixed-slot hybrid authority contract is unchanged.

## 2026-09-05 VRM boundary adaptation annotations

- Selected3 development scenes for supervised boundary adaptation:142337VRM4 missed rotation,144513VRM1 missed rotation/lip,160027VRM2 overextended mask. Entire3scene IDs reserved for adaptation; other24scene IDs retained for development validation, not claimed blind because already inspected. Historical evaluation reports unchanged. No frame from these3scenes may count as independent evaluation of a later adapted candidate.
- prepare_vrm_boundary_adaptation.py reconstructs identical fixed189x241crops, checks registration/source hashes, and saves crop provenance and partition.json. Local SAM2.1-t box-prompt drafts generated on GPU for annotation assistance only. Direct visual review rejected all3drafts for including socket/shadow. They remain draft_labels, never accepted training labels.
- Manually specified body polygons in original crop pixels, rendered original/overlay, and visually reviewed all3. Exported reviewed_labels and explicit EXPERIMENTAL_BOUNDARY_REVIEWED reviews using export_reviewed_vrm_adaptation.py (crop SHA,scene disjointness,polygon convexity/area verified). Annotator=assistant; edges are approximate on blurred images, not metrology ground truth. These masks are eligible only for experimental supervised boundary fitting, never normal PatchCore training; original physical poseFAIL retained. No generic COMPLETE status, no automatic dataset ingestion.
- Artifacts: segmentation/vrm_boundary_adaptation_v1/{partition.json,manual_polygon_drafts.json,manual_preview.jpg,reviewed_labels,reviews}. Generic training_allowed remainsfalse; explicit supervised_boundary_training_allowed is recorded separately. No training yet, no active model changes, camera captures or robot/conveyor commands. Next step is an explicit adaptation dataset builder honoring these scene exclusions and review type.

## 2026-09-05 VRM boundary saved-scene validation

- Ran validate_vrm_boundary_scenes.py on27 archived scenes/135fixed slots using candidate b7cbf9a6e7cb47a2f1153ba93a0e99da47e8fc301c8a1fe8f296559d03d779b5. CUDA0,320px,conf.25,original-color fixed1.5x integer crops identical to training. Verified available source hashes, checked no source overlaps boundary train/val/test images, and applied board alignment quality gates. No per-part pose normalization.
- Ground-truth presence available for118slots:107PRESENT,11EMPTY;17unknown excluded. Central mask candidates in105/107present,0/11empty. Central region20–80% separates neighboring fragments for descriptive counting only; all masks preserved in reports. Not a calibrated presence decision or deployment accuracy estimate.
- Misses: vrm_04 at20260905_vrm04_small_rotation_defect_a and vrm_01 at20260905_vrm01_rotation_lip_144513. Both truly present/poseFAIL, no central detection at unchangedconf.25. Inspected these images, empty scene,144017rotation,150517rotation,160027translation and184100subtle lip directly. Some masks overextend actual edges; notably160027VRM2 has relative center~[.226,-.145]px and angle0 despite physical FAIL, so detection cannot establish correct seating.
- Saved-mask angle deltas versus fixed143632reference include VRM5 at144017~-10.204deg,VRM3 at150517~-5.886deg. No polygon ground truth in these development scenes: these are estimated angles, not measured angular accuracy. Subtle lip184100VRM5 angle0 with nonzero center shift; cannot infer height from long-axis angle. Do not lower thresholds or auto-PASS missing masks.
- Artifacts: segmentation/runs/vrm_fixed_boundary_v1/saved_scene_validation/report.json and27scene JPEGs. Three tests pass(primary centroid,neighbor fragment,degenerate polygon). Candidate remains ADVISORY_ONLY, not installed; active segmentation SHA remains2f50e85b98286c27579cd79102b8b4db24527b9e00ddc4d926a137cbbdf8b8a7. GPU process completed; no capture, robot or conveyor commands.
- Next: review boundary annotations on existing missed-rotation/overextended-mask scenes while retaining separate untouched evaluation scenes. Existing presence/seating and appearance paths remain necessary; this normal-only boundary candidate cannot replace them. No additional photography required to start that work.

## 2026-09-05 VRM fixed-crop boundary GPU candidate

- Logging policy: user requested a single detailed record, English acceptable. AGENTS.md now directs grouped details here and links only from Vision_AI_작업기록.md; historical entries preserved.
- Trained isolated generic YOLO26n-seg initialization on vrm_fixed_boundary_dataset_v2 using RTX5070Ti Laptop, CUDA0,320px,batch8,mask_ratio1,workers2. Maximum80epochs,patience20; stopped at51epochs (~94s in results.csv). No existing S22 checkpoint fine-tuning or active link replacement. Normal scene IDs split5train/1val/1test (100/10/10 crops). Supervised joint image/polygon augmentation only, not per-component inference alignment.
- Candidate: segmentation/runs/vrm_fixed_boundary_v1/weights/best.pt; SHA256 b7cbf9a6e7cb47a2f1153ba93a0e99da47e8fc301c8a1fe8f296559d03d779b5. Dataset manifest SHA847c4262a83f2f00bd3cae24df7d119cebad4f6b00252a5ef203222062a413ae. Provenance stored next to run. Existing active segmentation hash remained2f50e85b98286c27579cd79102b8b4db24527b9e00ddc4d926a137cbbdf8b8a7.
- Held-out normal test10crops from2photos/1scene: mask mAP50=.995,mAP50-95=.980,recall1.0. Fixed conf.25 primary-mask evaluation:meanIoU.964533,minIoU.934882; centroid error mean1.178px,max1.612px in original fixed crop. primary_test/comparison.jpg inspected directly; green reviewed polygon vs orange prediction. Evaluation GT matching is not deployment selection.
- Validation contains14instances including neighboring fragments, versus10primary test instances; do not equate aggregate recall with primary-boundary recall. No empty/rotated/lip-defect accuracy established, no calibrated socket/robot clearance, and recurring physical components limit independence. Normal test does not select epochs or thresholds. Candidate remains ADVISORY_ONLY, runtime disabled.
- New scripts train_vrm_fixed_boundary.py and evaluate_vrm_boundary_primary.py completed successfully. No camera capture, robot or conveyor command. GPU jobs finished; no live inference launched. Next appropriate validation is saved empty/rotated/displaced slots with independent presence gating, before integration.

## 2026-09-05 grouped confirmed normal and post-bump capture

- Prepared fixed-slot VRM boundary datasetv2 from reviewed24S22 images/7scene IDs:100train/10val/10test crops, source-image counts20/2/2, disjoint scene IDs5/1/1. Global registration only, inverse ECC annotation mapping, original color and fixed1.5x crops. Source/label hashes and transforms archived; duplicate source rejection.8 crops contain neighboring VRM fragments: clipped reviewed polygons retained,total128instances for120primary slots. v1 marked DO_NOT_TRAIN.3 tests pass(mapping/splits/clipping),v2 preview inspected. No training or runtime/camera/motion changes. Normal-only supervision does not validate empty/defects; physical identities may recur across scenes.

- Joint rectangle hypothesis experiment(up to4 lines/edge, competition and raw/CLAHE consistency) replays45 slots with source SHA checks:10 available vs18 prior, not an accuracy gain, not deployed.11 related synthetic tests pass. Existing S22 reviewed segmentation inventory:24 images/7scenes/120VRM polygons, all normal metadata; inspected15 polygons from3scenes. Reusable boundary supervision candidates exist but this collection lacks reviewed empty/rotated masks. No label edits, training, camera/motor commands. Outputs vrm_joint_rectangle_20260905.json and vrm_boundary_label_inventory. Any future boundary learning remains auxiliary to fixed-slot independent presence/appearance fusion.

- Added four-edge pose evidence with intersection/angle consistency, crossing and raw/CLAHE corner disagreement rejection. Fit checks3deg/4px are not assembly tolerances.18/45 saved-slot candidates available,27 withheld; fixed143632 reference available onlyVRM4, so other relative poses withheld.144513VRM1 raw-angle visual improvement fails full geometry consistency, not detection success.5 synthetic tests pass. Output vrm_line_pose_evidence_20260905.json; no runtime/model thresholds, capture or motion changes. Not fit for production coordinate supply yet.

- Added offline robust multi-peak line consensus(9 bands,up to3 peaks) with competing-line/raw-CLAHE disagreement evidence.9 saved frames×5slots, both montages inspected.144513 VRM1 raw edge slope magnitudes4.76–6.77deg versus prior outline1.21deg; visually follows tilted edges.144017 VRM5 8.67–10.84deg and150517 VRM3 4.51–6.07deg still include ambiguity. Axis slope signs differ; not calibrated part angle.150807 position defect remains near0–2.39deg, cannot solve by angle alone. All UNKNOWN/no runtime adoption.3 synthetic tests pass(outliers, competing lines,blank/input preservation). Artifacts vrm_robust_edges_190202 and vrm_robust_edges_pose_regression. No training/capture/motion.

- Multi-band edge probe added,4 saved frames×5 slots; seven scan bands/raw vs local CLAHE. Montage inspected. VRM2 band spread14px at185803 versus3px at190202,raw/CLAHE median gap1→0px; other cases reach63px spread. Agreement cannot certify component rather than socket edge, height or clearance. Diagnostic only, no runtime adoption. Synthetic rectangle/input-preservation and blank-strength tests added. Artifacts vrm_boundary_consensus_190202; no camera/motor commands.

- Added cause-track archived replay join keyed by scene/slot, validating current labels and available hashes. Geometry:9/77 normal warnings;4/5 explicit rotation-position defects detected;4/7 translation/lip setups;0/1 POSITION_SEATING_ERROR;0/2 unspecified. Appearance warns15/15 on this older subset but cannot determine cause, and excludes later normal false warnings/historicalVRM5 miss. Neither appearance score nor outline angle proves seating height/clearance. Saved vrm_failure_tracks_20260905.json; no runtime changes, capture or motion.

- Added saved-score separability audit, excluding train split and checking model/image hashes for merged fresh reports. Available labels:86 flat,19 defect; existing0.5 yields2 seating false warnings(VRM2 with separate clearance concerns),1 historicalVRM5 miss0.262353. Global normal max0.880559 exceeds defect min0.262353: no single cutoff separates these seating labels. Per-slot sample separation is not generalization; no threshold selected or deployed. Output vrm_score_separation_20260905.json. No training/capture/motion commands.

- Saved-image diagnostic versus185803: VRM2 at184100 dx0,dy0.5px;190202 dx-2,dy5.5px,match0.657,search angle0deg. Reviewed montage in vrm_motion_before_after_bump_190202. Horizontal direction agrees with user observation, but vertical change also exists; cannot attribute score drop solely to leftward shift. Texture displacement is not measured socket/gripper clearance. No runtime/model/threshold changes or motion commands.

- Follow-up: user observed VRM2 shifted slightly left in190202. For184100/185803 preserve flat seating truth but record separate requested POSITION_ERROR disposition for possible PM/gripper interference. process_position_review stays ADVISORY_ONLY/UNKNOWN; clearance unmeasured, collision unverified, training excluded. Existing seating false-warning metrics are not process-clearance validation. Metadata only; no capture, training, runtime threshold changes or robot/conveyor commands.

- User confirms185803 VRM3/5 normal restoration,VRM2 unchanged normal against right wall. Label only2/3/5 PASS. Frozen scores.880559/.136908/.036510: VRM2 false warning retained.
- User-reported slight bump followed by requested190202 flashOFF capture,4000x3000/69mm,overview restored. Same frozen model gives five no warnings; VRM2 drops to.008598. Alignment.979752. Compared raw slot crops. Post-bump physical labels unconfirmed, so no whole-board PASS or retrospective defect inference for pre-bump normal.
- Reserved manifest stores both sources/hashes with empty labels for190202. Artifacts vrm_recheck_190202 and vrm_recheck_crops_190202. No training, threshold/active model changes or robot/conveyor commands. Related captures and ground-truth confirmation recorded together; normal-position sensitivity remains unresolved.

## 2026-09-05 grouped invariant-board and component-surface motion audit

- Forward/backward LK on component-excluded board: p90 displacement5.78/5.09px before alignment,1.44/1.48px after;246 points each, median approximately-0.3px X/-0.1px Y. Whole-board9px misalignment is not supported.
- Separate interior LK corroborates VRM2 dx9.27px and VRM3 dx9.21--9.54/dy3.62--3.67px apparent surface changes. Initial global feature subset had zero nearby points; local-mask feature extraction instead finds17/16 VRM2 fixed-board points (median dx-0.592/-0.754px,p90 displacement1.09/1.31px). Correct the implication that no local features exist: global allocation caused sampling bias. VRM3 still only0/2 points. VRM2 board/surface motion differs, but physical movement/height/viewpoint cause remains unproven. User reports no movement; no normal/defect labels inferred.
- Artifacts vrm_board_motion_181938, vrm_board_and_surface_motion_181938 and vrm_local_board_motion_181938; diagnostic script only. No input warping corrections, capture/training/runtime change or robot/conveyor command. Tracking filters are diagnostic, not production acceptance limits. Local sampling refinement recorded in the same batch.

## 2026-09-05 grouped VRM05 normal-lip-subtle-lip sequence — corrected

- User explicitly clarified184100 was intentionally a very subtle lip defect, not normal return. Retract false-warning/normal-return-failure assertion; correct only VRM5 label from physical clarification. Frozen scores0.028589(normal),0.987525(lip),0.623486(subtle lip) agree with these three labels. No actual normal-return test established; historical194959 miss persists.
- Other parts reportedly untouched, not automatically labelled normal. Saved texture matching shows apparent VRM2 dx9/dy-0.5px and VRM3 dx9--10/dy2.5--3.5px versus181938 in both later images. Diagnostic image displacement only, not proof of physical motion or camera fault. Need disentangle illumination/viewpoint/registration/matching effects. Reviewed vrm23_unchanged_review/review.png, retained vrm_unchanged_motion_181938/motion.json.
- No new capture, fitting, live rules/model changes or motion commands during correction/audit. Earlier captures flashOFF/4000x3000/69mm, overview restored. Reserved validation remains training-disabled; no per-slot warp to excuse displacement. Related correction and audit grouped here.

## 2026-09-05 grouped VRM05 comparison — corrected physical label

- User clarified that current181938 is normal, seated against the wall without resting on the lip. The defect confirmation referred to historical194959. Assistant's prior current-defect attribution and additional-miss claim are retracted. Only current VRM05 corrected to PRESENT/PASS in reserved manifest and comparison.json; other slots unlabelled and historical defect unchanged.
- Frozen score0.028589 and alignment0.976093 unchanged: no warning agrees with normal ground truth, not an authoritative runtime PASS. Source hash b080de57756a4614d7905b5257123c4c97f0a879fe8b19b68ae2961ac410be2c preserved. No fitting, automatic normal-training ingestion, image/score/model/threshold change or robot/conveyor command. Artifacts vrm05_comparison_181938; correction is explicit user ground truth, not tuning to model output.

## 2026-09-05 grouped nonlinear seating alternative

- Offline frozen B0 multiscale4x4 + SVC RBF C1/gamma=scale/balanced trained on106 train crops only. Scores are sigmoid margins, explicitly not calibrated probabilities. No holdout threshold tuning.
- Train105/106, validation10/10, historical4/5, current91/92: persistent194959 VRM05 miss and new150517 VRM03 miss0.4861. Not promoted; separate candidate.joblib and review.json in vrm_multiscale_rbf_offline_20260905. Existing4x4 logistic/bridge/runtime untouched.
- Experimental evaluator option and overwrite guard added; syntax passed. No capture or robot/conveyor command. Related implementation, replay and rejection recorded as one batch. Persistent miss remains unresolved; no false completion claim.

## 2026-09-05 grouped missed-holdout feature audit and 7x7 probe

- Verified106 training crop hashes and isolated194959 VRM05 holdout. Frozen feature cosine nearest normal0.84546 vs defect0.80333; spatial contributions reconstruct logit-1.03377/score0.262353. Visually reviewed neighbors.png. These are feature-level diagnostics, not pixel-local causal explanations or grounds for relabeling.
- Separate7x7 spatial probe fit only existing106 train crops, C1 and diagnostic0.5 unchanged. Train106/106, validation10/10, historical holdout4/5 still missed; current session91/92 vs existing92/92, new150517 VRM03 miss0.4275. Rejected candidate, no export/promotion. Source scripts compile; no capture, live rule/model change or robot/conveyor command. Artifacts vrm05_holdout_feature_audit and vrm_multiscale7_seating_offline_20260905. Unresolved historical miss retained explicitly; batch record after related work.

## 2026-09-05 grouped offline VRM alternative and frozen-model regression

- Replayed22 archived scenes with board-only registration and GPU YOLO; fixed raw centroid references fitted only on historical normal151315/151404/151508. No test fitting or tolerance relaxation. First12-frame run stopped on missing legacy manifest hash; resume reused verified outputs. All22 source hashes ultimately verified against manifest or archived original report.
- Explicit PRESENT pose-labelled92 slots: fixed-centroid alternative gave9/77 normal false warnings and8/15 defect detections; not promoted. Same-pixel frozen seating+actual presence gate gave0/77 false warnings,15/15 defect warnings and0/11 EMPTY seating warnings. OR retained9 false warnings; AND retained7 misses. No fusion replacement.
- Separate historical holdout194959 exact hashed crops replayed: four normal no warnings, defective VRM05 score0.262354 remains missed at diagnostic0.5. Recent success is retrospective development evidence, not independent certification. No relabel/refit/threshold lowering. Disabled bridge metadata blocker text updated to reflect verified parity/gating and persistent miss; runtime disabled.
- Artifacts in vrm_fixed_pose_offline_20260905, scripts evaluate_vrm_fixed_pose.py and compare_vrm_pose_seating.py. No capture, active model/decision change or robot/conveyor command. Batch record after related checks, per user request. Outstanding historical miss, geometry calibration and independent acceptance validation remain.

## 2026-09-05 grouped VRM geometry context investigation

- Batched raw empty/normal boundary review, normal170142 GPU geometry replay (PatchCore intentionally disabled), texture comparison and historical geometry counterfactual. Normal VRM2 again warned at1.02848mm; pairwise texture motion165914 versus170142 was0/0.5px, whereas physically moved VRM5 was-7/-6.5px (diagnostic only).
- audit_vrm_pose_context.py verifies identical historical normal151315 centroid/reference yields0.09169mm with common correction and0.72190mm without it, crossing advisory0.70mm. Current5-part scene disables correction requiring6 detections. Occupancy-dependent common correction and post-correction reference context mismatch reproduced; other mask/projection effects not ruled out. Historical lip180801 remains1.20496mm with correction and1.38634mm without.
- Artifacts: vrm02_pose_boundary_review/context_audit.json and review.png, vrm_pose_texture_pair_170142_165914, bridge report174122. Assertions passed. No production calibration/model/threshold/fusion changes or capture/motion commands. UNKNOWN retained. Next: occupancy-independent board reference validation; do not normalize away component displacement. Records grouped after this diagnostic batch per user preference.

## 2026-09-05 VRM2 auxiliary geometry audit

- Read-only audit_vrm_pose_report.py verified all5 VRM residuals in172632 full report. VRM2 error1.011070mm comes from YOLO geometry; new seating score0.000426 is not its warning source. Only5 candidates means common-bias correction requires6 and is skipped. Fixed references were calibrated post-common-bias; sparse-scene transfer remains unverified.
- Counterfactual removal of slot reference still yields0.979876mm, so simply deleting offsets does not resolve warning. Physical/mask/registration discrepancy not yet isolated. No active behavior or thresholds changed, no capture or motion; UNKNOWN/ADVISORY_ONLY retained. Audit assertions passed; work is diagnosis, not completed production fix.

## 2026-09-05 isolated full-report bridge verification

- Saved165914 replay with candidate injected only into test process; bridge disk disabled and active models unchanged. CPU sandbox lacked CUDA; GPU rerun produced YOLO/PatchCore evidence and visible heatmap (vrm_bridge_full_report_test/20260905_172632_641217).
-25 slots:20 true-empty advisory candidates, correct VRM5 SEATING? at0.8757, but existing YOLO geometry also flags normal VRM2 POSE? at1.011mm. Full integration not accepted; no threshold change. Final UNKNOWN/ADVISORY_ONLY retained. No capture or robot/conveyor command; legacy geometry discrepancy, calibration and historical holdout miss remain unresolved.

## 2026-09-05 real state-to-seating chain

- Existing VRM state model actual outputs tested:20/20 present slots reach seating,0/5 empty slots reach seating. Isolated bridge harness, no active runtime change; report actual_presence_integration_test.json.
- Real-crop parity remains4.77e-7. Full25-stage/report run still not done. No capture,training,motion or authority changes.


## 2026-09-05 bridge real-input tests

-20 original crops through existing seating provider match NPZ scores within4.77e-7. In-memory injected presence gate and SEATING? display tests pass; fused UNKNOWN retained. Disabled metadata/active runtime unchanged.
- This is isolated provider testing, not full inspection or live presence validation. No motion,capture,fit; report plus165057/integration_bridge/real_crop_integration_test.json. Remaining task actual presence-chain test and explicit advisory-only wiring.


## 2026-09-05 disabled integration bridge

- Confirmed existing TorchScript/FLAT-SEATING provider and nonempty .90 gate. Exported new NPZ-head model into separate TorchScript bridge; batch2 trace parity0.0. Original RGB crop contract retained. Files under vrm_multiscale_seating_plus_165057/integration_bridge.
- Runtime disabled,advisory only, active models untouched. Real-image conversion parity/display and presence gating unverified; no definitive PASS/FAIL authority. No motion/capture/training performed.


## 2026-09-05 normal reseating170142

- All5 new reseated normals0warnings,max .003147,alignment .979450. Viewed/reserved capture, frozen model unchanged. Four postfreeze scenes18normal0warnings,2defects2warnings; limited evidence, no deployment.
- Flashoff/overview restored,no fit/threshold/runtime edits or motion commands. Further software validation consolidation pending; UNKNOWN maintained.


## 2026-09-05 isolated05 validation165914

-05 .875697 onlywarning,normal4 max .005083; alignment .980483. Viewed/reserved source, no fitting. Current candidate postfreeze13normal0warnings/2defects2warnings across3scenes, not deployment qualification.
- Flashoff/overview restored,no motion or runtime/threshold edits. UNKNOWN/advisory retained.


## 2026-09-05 isolated04 validation165642

- Frozen candidate04 .811235 onlywarning,other4 max .007826. Alignment .980354,source viewed/validation-only. No refit/promotion/threshold change; few postfreeze scenes remain limitation.
- Flashoff/overview restored, no motion commands. Next05 independent on-lip test,04normal. UNKNOWN maintained.


## 2026-09-05 normal165413

- Frozen plus165057 new normal scene0/5 warnings,max .013893,alignment .979530. Source reviewed/reserved; no fit,promotion or threshold changes. Flashoff/overview restored, no motion commands.
- Next isolated04 fresh on-lip test; UNKNOWN remains.


## 2026-09-05 new04 training165057

- New explicit04left defect scene archived, not164343 reuse.30crops6scenes;106 total fit. Development72/72 (59normal13defect), historicalval10/10,holdout4/5;04miss now .9731. Prior03 .5727 marginal. Separate artifact multiscale_plus_165057, no deployment.
- Flash off/overview restored, no motion/threshold/camera changes. Reserved test scenes excluded; need new postfreeze normal/defect checks. UNKNOWN maintained.


## 2026-09-05 VRM04 coverage

- Reviewed failed04 versus training crops.04 training18normal/2defect (historical15/0,current3/2); two defect views rotation/right shift. Shared-slot classifier but limited04 variation. Findings and raw review in vrm04_training_review_164343.
- No new fit/capture/promotion; test164343 reserved. Next user setup requested: new04 left translation-on-lip,all othersnormal, rough face up. No motion commands.


## 2026-09-05 mixed validation164343

-01 detected .996606;04 intended on-lip miss .441096. Normal3 no warnings; alignment .980647. Frozen artifact unchanged, validation-only source recorded. Postfreeze4scenes16normal0warnings/4defects3warnings, not deployment-ready.
- Flash off/overview restored, no fit/threshold/runtime changes or robot/conveyor commands. Keep04 defect label; do not consume this test as training without new explicit scope.


## 2026-09-05 isolated03 validation164022

- Frozen model03 .996247 only warning, other4 max .029882; alignment .981754. Reserved new scene, no fitting. Postfreeze3 scenes13 normal0warnings/2defects2warnings, not broad reliability proof. No deployment or threshold edits.
- Flash off, overview restored, no motion. Next cross-slot01/04 defect control with remaining slotsnormal; UNKNOWN maintained.


## 2026-09-05 isolated02 validation163741

- Frozen candidate detects only02 (.998406); others max .007381. Alignment .979809, original reviewed, validation manifest updated. No fitting/promotion; displacement obvious here, no minimum-detectable-offset claim.
- Flash off and overview restored; no robot/conveyor commands. Next isolated03 control, UNKNOWN stays.


## 2026-09-05 normal163509 frozen validation

- New normal scene reserved, alignment .980084. Frozen latest candidate0/5 false warnings, max .008891 at unchanged diagnostic.5. No fit or promotion; one scene only, UNKNOWN retained. Report vrm_multiscale_normal_holdout_163509.json.
- Flash off/overview restored, no robot/conveyor motion. Next fresh isolated02 defect test without training.


## 2026-09-05 training163146

- New explicit02/03 on-lip training capture archived (not validation reuse).25 crops5 scenes; hash/group leakage checks passed. Flash off, overview restored, no motion.
- Separate101-sample multiscale fit: current development43/43 normal and9/9 defect diagnostic agreement; historicalval10/10,holdout4/5. Previously missed02/03 now .8252/.7590. Not fresh blind validation; no deployment or threshold change. Old models preserved, UNKNOWN retained. Next fresh normal control required.


## 2026-09-05 multiscale seating training

- Trained separate96-sample supervised head on frozen layer5+final B0 spatial features; no reserved images fitted. Historicalval10/10,holdout4/5; current52 slots50 agreements, two translation misses persist (.480731/.3721). No claim of complete correction.
- Predictor replay parity<1e-5 verified; overwrite guard added. Candidate remains UNKNOWN/advisory, no active runtime replacement, thresholds/camera/motion unchanged. Artifacts vrm_multiscale_seating_candidate_20260905.


## 2026-09-05 four false warnings inspected

- Raw comparisons exported/reviewed for14363205,15051705,15080704/05. Three have1–2px leave-scene-out excess; largest5px case also boundary/width variability. Raw and CLAHE agree on150807 shifted vertical edges, disallowing blanket edge-detector-error explanation.
- Findings.json documents limited observed normal coverage versus unmeasured mechanical clearance. No test-to-calibration leakage, relabeling, runtime edits, captures or motion. Continue treating combined evidence as UNKNOWN; no validated threshold available.


## 2026-09-05 classifier plus boundary retrospective comparison

- Ten scenes/50slot observations: classifier5/7 defects0/43 false warnings; OR edge comparison7/7 defects but4/43 false warnings; AND4/7 defects0/43 false warnings. Edge min/max are descriptive development evidence, not calibrated tolerances. Recovered misses do not justify deployment.
- Added reproducible combination audit, artifact hash checks, UNKNOWN on all outputs, missing-evidence tests pass. Report vrm_combined_evidence_audit_160027.json. No training/capture/runtime changes or motion commands. Remaining issue is boundary-only false warnings, not absence of a combined diagnostic.


## 2026-09-05 visual boundary review

- Six raw crops exported with coordinates and visually reviewed; review.png/findings.json under vrm_boundary_review_160027. Rough part versus patterned empty slot discernible, but hidden inner wall/contact height not measurable. No invented exact polygons or shadow-as-hole labels.
-02 remains user-confirmed defective. No training, threshold/runtime change, capture or robot/conveyor commands. Boundary-ground-truth task only partially feasible from top view; maintain UNKNOWN for ambiguous seating.


## 2026-09-05 per-slot envelope audit

- Leave-scene-out normal edge ranges plus concordant opposing-edge excess implemented; three synthetic cases pass.02 missed translation now has3px descriptive excess, yet normal05 reaches5px and rotated05 defect0px. This fallback alone still overlaps normal/defect; cannot confer PASS/FAIL.
- Report vrm_edge_profiles_regression_160027/slot_envelopes.json, no threshold/runtime/model/capture changes or motion commands. Next boundary-label review on existing crops; no further physical capture required yet.


## 2026-09-05 profile boundary experiment

- Signed raw/CLAHE edge diagnostic implemented, synthetic4px translation passed, montage inspected. Four recent controls raw normal<=2px, missed02 left/right -4px; CLAHE right edge differs16px. Previous15080703 raw -7px both sides. Provides extra displacement evidence, not confirmed socket metrology.
- Ten-scene regression exposes earlier normal edge variations up to9px, prohibiting global2px-style thresholds. No runtime promotion, no training/capture/motion commands; original learned inputs and fixed coordinates maintained. Reports vrm_edge_profiles_{160027,regression_160027}; UNKNOWN retained.


## 2026-09-05 boundary-control audit160027

- Existing four scenes replayed with frozen sigma1 boundary diagnostic. Missed02 center1.67px vs normal max8.5px; normal masks visibly shrink (05 width/height ratios .921/.904,03 width .890). No clean center-distance separation. Model-score miss and unreliable geometric fallback both documented; not proven physical pixel motion.
- Added reproducible boundary comparison with synthetic translation/axis-equivalence/missing-mask checks passing. Artifacts runtime/inspection/vrm_outline_controls_160027/{comparison.jpg,boundary_deltas.json}. No capture/fit/threshold/runtime change, no robot/conveyor commands. Boundary ambiguity unresolved, UNKNOWN remains.


## 2026-09-05 slot02 translation160027 miss

- Frozen2/4 replay misses user-controlled02 on-lip defect (.439465/.404812 at diagnostic.5), alignment .980079; all other slots no warning.2x2 normal05 .402850 highlights weak score separation. No threshold change or fitting; validation manifest reserved. No deployment, UNKNOWN retained.
- Flash-off capture, overview restored, no robot/conveyor commands. Need boundary/normal-control analysis; physical seating height not directly measured. Earlier03 successes not generalized to02.


## 2026-09-05 opposite translation155745

- Independent03 opposite-displacement scene: frozen2/4 scores .625382/.748617, warnings only03. Other4 no warnings, alignment .979740. Reserved validation, no fitting/threshold/runtime changes. Previous150807 miss unresolved; UNKNOWN retained.
- Flash-off capture and overview restored, no motion commands. Next independent slot02 translation check; physical height per user setup, not measured.


## 2026-09-05 independent translation155509

- Reserved new VRM03 translation-on-lip capture, alignment .980772. Frozen spatial2/4 scores03 .814386/.935997; only03 diagnostic warning, no other-slot warnings. No training or threshold changes; artifact hashes unchanged. UNKNOWN retained; earlier150807 miss prevents promotion.
- Optical flash off, overview restored, no robot/conveyor commands. Physical seating height not metrically measured; need independent opposite-displacement check.


## 2026-09-05 frozen normal control154927

- Independently captured normal VRM scene reserved from training; alignment .981301. Frozen2x2 and4x4 candidates both 0/5 false warnings at diagnostic .5 (max .216794/.110814). Added no-fit predictor with artifact/source hashes and alignment/class guards. All statuses UNKNOWN; absence of warning is not authoritative PASS.
- Existing subtle translation miss remains; no promotion or threshold changes. No robot/conveyor commands or camera setting changes. Next physical test: isolate subtle translation on slot03 with other four unchanged normals.


## 2026-09-05 four supervised scenes

-154302 even translation defects captured/checked;20 training crops4 scenes.2x2/4x4 frozenB0 comparators both normal26/26,defect5/6; historicalvalidation9/10,holdout4/5.03 translation scores.2373/.3964 remain misses at0.5. No threshold or runtime promotion; test score change not success.
- Separate artifact directories, validation/excluded scenes never fitted. Fresh normal control next. Flash-off overview restored, no motion.

## 2026-09-05 translation sample153909

- Odd translation defects/even normal captured and archived;15 crops3 scenes. Separate91-crop fit saved, previous candidate retained. Current normal26/26,defect5/6; latest translation test03 .1975 remains miss. Historicalvalidation9/10 (regression),holdout4/5. No promotion/threshold changes.
- Validation and invalid152604 excluded fit; overview restored, no motion. Need even-slot translation training and independent validation.

## 2026-09-05 explicit training2 scenes / candidate refit

-153405 even02/04 defects,odd normal captured/checked; total10 crops2 scenes. Invalid152604/reserved validation excluded. Historical76+new10 fit separately, not active runtime model.
- Current heldout normal26/26,defect4/6 versus baseline1/6 at diagnostic0.5;03 rotation.3505/translation.145 remain misses. No threshold change, production verdict or promotion. Historicalholdout4/5. More translation coverage needed in separate training data.
- Flash-off overview restored, no motion commands.

## 2026-09-05 corrected153051 training scene

- Flash-off captured, visually checked and user-ready odd01/03/05 defects,02/04 normal. Archived5 crops/one physical scene, SHA checked. Invalid152604 skipped and still quarantined; validation excluded. No training or production changes yet.
- Overview restored, no motion commands. Complementary slot labels needed next.

## 2026-09-05 invalid152604 capture quarantined

- User corrected01 flipped/03 settled. Whole scene excluded; supervised spec training_allowed=false. Five initially generated crops moved to recoverable vrm_pose_session_20260905_quarantined_152604; no training/model changes occurred.
- New builder enforces source hashes/reserved validation exclusions and refuses disabled spec. Capture overview restored; no motion. Fresh corrected setup needed.

## 2026-09-05 spatial seating baseline

- Historical-only76 TRAIN RGB crops/frozenB0 spatial2x2/logisticC1; validation10/10, historical holdout4/5, current normal26/26 but defect1/6 at diagnostic0.5.27/32 total is misleading; not promoted. Current session excluded fit, splits checked.
- Latest translation score.035, current rotation03 .0346. No lowering thresholds to these test cases. Runtime candidate only, all UNKNOWN. No capture/motion/active model changes. Need separate current-camera supervised train scenes.

## 2026-09-05 static residual check

- New masked-static-patch audit,117/118/123 accepted; left71/72/74 median0px,95percentile abs1px/axis on143632/145643/150807 vs empty134637. Visual arrows checked. No broad registration shift supported; don't blame observed7..12px discrepancy solely on global alignment.
- No image/slot corrections, capture, refit, thresholds or motion. Inner-edge and foreground localization still unvalidated. Artifacts vrm_static_registration_20260905.

## 2026-09-05 empty groove diagnostic

- New offline empty134637 dark-profile bounds overlaid on20 crops, visually checked.03 normal left gap already -4px, translation defect -12px; zero-crossing would false-flag normal. Reference is unvalidated groove, not inner wall. No coordinate/tolerance changes.
- Reports vrm_socket_reference_audit_20260905, all UNKNOWN. No camera/motion/refit/runtime changes. Need calibrated inner-edge localization, not direct profile cutoff.

## 2026-09-05 position range audit

- New offline leave-scene-out audit; latest150807 entirely excluded from refs.03 defect outside normal range7px x,2px y, while normal holdouts deviate up to5.11px x/5.47px y. No position threshold promoted; these ranges mix placement and extraction variability.
- Checked existing CAD clearance VRM11x14/socket12x15mm, allowance0.5mm/axis. No tolerance or runtime changes. Need actual socket center reference and uncertainty. All UNKNOWN; no capture/motion/refit.

## 2026-09-05 translated VRM03 capture150807

- All5 present,03 angle0deg while user-confirmed translated/on-lip defect. FAIL03 ground truth archived separately from angle absence. Center delta vs145643=(-7.5,+2)px; unchanged controls move up to4.55px in one axis due combined capture/fit variation. Not calibrated translation/height measurement.
- No PASS inferred, no new threshold or runtime/model change. Flash-off, overview restored, no motion commands. Further geometry tolerance validation required.

## 2026-09-05 frozen outline150517 fresh test

- Presence all5; outline -.67/0/-7.31/2.29/-.92deg. Frozen3deg diagnostic warns03 only, consistent with user defect; one fresh post-selection scene, not validated production performance. No retuning/refit.
- Visual comparison checked; holdout archived. Translation/height not tested, no automatic PASS/FAIL authority. Flash-off overview restored, no robot/conveyor motion.

## 2026-09-05 blur1 outline development candidate

- Offline sigma1/2/3 comparison35 crops each: sigma1 separates four known rotation cases (abs4.81..11.31deg) from25 present normal observations (<=1.82deg). Selection used these images, not fresh validation. Six EMPTY require independent presence and cannot be assigned pose.
- Montage visually checked. Diagnostic3deg frozen in vrm_outline_candidate_20260905.json; explicitly runtime false/UNKNOWN, not production tolerance or calibrated metrology. Sigma2/3 fail one existing defect. No runtime/refit/capture/motion changes. Next independent new scene required.

## 2026-09-05 swapped normal145643

- Flash-off, normal01/03 physical swap verified; frozen presence5/5. Single-reference texture scores collapse on01/03 to.193/.238, gaps.0045/.0191, while unchanged slots>.509. Pose angles invalid for swapped parts, not defects. Candidate not promoted or templates retrained.
- Outline alternate deviations -.87/-.68/0/-.68/-1.85deg; remains insufficient for previous tilted01. Ground truth normal archived, no selective ground-truth-dependent fusion. Overview restored; no motion/runtime changes.

## 2026-09-05 texture movement measurement candidate

- Added offline fixed-reference central-patch motion search, no correction of component pose or downstream images.35 slots/7 scenes evaluated. Defects02/04/05/01 match angles -12/+10/+11/-7deg, scores.420/.479/.333/.484.144513 dx17px. Diagnostic estimates only, all UNKNOWN.
- Earlier normal135111 fails texture matching (.195..254) despite presence; arbitrary angle not usable. No confidence threshold promoted. Requires cross-part normal test and independent presence/match quality before runtime. Empty maxima not interpreted.
- Three-scene15-pair montage visually checked. Synthetic motion/blank/immutability tests4 passed after import path fix. No capture, refit, runtime or motion changes. Reports vrm_texture_motion{,_visual}_20260905.

## 2026-09-05 boundary-segment alternative rejected for promotion

- Offline seven-scene35-crop replay, contour segments/median and foreground masks saved.144513 VRM01 mask visibly omits upper/right portions: segmentation error precedes angle fitting. Boundary median2.96deg vs enclosing1.21deg does not solve it.
- Defective142049 VRM02 regresses to0deg median;04/05 defects -9.83/-10.20. No selective per-label switching or threshold changes. All UNKNOWN/advisory, no runtime/refit/capture/motion. Artifacts vrm_boundary_segments_20260905.

## 2026-09-05 outline counterexample144513

- User-ready VRM01 rotated/on-lip capture, all5 presence correct. Outline01 gives1.21deg/fill.83 and does not faithfully follow visible boundary; normal controls -.77/-.65/-.74/0. Earlier normal max2.96deg overlaps this defect score. No threshold promotion or claim of pose success.
- FAIL01 holdout recorded; prototype stays offline UNKNOWN. Need boundary/overhang work using this image, not larger staged defect. Flash-off, overview restored, no motion commands.

## 2026-09-05 144017 identity resolved

- User explicitly confirmed VRM05 rotation mistake. Holdout now labels05 pose FAIL, other4 unchanged PASS ground truth; all PRESENT. No slot remap. Outline -10.89deg agrees with defective05; no authoritative verdict or threshold promotion. No training/capture/motion.

## 2026-09-05 capture144017 numbering check required

- All five present; outline deviations 01..05 = 0/-1.40/0/-1.74/-10.89deg, montage visually checked. User was instructed VRM1, but rotated crop is software05. No defect label archived until physical identity confirmed; no automatic slot remap.
- Capture flash-off, overview restored, no robot/conveyor commands. Models/thresholds unchanged, reports advisory. Artifacts vrm_outline_holdout_144017 and presence blind_144017.json.

## 2026-09-05 fresh normal control143632

- Flash-off capture, all5 VRM present/flat user-confirmed and visually checked. Frozen presence5/5; unchanged outline axis residuals 0/-.77/0/-.86/0deg. Fits visually checked. Not calibrated PASS; one physical scene.
- Audit CLI now supports separate stamps/output; saved vrm_outline_holdout_143632, holdout labels excluded training. Prior defects +6.18/-11.31deg remain development examples. No runtime/refit changes; overview restored, no motion commands.

## 2026-09-05 foreground outline feasibility

- Deterministic seeded GrabCut/minAreaRect added to offline outline audit. Visual6-pair comparison confirmed two rotated outlines; fitted image-plane axes +6.18/-11.31deg. Expanded25 crops: 11 present normal controls -2.96..0deg, 2 defect cases; development regression only.
- EMPTY slots also produce false rectangles (EMPTY01 -11deg), so independent presence gating mandatory. No production threshold, pose PASS/FAIL or runtime promotion. New all-flat physical control needed. No capture/motion commands.

## 2026-09-05 local outline diagnostic

- audit_vrm_outline.py completed after line-array shape fix; six registered crop comparisons visually checked. 142049 VRM02 and142337 VRM04 have visible slot-relative rotation, but Hough candidates mix component/socket/texture edges, including controls.
- Artifacts vrm_outline_audit_20260905/{comparison.jpg,edges.json}; no reliable angle or calibrated defect verdict yet. All UNKNOWN/advisory; no runtime, camera or motion changes. Must disambiguate component outline before thresholding.

## 2026-09-05 pose regression (offline, unchanged models)

- audit_vrm_pose_holdout.py completed four scenes. Confirmed defective VRM02(142049)/VRM04(142337) yield raw CORRECT .765802/.843660, ROTATED .148054/.124398; both UNKNOWN at .9. No successful rotation detection claim.
- Disabled seating candidate respected. No final hybrid run, promotion, refit, capture or motion. Lowering confidence is not a remedy. Next requires independent outline/slot-relative pose verification with normal controls; ground-truth defects excluded normal training.

## 2026-09-05 user-confirmed slight rotation is defective

- 142049 VRM02 and new142337 VRM04 labeled expected_pose FAIL / ROTATION_POSITION_ERROR, distinct from presence PRESENT. Both excluded normal training. No inference verdict overridden with ground truth.
- Flash-off142337 visually checked; frozen presence5/5, scores .011650/.994873/.020993/.994625/.008243. Pose not tested by this probe; advisory UNKNOWN unchanged.
- Overview restored, no robot/conveyor motion. Further work: pose regression on these confirmed defect cases.

## 2026-09-05 slight-rotation presence holdout 142049

- VRM02 user-confirmed slight rotation (not 90deg), VRM04 present; 01/03/05 empty, visually checked after flash-off capture. Frozen presence 5/5 matched, p=.004740/.993660/.162735/.997186/.029237.
- Three fresh scenes total15/15 slot observations, not 15 independent trials. EMPTY03 score .162735 warrants continued testing; no threshold/refit changes.
- Holdout manifest excludes training, pose correctness not established. Advisory/offline retained. Overview restored; no robot/conveyor commands.

## 2026-09-05 frozen presence complementary scene 141603

- Visually verified EMPTY01/03/05, PRESENT02/04. Unchanged frozen model 5/5;
  p=.014097/.996073/.011641/.998411/.004037; ALIGN .981977.
- Post-freeze total two physical scenes, EMPTY5/5 PRESENT5/5. Holdout manifest
  updated; no training or runtime promotion. Advisory UNKNOWN remains.
- Pose/seating not validated by presence scores; no robot/conveyor commands.

## 2026-09-05 frozen presence post-freeze scene 141311

- Flash-off capture, VRM02/04 empty and 01/03/05 present visually checked.
  Frozen predictor 5/5: p=.998149/.010204/.997115/.044818/.985054.
  One physical scene, not five independent trials; training excluded via
  vrm_presence_context_holdout_20260905.json. No promotion or refit.
  Overview restored; no robot/conveyor motion commands.

## 2026-09-05 dual-region VRM presence probe

- Central .55 + context 1.30 frozen B0 RGB features, logistic C1. Historical
  scene-out 70/70; inspected session regression EMPTY 6/6, PRESENT 34/34.
  Present score ranges: empty .001513–.036670, present .961077–.999745.
- Gain .85/1.15, translations ±3px x/y: 0/240 synthetic sensitivity errors;
  not independent validation. Session never fitted, but used for development.
- Frozen NPZ + predict_vrm_presence_context.py no-refit replay verified <1e-9
  difference. Candidate remains offline ADVISORY_ONLY, final UNKNOWN, no runtime
  promotion, capture or motion. Need fresh mixed physical EMPTY/PRESENT setup.

## 2026-09-05 original-source sampling audit

- audit_vrm_source_sampling.py uses raw-image H plus ECC inverse-map coordinates;
  visually verified final crop alignment. Upright preview is not H's source frame.
- VRM02 central canonical 69x88 samples correspond to source 54x68–69 pixels
  for 134637/135454/135111. This area is enlarged in ROI; prior downscale-loss
  hypothesis does not hold. Direct source crops show no substantial new texture.
- No direct-crop classifier accuracy measured; no runtime activation, settings,
  thresholds or physical commands. Artifacts: vrm_source_sampling_20260905.

## 2026-09-05 VRM02 crop audit

- audit_vrm02_crops.py -> runtime/inspection/vrm02_crop_audit_20260905.
- EMPTY 134637/135454: same geometry, 69x88 central crop, visually inside socket.
  mean 53.339/51.616; std 3.670/3.120; LapVar 6.595/6.028; MAE 2.500,
  pixel corr .724. PRESENT 135111: mean 57.944/std 5.389/LapVar 10.529.
- No obvious crop misplacement. Low-detail central crop enlarged to 224 cannot
  recover texture. Large classifier swing demonstrates sensitivity; illumination,
  capture and resampling effects not causally separated. No runtime/capture
  settings/threshold changes or physical commands. User permits concise internal
  notes; keep provenance and limitations for later summary.

## 2026-09-05 — VRM02-only removal validation

- Captured flash-off 135454; visually checked empty VRM02 and four present
  VRMs, recorded labels, overview restored. Same historical-data probe correctly
  classified this scene's one EMPTY and four PRESENT observations.
- Fresh totals: EMPTY 5/6, PRESENT 34/34. The fully empty scene's VRM02 false
  positive remains unresolved; this does not establish robustness. No new
  training, runtime activation, threshold change or robot/conveyor motion.
  Report: vrm_texture_presence_probe_vrm02_20260905/evaluation.json.

## 2026-09-05 — VRM-only scene validation

- Captured flash-off 135111; visually confirmed five VRMs and other slots empty.
  Overview restored, scene labels preserved. Frozen probe trained on the same
  historical data predicted all five PRESENT; fresh cumulative present 30/30,
  empty 4/5. No new fitting or runtime activation.
- This supports presence recognition without neighbouring components in this
  scene, not complete background invariance. VRM02 empty false positive remains.
  Report: vrm_texture_presence_probe_only_20260905/evaluation.json.
  No robot or conveyor motion commands or decision changes.

## 2026-09-05 — Fresh fully empty board validation

- User confirmed all 25 components removed. Captured flash-off 134637 and
  visually checked empty board; overview restored. Manifest records full removal.
- Same historical training data, new capture excluded from fitting: fresh empty
  4/5, with VRM02 false PRESENT at 0.578704. VRM04 present score 0.430278
  is also near the binary 0.5 boundary. Prior fresh PRESENT remains 25/25.
  These are uncalibrated candidate outputs, not authoritative verdicts.
- Saved evaluation in vrm_texture_presence_probe_empty_20260905. Candidate
  remains disabled, thresholds unchanged; no robot/conveyor motion commands.

## 2026-09-05 — Offline central-texture VRM presence probe

- Added evaluate_vrm_texture_presence.py: central 55% original RGB slot crops,
  frozen EfficientNet-B0 features and balanced binary logistic classifier.
  Correct and rotated VRMs map to PRESENT; pose/seating remain separate.
- Leave-one-recorded-scene-out evaluation: empty 5/5, present 62/65.
  Today's five captures excluded from fitting: present 25/25 including lip
  placements. Results in runtime/inspection/vrm_texture_presence_probe_20260905/evaluation.json.
- Only five historical empty observations and no fresh empty controls: not
  production validation. Candidate remains offline ADVISORY_ONLY, runtime
  disabled. No fusion changes, capture, robot or conveyor commands; CPU probe
  completed successfully. Next requirement is fresh empty-slot validation.

## 2026-09-05 — Five-frame normal/lip/return evaluation

- Captured normal-return 133256, flash off, overview restored. Evaluated v4
  in memory on CPU with registration and the existing non-empty gate.
  All registration scores were OK (0.9865–0.9868).
- VRM05 normal/lip/return seating scores: 0.008784/0.081363/0.006891.
  VRM01 lip scored 0.059623 (UNKNOWN), return 0.040985 (FLAT).
  Of 23 normal slot observations: 20 FLAT, 3 UNKNOWN, zero SEATING;
  all three UNKNOWNs were VRM04 blocked by non-empty probability below 0.90.
  Two physical lip observations yielded one SEATING and one UNKNOWN.
- Repeated slots in one session are not 25 independent samples. No threshold
  changes, training or runtime promotion; earlier mixed-scene false positive
  remains unresolved. No robot or conveyor motion commands.

## 2026-09-05 — VRM01 lip validation capture

- Captured flash-off 124122 after user setup confirmation and visually checked
  bottom VRM01 displacement. Stored user-confirmed SEATING label in session
  manifest; four captures total, training disallowed and evaluation pending.
- Overview restored; no robot/conveyor motion or decision-rule changes.

## 2026-09-05 — VRM05 normal-return capture

- Saved and visually checked flash-off capture 122706 after user confirmation
  of normal reseating. Session labels preserve the normal/lip/normal-return
  sequence; unchanged slots are not independent physical setups. No training
  or decision changes; evaluation remains pending. Overview restored and no
  robot or conveyor motion command sent.

## 2026-09-05 — Fresh controlled VRM validation pair captured

- Captured flash-off normal 122212 and user-prepared VRM05 lip scene 122437;
  4000x3000 originals and board ROIs saved, overview restored.
- Slot labels and physical-scene IDs are in `vrm_seating_session_20260905.json`.
  Evaluation is pending and training is disallowed. The visible GPU fragment
  prevents assuming the entire board is normal. Seating ground truth is supplied
  by the user's physical setup confirmation, not inferred height from one image.
- Camera capture only; no robot or conveyor motion commands sent.

## 2026-09-05 — Match VRM seating resize to training; false positive persists

- Runtime seating input now uses PIL bilinear resizing, matching training,
  instead of OpenCV INTER_AREA. Original RGB, fixed slots and fusion remain unchanged.
- Offline classifier-only replay of four registered images found VRM05 seating
  0.101769 (194959), and VRM01/02 seating 0.999291/0.999806 (180910).
  Normal VRM01 in mixed 145130 still scored 0.108095 (false SEATING), while
  normal 193555 VRM01 scored 0.052844 (UNKNOWN). Resize mismatch was real but
  does not explain away the cross-scene failure. Runtime remains disabled.
- This diagnostic forced the non-empty gate open in memory only; its empty
  VRM03 response is not an integrated verdict. No thresholds were changed.
  65 tests passed; no capture, robot or conveyor commands. Fresh physically
  confirmed normal/seating scenes remain necessary for independent evaluation.

## 2026-09-04 — VRM seating candidate v4 developed, then disabled after cross-scene regression

- Added a separate S22 fixed-slot `FLAT / SEATING / UNKNOWN` EfficientNet-B0
  provider because the existing VRM `EMPTY / CORRECT / ROTATED` model cannot
  represent a present, correctly oriented component resting on the socket lip.
  It consumes registered original RGB crops and runs only when the independent
  VRM state distribution gives non-empty probability `>=0.90`.
- Dataset v3 groups repeated captures by physical-scene ID to prevent split
  leakage: train `FLAT 68 / SEATING 8`, independent-normal validation
  `FLAT 10`, and fixed regression `FLAT 4 / SEATING 1`. Capture `194959` was
  consumed during the first candidate comparison and is now honestly marked
  as fixed regression, not as a still-blind holdout.
- Candidate v4 uses a fail-safe band: FLAT at `P(SEATING)<=0.052442`, UNKNOWN
  between `0.052442` and `0.078663`, and SEATING at `>=0.078663`. It scored
  `76/76` on train, `10/10` on independent normal controls, and `5/5` on the
  fixed regression. Full 25-slot replay produced zero candidates on normal
  `193555`, only `vrm_05 SEATING?` on lip scene `194959`, and only VRM01/02
  seating candidates on repeated development scene `180910`.
- Cross-scene replay `145130` nevertheless added a false `vrm_01 SEATING?`
  candidate (`P=0.0955`) where VRM01 is a known normal component. The artifact
  was therefore not promoted: metadata is `runtime_enabled=false` and
  `candidate_status=DEVELOPMENT_ONLY_FAILED_CROSS_SCENE_REGRESSION`. Runtime
  loading now requires an explicit enable flag, so merely placing a candidate
  checkpoint in the model directory cannot activate it. The failed first model
  remains preserved as `vrm_seating_candidate_v1_failed`.
- The locked S22 hybrid contract and `ADVISORY_ONLY` PASS/FAIL/UNKNOWN fusion
  remain unchanged. Python/shell syntax checks and 64 unit regressions passed.
  No new scene was silently relabelled as normal, and no camera capture, robot,
  or conveyor command was sent. Fresh independently reseated normal and lip
  scenes are still required before any authoritative promotion.

## 2026-09-04 — Portable DB handoff for S22 hybrid inspection results

- Added `run_export_latest_inspection_for_db.sh` and
  `vision_assembly/integration/export_inspection_result.py`. They convert one
  `s22_hybrid_aoi_v1` report into the `ksmc.vision-inspection.v1` handoff while
  retaining all 25 slot rows, component names, internal IDs, assembly-recipe
  slot codes, finding codes, and presence/pose/orientation/surface measurements.
- External slot codes now exactly follow `assembly-r1`: `GPU-01`, `HBM-01..08`,
  `PM-01..04`, `CAP-01..05`, `IND-01..02`, and `VRM-01..05`. Candidate codes
  map to stable DB terms (`COMPONENT_MISSING`, `POSITION_ERROR`,
  `DIRECTION_ERROR`, `SEATING_ERROR`, `PIN_DEFECT`, `SURFACE_ANOMALY`) without
  dropping the original authority, decision, or confirmed-defect fields.
- Each package copies the source ROI, registered board, three-panel report,
  gated heatmap and overlay, slot diagnostic, optional GPU-pin diagnostic, and
  raw hybrid JSON. Every attachment uses a package-relative path and SHA-256;
  the input image hash is rechecked before export, so the DB is not given
  unusable vision-PC `/home/hc/...` paths as image URLs.
- With no DB URL, the adapter writes an offline directory and ZIP under
  `runtime/inspection/db_outbox/`. An explicit `--endpoint` sends the same data
  as multipart HTTP with an optional Bearer token. Stable inspection and
  idempotency keys allow a failed delivery to reuse the same package without
  creating a duplicate record. DB/API and countermeasure-form mappings are in
  `team_handoff/vision_inspection_db/`.
- The locked fusion decision was not changed. Current findings remain
  `ADVISORY_ONLY`, `UNKNOWN`, and `confirmed_defect=false`; consequently
  `formal_defect_report_allowed=false`. A DB consumer must store them as
  recapture/hold candidates and may not count them as confirmed defects or
  auto-issue a countermeasure report.
- A package generated from known mixed capture `145130` contained the expected
  four findings (HBM-04 direction, IND-01 direction, PM-01 position, VRM-03
  missing), all 25 slots, and seven verified image attachments. All attachment
  hashes passed. Five tests covering mapping, authority preservation,
  authoritative-fail isolation, retry idempotency, and multipart construction
  passed, as did Python compilation and shell/JSON syntax checks. No external
  DB endpoint was available, and no capture, robot, or conveyor command was
  sent. DB URL/auth/cycle identifiers and migration of the conveyor auto trigger
  from its older inspection path to this hybrid report remain open.

## 2026-09-04 — VRM05 lip-seating false-negative root cause

- The user physically confirmed that top slot `vrm_05` was resting on the
  socket lip in S22 capture `194959`. Full RTX-GPU inspection had valid
  registration `0.9807` but produced zero advisory candidates. This frame is
  therefore a confirmed VRM05 lip-seating false negative, not an accepted
  clearance variation or a normal sample.
- Operational VRM v6 classified the slot as `CORRECT 0.9712`. Its metadata and
  training code contain only `EMPTY / CORRECT / ROTATED`; no SEATING class was
  ever trained. Replaying the same crop through historical v2–v6 candidates
  also returned CORRECT (`0.7628/0.9933/0.9554/0.9002/0.9717`), proving this is
  not a recent model-regression event but an out-of-training-scope defect mode.
- Auxiliary YOLO did detect a physical VRM outline, but calibrated position
  error was `0.493 mm`, transverse displacement `0.444 mm`, and mask area
  `21513.5 px`, below the existing 2-D candidate gates. PatchCore scored
  `0.6441`, slightly below the preceding normal VRM05 score `0.6532`, so it
  cannot separate this height/seating condition with a stand-alone threshold.
  The perspective change of the dark square part is being absorbed by the 2-D
  centroid and normal-appearance distributions.
- Previous VRM01/02 lip defects were not recognized by v6. They were exposed by
  slot-specific, repeated-control fusion rules combining calibrated geometry,
  outline, and PatchCore evidence. Those rules were deliberately not generalized
  to unvalidated VRM03–05, which is why no VRM05 seating candidate existed.
- Capture `194959` remains excluded from training as an independent seating
  holdout. No one-frame geometry threshold reduction was made. The corrective
  path is to retain v6 for presence/direction and add a separate fixed-slot
  `FLAT / SEATING / UNKNOWN` provider, trained on VRM01/02 controls and blindly
  evaluated first on VRM05. Models, thresholds, and authority are unchanged;
  all evidence remains `ADVISORY_ONLY` and the board verdict remains `UNKNOWN`.
  No robot, conveyor, or camera-control command was sent.

## 2026-09-04 — Five-slot VRM displacement fusion and record correction

- The user confirmed that all five VRMs were physically misplaced in capture
  `185451`. Before this change, the integrated inspector exposed only
  `vrm_03 DIR?` (1/5). A raw-evidence audit found usable but previously
  un-fused signals: calibrated centroid displacement for VRM02/05, rotation
  probabilities for VRM03/04, and an enlarged outline plus PatchCore response
  for VRM01.
- Capture `183712`, previously documented as a repeated VRM-normal frame, was
  visually and numerically re-audited and found to contain the same five-VRM
  misplaced physical scene as `185451`. It is now excluded from VRM-normal
  evidence. The HBM parts were unchanged in that scene, so the frame may only
  remain in the HBM-normal centroid calibration set.
- Added post-common-bias auxiliary centroid references for VRM03–05 from six
  user-verified normal captures: `[-0.5865,0.0089]`,
  `[-0.3705,-0.1425]`, and `[-0.5780,-0.2489] mm`; the existing VRM01/02
  references remain unchanged. Per-slot maximum residuals across those six
  normal frames were `0.116/0.113/0.252/0.250/0.115 mm`, and the independent
  normal `183405` remained at or below `0.413 mm`. The physical pose tolerance
  remains `0.75 mm`. The `0.70 mm` threshold is only an advisory near-limit
  display band, not an automatic defect threshold.
- VRM advisory fusion now exposes calibrated displacement as `POSE?` only with
  non-empty probability `>=0.90` and auxiliary-outline confidence `>=0.20`.
  A weak raw ROTATED probability `>=0.75` produces `DIR?` only when PatchCore
  also scores `>=0.85`. For VRM01, whose centroid signal did not separate this
  displacement, `POSE?` requires non-empty `>=0.90`, mask area `>=23000 px`,
  and PatchCore `>=0.85` together. Existing lip-seating evidence retains the
  single, more specific `SEATING?` code instead of a duplicate `POSE?`.
- Both `185451` and repeated capture `183712` now produce exactly five advisory
  candidates: `VRM01 POSE?`, `VRM02 POSE?`, `VRM03 DIR?`, `VRM04 DIR?`, and
  `VRM05 POSE?`. Independent normal `183405` produces zero candidates. The
  VRM01/02 lip regression `180910` retains exactly two `SEATING?` candidates,
  and known mixed defect `145130` retains its original four candidates with no
  added normal-slot false positives.
- The user then independently reseated all five VRMs flat and centred and
  captured normal control `193555`. A complete RTX-GPU run measured registration
  `0.9831`, classified all five as CORRECT at confidence `0.9825–0.9982`, and
  measured calibrated pose errors of `0.218/0.255/0.378/0.452/0.096 mm`, all
  below `0.75 mm`; it produced exactly zero candidates. VRM PatchCore scores
  `0.469–0.757` remain surface `UNKNOWN` because no controlled-defect threshold
  exists and were not promoted into stand-alone defect evidence.
- All 65 related tests passed together with Python, JSON, and diff checks. Every
  new signal remains `ADVISORY_ONLY`, and the final board verdict remains
  fail-safe `UNKNOWN`. Captures `183712` and `185451` repeat one physical defect
  arrangement and therefore do not justify automatic FAIL authority. One
  independently reseated normal (`193555`) is now available, but repeated normal
  controls under varied lighting and varied per-slot defects are still required.
  No robot or conveyor command was sent; only the user's stored capture was
  inspected.

## 2026-09-04 — VRM01/02 flat recovery verification and per-slot HBM centroid calibration

- After the user returned VRM01 and VRM02 fully inside their sockets, a blind
  flash-OFF S22 3.5× capture (`183405`) measured 4000×3000 at 69 mm equivalent,
  board rectangularity `0.909`, and hybrid registration `0.9822`. The following
  `183712` frame was initially recorded as the same flat state, but a later audit
  against the user's ground truth showed that all five VRMs were already
  misplaced. It is excluded from VRM-normal validation.
- Before the final calibration, full PatchCore inspection correctly removed the
  two VRM seating candidates, but the visibly unchanged HBM01 intermittently
  emitted a false `POSE?`. Its post-common-bias centroid residual varied across
  normal frames (`0.633/1.270/0.930 mm`), identifying a slot-specific YOLO mask
  centroid bias rather than observed physical HBM movement.
- Added median post-common-bias reference offsets from eight user-verified
  normal frames for HBM01–08: `[0.7368,0.1766]`, `[0.7546,-0.0468]`,
  `[0.5694,0.1915]`, `[-0.0527,0.1728]`, `[0.0521,-0.4582]`,
  `[-0.0563,-0.5857]`, `[0.0107,0.0285]`, and `[-0.0709,-0.2939] mm`.
  This correction is applied after shared frame-bias removal; CAD slot centres
  and the existing `0.75 mm` physical pose tolerance were not widened.
- After HBM calibration, all eight HBM pose residuals in `183405` and `183712`
  were within the original limit, with maxima of `0.513/0.485 mm` respectively.
  The zero-candidate result and recovered VRM01/02 state in `183405` remain valid.
  The contemporaneous zero-candidate result for `183712` was a VRM false
  negative, not a normal pass; the multi-evidence fusion above now exposes all
  five misplaced VRMs.
- The known controlled mixed-defect frame `145130` retained exactly four
  candidates: `HBM04 DIR?`, `Inductor01 DIR?`, `Power Module01 POSE?`, and
  `VRM03 MISSING?`. HBM04 still failed direction because its white dot was at
  `upper_right`, showing that centroid calibration did not suppress the
  independent orientation evidence.
- Sixty hybrid/VRM dataset tests passed, together with JSON and diff checks.
  All providers and these HBM references remain `ADVISORY_ONLY`; the final board
  verdict remains fail-safe `UNKNOWN`. Although measured over multiple frames,
  the HBM references currently represent one physical normal placement, so an
  independently reseated normal set and controlled displacement set are still
  required before any automatic FAIL authority. No robot or conveyor motion
  command was sent; S22 overview was only temporarily released and restored for
  still capture.

## 2026-09-04 — VRM02 lip-seating blind repeat and slot calibration

- After the user accepted the current `power_module_01` placement, one edge of
  `vrm_02` (the second VRM from the bottom) was placed on its socket lip. Three
  flash-OFF S22 captures (`180328`, `180801`, `180910`) were all 4000×3000 at
  69 mm equivalent focal length, with board rectangularity `0.909` and hybrid
  registration scores `0.9842–0.9845`.
- Direct crop comparison showed the controlled VRM02 displacement and also
  showed that VRM01 had not actually returned to the verified-normal crop; it
  retained essentially the same one-sided displacement as the preceding
  VRM01 lip test. The physical ground truth for this scene was therefore two
  seating defects, VRM01 and VRM02.
- Added VRM02's median post-common-bias auxiliary centroid
  `[-0.7187, 0.2383] mm`, measured from six user-verified normal captures. The
  calibrated transverse residual was `0.017–0.100 mm` for those controls versus
  `1.115–1.191 mm` in all three lip-seated captures. Normal VRM02 PatchCore
  scores were `0.229–0.517`; all three controlled captures scored `1.000`.
  Mask-area ranges overlap, so area is used only as evidence that a usable part
  outline exists, not as a defect discriminator.
- VRM02 now emits `SEATING?` only when all slot-specific advisory gates agree:
  non-empty probability `>=0.90`, calibrated transverse displacement
  `>=1.00 mm`, auxiliary confidence `>=0.25`, mask area `>=21000 px`, and
  PatchCore `>=0.80`. VRM01's gate now uses `1 - P(EMPTY) >=0.90` instead of a
  single CORRECT-class confidence, preventing the same physical seating defect
  from flickering when the unverified state classifier alternates between
  CORRECT and ROTATED.
- Final GPU runs produced exactly `vrm_01 SEATING?` and `vrm_02 SEATING?` in
  all three controlled captures. VRM01 transverse residual was
  `0.784–0.840 mm`; VRM02 was `1.115–1.191 mm`. The difficult verified-normal
  regression `151315` produced zero candidates, with VRM01/02 residuals of
  `0.035/0.091 mm`. Fifty hybrid tests and ten VRM dataset/training tests passed
  (`60 passed` total), along with Python and JSON syntax checks.
- Both rules remain `ADVISORY_ONLY`, and the board result remains fail-safe
  `UNKNOWN`. This is repeatability evidence from one physical VRM02 lip setup,
  not support for automatic FAIL or generalization to VRM03–05. Independent
  flat placements and the opposite lip direction remain to be captured. No
  robot or conveyor motion command was sent; S22 overview was only temporarily
  released and restored during still capture.

## 2026-09-04 — PM01 fixed centroid calibration and VRM01 lip-seating evidence

- The user confirmed the current `power_module_01` placement as acceptable and
  `vrm_01` as physically defective because one edge was resting on the socket
  lip. S22 flash-OFF capture `173934` was 4000×3000 at 69 mm equivalent focal
  length, with board rectangularity `0.909` and registration score `0.9861`.
- Before calibration, auxiliary geometry reported the acceptable PM01 at
  `1.273 mm` from the nominal centre, while VRM state v6 called the lip-seated
  VRM01 `CORRECT 0.9044`. Its in-plane axis error was 0 degrees, so a direction
  classifier cannot describe this out-of-plane seating condition. PatchCore
  nevertheless scored it `1.000` and localized response around the socket edge.
- Added a fixed per-slot segmentation-centroid correction after the existing
  common frame-bias correction. PM01 uses `[0.7629, 0.0062] mm`, measured from
  the median of five unchanged user-verified normal captures (`101656–101935`).
  VRM01 uses `[-0.5634, 0.6974] mm`, measured from six verified-normal captures.
  Neither the CAD slot coordinate nor the existing `0.75 mm` CAD-plus-measurement
  tolerance was widened.
- The accepted current PM01 now has a `0.584 mm` residual and no operator
  candidate. The historical controlled PM01 displacement `144923` remains
  `POSE?` at `2.411 mm` after the same correction, demonstrating that the
  calibration removes fixed centroid bias without normalizing away a real
  slot-relative displacement.
- A PatchCore-only VRM seating threshold was rejected: additional normal runs
  produced a normal VRM01 maximum score of `0.7680`, overlapping the repeated
  lip-seating range `0.7293–1.000`. A VRM01-only corroborated `SEATING?` rule now
  requires raw CORRECT-state support `>=0.80`, calibrated transverse displacement
  `>=0.70 mm`, auxiliary outline confidence `>=0.25`, mask area `>=21800 px`, and
  PatchCore score `>=0.70` simultaneously.
- Current capture `173934` produced only `vrm_01 SEATING?` with
  `0.774 mm / 22207.5 px / 1.000`; earlier repeat `172955` reproduced it at
  `0.741 mm / 22032.5 px / 0.801`. The hardest normal regression `151315` stayed
  at zero candidates despite PatchCore `0.7680`, because calibrated transverse
  error was only `0.035 mm` and mask area `21510 px`.
- This remains `ADVISORY_ONLY`; the board verdict remains fail-safe `UNKNOWN`.
  Evidence covers one physical lip-seating setup on VRM01 and is not generalized
  to other slots, seating modes, dates, or lighting. Fifty-five related tests plus
  Python/JSON syntax checks passed. No robot or conveyor motion command was sent;
  only the S22 overview was temporarily released and restored for capture.

## 2026-09-04 — VRM v6 독립 VRM03 누락 블라인드 검증

- v6 배포 이후 학습에 사용하지 않은 새 물리 장면에서 `vrm_03`만 제거하고,
  VRM04와 PM02는 정상 위치로 복구했다. S22 3.5배 망원·플래시 OFF 촬영
  `171123`, `171205`, `171554`는 모두 4000×3000/환산 69 mm였고 기판
  직사각형도 `0.908–0.909`, 통합 정합 score `0.9865–0.9868`이었다.
- 현재 운영 v6을 고정 슬롯 통합 경로로 블라인드 검사한 결과 세 장 모두
  `vrm_03=EMPTY`를 confidence `0.9609–0.9867`로 검출해 `MISSING?`을
  재현했다. 나머지 VRM 12/12는 모두 `CORRECT`였고 최저 confidence는
  `0.9790`으로 운영 기준 `0.90`을 통과했다.
- 대표 `171554`에는 부품별 PatchCore까지 실행했다. VRM03 surface score
  `1.0`과 빈 소켓에 국소화된 heatmap이 상태 분류기의 누락 증거와
  일치했다. 결과는
  `runtime/inspection/hybrid_vrm_v6_blind_empty03_full_171554/20260904_171918_011151/`
  에 저장했다.
- PM01 geometry는 세 프레임에서 중심 오차 `1.230–1.367 mm`로 허용치
  `0.75 mm`를 넘었으며 세 번째 화면에만 보조 `POSE?` 후보가 표시됐다.
  이는 이번 VRM 판정과 분리하며 다음 제어 장면 전에 PM01을 중앙으로
  복구한다. 이 누락 장면은 v6 학습 데이터에 추가하지 않고 독립 holdout으로
  유지했다.
- 모델·threshold·융합 권한은 변경하지 않았다. VRM v6은 계속
  `ADVISORY_ONLY`, 전체 결과는 필수 provider 검증이 끝날 때까지
  `UNKNOWN`이다. 로봇·컨베이어 실제 명령은 전송하지 않았고 세 촬영에서
  S22 overview만 일시 해제·복구했다.

## 2026-09-04 — VRM04 회전 데이터·라벨 감사 및 v6 운영 후보 교체

- 사용자가 다른 부품을 정상으로 복구한 뒤 왼쪽 VRM 열의 위에서 두 번째
  `vrm_04`만 반시계 방향 90도로 회전했다. S22 3.5배 망원·플래시 OFF로
  `163721`, `163814`, `163931` 세 장을 촬영했으며 모두 4000×3000/환산
  69 mm, 기판 직사각형도 `0.903–0.909`였다. 영상과 crop preview를 직접
  확인해 반복 세 장을 단일 물리 scene `vrm04_90ccw_20260904_1637`로
  보관했다.
- 교체 전 운영 VRM 모델은 이 VRM04 회전을 세 장 모두 확정하지 못했다.
  raw 결과는 `CORRECT 0.545`, `CORRECT 0.724`, `ROTATED 0.429` 수준이었다.
  함께 반복된 `power_module_02 POSE?`는 모델 오검이 아니라 실제 중심 이탈
  약 `1.70 mm`가 허용치 `0.75 mm`를 넘은 물리 상태였다.
- 새 scene을 포함한 v5 후보는 물리 scene holdout accuracy `0.90`, macro
  recall `0.9444`, EMPTY/CORRECT/ROTATED recall `1.0/0.8333/1.0`이었으나,
  과거 `CORRECT` 자료 하나를 회전으로 분류했다. 원본·preview·Unity 슬롯
  방향을 재감사한 결과 그 자료는 모델 오검이 아니라
  `vrm_state_ambient_01`의 VRM04/VRM05 라벨이 서로 뒤바뀐 데이터 오류였다.
- 원본 이미지는 보존하고 ambient-01을 실제 모습대로
  `vrm_01=EMPTY`, `vrm_05=ROTATED`, `vrm_02/03/04=CORRECT`로 수정했다.
  두 crop의 class 위치와 manifest를 함께 바로잡고
  `POST_CAPTURE_VISUAL_AUDIT_CORRECTED` 근거 및 이전 라벨을 기록한 뒤
  preview를 재생성해 재확인했다. 따라서 구 운영 v2는 잘못된 라벨로 학습된
  모델로 분류해
  `slot_classifier/models/vrm_state_v2_pre_label_audit_20260904/`에 백업했다.
- 수정 데이터와 VRM02·04·05의 독립 90도 scene으로 v6 후보를 35 epoch
  재학습했다. holdout accuracy와 macro recall은 모두 `1.0`, 클래스별
  recall도 `1.0/1.0/1.0`이었다. 다만 holdout의 최소 정답 확률은
  `0.6707`이라 자동 산출 문턱을 채택하지 않고 fail-safe 운영 문턱을
  `0.90`으로 유지했다.
- 동일한 실제 통합 검사 경로의 스테이징 검증에서 독립 정상 3장
  (`151315/151404/151508`)의 VRM 15/15를 모두 `CORRECT`로 판정했고 후보는
  0건, 최저 신뢰도는 `0.9715`였다. VRM04 90도 장면 3/3은 모두
  `ROTATED 0.9999+`였고 다른 VRM 오검은 없었다. 동일 crop 경로의 VRM02와
  VRM05 90도 장면도 각각 3/3 검출했다.
- 검증 후 v6을 기본 `models/vrm_state.*`로 교체했다. 기본 운영 경로 재검사도
  정상 `151508`에서 후보 0건, 불량 `163931`에서 `vrm_04 DIR?`를
  `0.9999`로 재현했다. 모델은 여전히 `ADVISORY_ONLY`, `validated=false`이며
  낮은 신뢰도는 PASS가 아닌 UNKNOWN으로 남는다. 검사 계약은 구조나 융합
  권한을 바꾸지 않고 현재 provider 표기만 `VRM_STATE_V6_ADVISORY`로 맞췄다.
  관련 테스트 `50 passed`를 확인했다. 로봇·컨베이어 실제 명령은 전송하지
  않았고 촬영 중 S22 overview만 일시 해제·복구했다.

## 2026-09-04 — VRM02 90도 독립 장면 추가 및 v4 후보 보류

- 사용자가 `VRM02`를 슬롯 중앙에서 시계 방향 90도로 회전한 장면을 S22
  3.5배 망원·플래시 OFF로 세 번 촬영했다(`160933`, `161049`, `161133`).
  모두 4000×3000/환산 69 mm였고 기판 직사각형도는 `0.905–0.906`이었다.
- 영상과 dataset preview를 직접 확인해 왼쪽 VRM 열의 아래에서 두 번째
  `vrm_02`만 `rotated`, 나머지 네 VRM은 `correct`로 보관했다. 반복 3장은
  같은 물리 배치이므로 하나의 scene `vrm02_90cw_20260904_1609`로 기록했다.
- 사용자가 이전 혼합 장면을 완전히 복구하지 않아 GPU01 180도와 PM01 위치
  이탈도 영상에 남아 있었다. 고정 슬롯 검사 최신 프레임은 이 둘과 VRM02
  회전을 후보로 냈다. 다른 부품의 상태는 VRM 전용 crop 학습에는 포함되지
  않지만, 이 장면을 전체 정상 회귀 자료로는 사용하지 않는다.
- 기존 운영 VRM 모델은 세 프레임의 VRM02를 raw `ROTATED` 방향으로 보았으나
  runtime confidence가 `0.595`, `0.522`, `0.982`로 변동해 1/3만 현재
  `0.90` 확정 기준을 통과했다.
- 운영 모델을 덮어쓰지 않고 VRM05·VRM02의 두 새 90도 scene을 포함한
  `vrm_state_v4_candidate`를 별도로 35 epoch 학습했다. 물리 scene holdout
  accuracy `0.90`, macro recall `0.8333`, EMPTY/CORRECT recall `1.0`, ROTATED
  recall `0.50`이었다.
- v4는 새 VRM05 3장과 VRM02 3장, 직전 독립 정상 3장의 VRM 15개를 모두
  맞혔다. 그러나 기존 독립 holdout의 슬롯 밖 회전 `vrm_03`을
  `CORRECT 0.809`로 놓쳐 운영 모델로 배포하지 않았다. 후보는 계속
  `ADVISORY_ONLY`, 운영 모델·threshold·융합 계약은 변경하지 않았다.
- 다음 데이터는 다른 슬롯의 중앙 90도 회전과 슬롯 이탈을 동반한 회전 장면을
  각각 별도 물리 scene으로 수집해야 한다. 로봇·컨베이어 실제 명령은 전송하지
  않았고 촬영 중 S22 overview만 일시 해제·복구했다.

## 2026-09-04 — 비-SMD 보완 혼합 시험 및 VRM 90도 후보 모델 보류

- 정상 복구 장면 뒤 `GPU01 180도`, `HBM02 누락`, `VRM05 90도`,
  `Inductor02 누락`을 구성했다. Power Module은 90도 안착이 불가능해 사용자가
  한 부품을 기존 슬롯보다 위로 이동했다. 실제 영상과 Unity 파생 슬롯 매핑을
  대조한 결과 이동한 하단 가로 부품은 `power_module_03`이며,
  `power_module_04`는 상단 가로 부품으로 정상 위치였다. 좌측 세로
  `power_module_01`도 직전 정상 장면보다 실제 중심이 이동해 있었다.
- S22 3.5배 망원·플래시 OFF로 `153507`, `153559`, `153718` 세 장을
  촬영했다. 모두 4000×3000/환산 69 mm, 기판 직사각형도 `0.905–0.908`,
  정합 score `0.8824–0.8860`으로 유효 하한 `0.82`를 통과했다.
- 고정 슬롯·방향·보조 외곽 검사는 3/3 모두 `GPU01:DIR?`,
  `HBM02:MISSING?`, `Inductor02:MISSING?`, `Power Module01:POSE?`,
  `Power Module03:POSE?`를 반복 검출했다. PM03 중심 오차는 약
  `3.25–3.30 mm`, PM01은 약 `2.71–2.72 mm`였고 PM04는
  `0.12–0.34 mm`로 정상 범위였다. 기존 운영 VRM 상태 모델은 VRM05 90도를
  낮은 신뢰도의 `EMPTY/CORRECT`로 보아 후보를 만들지 못했다.
- 최신 `153718` 전체 GPU 검사 결과는
  `runtime/inspection/hybrid_nonsmd_complement_full_153718/20260904_154645_057770/`
  에 저장했다. VRM05 PatchCore score는 `0.8304`로 정상 복구 장면 최대
  `0.5663`보다 높았지만 제어 불량 검증 threshold가 없어 PatchCore 단독
  판정에는 사용하지 않았다.
- 현재 VRM05 90도 장면의 반복 3장을 같은 물리 scene
  `vrm05_90deg_20260904_1535`로 `vrm_state_v2` 데이터셋에 추가했다. 같은
  배치를 반복 촬영한 세 장을 서로 독립 scene처럼 부풀리지 않았으며 preview로
  VRM05=`rotated`, 나머지 VRM=`correct` crop을 확인했다.
- 운영 모델을 덮어쓰지 않고 `vrm_state_v3_candidate`를 별도로 35 epoch
  학습했다. 후보는 이번 VRM05 90도 3/3과 직전 독립 정상 3장 15/15를 맞혔지만,
  물리 scene holdout은 accuracy `0.70`, macro recall `0.7222`,
  CORRECT recall `0.6667`, ROTATED recall `0.50`에 그쳤다. 더 엄격한
  confidence `0.80` 적용 시 기존 holdout 회전 2개를 모두 확정하지 못하고
  정상 VRM 하나를 `ROTATED 0.977`로 오검했다.
- 따라서 후보 모델은 배포하지 않았고 운영 `vrm_state` 모델·threshold·융합
  권한은 그대로 유지했다. 다음 학습에는 서로 다른 슬롯에서 만든 독립적인
  90도 회전 물리 장면이 추가로 필요하다. 모든 모델은 계속
  `ADVISORY_ONLY`, 최종 상태는 `UNKNOWN`이며 로봇·컨베이어 실제 명령은
  전송하지 않았다. 촬영 중 S22 overview만 일시 해제·복구했다.

## 2026-09-04 — 비-SMD 혼합 불량 정상 복구 3회 검증

- 직전 혼합 시험의 `hbm_04`, `inductor_01`, `power_module_01`, `vrm_03`을
  모두 정상 위치·방향으로 복구하고 SMD를 포함한 나머지 부품도 그대로 정상
  유지했다.
- S22 3.5배 망원·플래시 OFF로 `151315`, `151404`, `151508` 세 장을 새로
  촬영했다. 모두 4000×3000/환산 69 mm였고 기판 직사각형도는
  `0.909–0.910`이었다.
- 고정 슬롯 존재·방향·보조 외곽 검사를 세 장에 각각 실행한 결과 3/3 모두
  advisory 후보 0개였다. 정합 score는 `0.9865–0.9888`, YOLO 보조 provider
  error도 0개였다.
- 최신 `151508`은 부품별 PatchCore까지 RTX GPU에서 전체 재검사했다. 정합
  score `0.9876`, 후보 0개, PatchCore provider error 0개였으며 빈 Heatmap과
  무색 오버레이를 직접 확인했다. 결과는
  `runtime/inspection/hybrid_nonsmd_recovery_full_151508/20260904_152856_272283/`
  에 저장했다.
- 이번 작업에서는 코드·모델·threshold·판정 권한을 변경하지 않았다. 필수
  provider가 아직 `ADVISORY_ONLY`이므로 최종 결과는 계속 `UNKNOWN`이며,
  정상 장면에 오류 후보가 있다는 뜻은 아니다. 로봇·컨베이어 실제 명령은
  전송하지 않았고 촬영 중 S22 overview만 일시 해제·복구했다.

## 2026-09-04 — 비-SMD 누락·역방향·회전·위치 이탈 혼합 검증

- SMD 5개와 그 외 미조작 부품은 정상으로 둔 채, 한 장면에 네 제어 불량을
  동시에 구성했다: `vrm_03` 누락, `hbm_04` 180도 역방향,
  `inductor_01` 90도 회전, `power_module_01` 슬롯 밖 측면 이탈.
- S22 3.5배 망원·플래시 OFF로 `144923`, `145046`, `145130` 세 번
  촬영했다. 원본은 모두 4000×3000/환산 69 mm, 보드 ROI는 1600×1266,
  기판 직사각형도는 `0.908–0.909`였고 통합 검사 정합 score는
  `0.9061–0.9266`으로 유효 기준 `0.82`를 통과했다.
- 세 프레임 모두 HBM04 흰색 기준점이 우측 상단에서 검출되어
  `DIR?` confidence `1.0`, Inductor01 검정 방향 마커가 기준에서 벗어나
  `DIR?` confidence `0.295–0.329`, VRM03 상태 분류기가 `EMPTY`
  confidence `0.951–0.997`로 `MISSING?`을 반복 검출했다.
- Power Module01은 실제로 존재하지만 중심이 `3.163–3.219 mm` 이탈했다.
  보조 외곽은 confidence `0.598–0.606`, mask 면적
  `98,384–98,821 px²`로 긴 노란 몸체를 반복 검출했으나, 고정 슬롯
  분류기는 노출된 슬롯 중심 때문에 낮은 신뢰도의 `EMPTY 0.524–0.762`를
  냈다. 이 상태에서 `MISSING?`가 `POSE?`를 덮던 원인명 오류를 수정했다.
- Power Module에만 한정해 `LOW_CONFIDENCE EMPTY`, pose FAIL, 외곽
  confidence `>=0.55`, 중심 오차 `>=2.0 mm`, mask 면적 `>=90,000 px²`가
  모두 성립할 때 실제 몸체 존재 증거로 보고 화면의 `MISSING?` 원인만
  억제한다. 확신도 높은 EMPTY, 외곽이 없거나 작은 경우는 계속
  `MISSING?`이며 판정 provider와 원시 evidence는 변경하지 않는다.
- YOLO 보조 외곽과 부품별 PatchCore를 RTX GPU에서 포함한 전체 검사 결과
  3/3 모두 정확히 `HBM04:DIR?`, `Inductor01:DIR?`,
  `Power Module01:POSE?`, `VRM03:MISSING?` 네 후보만 나왔다. 대표 화면은
  `runtime/inspection/hybrid_nonsmd_mixed_full_gpu_145130/20260904_150337_441684/`
  이며 나머지 반복 결과는 `hybrid_nonsmd_mixed_full_gpu_144923` 및
  `hybrid_nonsmd_mixed_full_gpu_145046` 아래에 저장했다.
- 직전 정상 보드 `142508`을 같은 GPU 경로로 재검사해 후보 0개와 provider
  error 0개를 확인했다. 결과는
  `runtime/inspection/hybrid_nonsmd_mixed_normal_regression/20260904_150441_933238/`
  이다. Python compile과 회귀 테스트 `42 passed`도 통과했다.
- 이 보정은 원인 표시만 다듬은 `ADVISORY_ONLY` 규칙이며 자동 FAIL 권한을
  추가하지 않았다. 필수 provider 검증이 끝나지 않아 최종 상태는 계약대로
  `UNKNOWN`이다. 로봇·컨베이어 실제 명령은 전송하지 않았고, 촬영 중 S22
  overview만 일시 해제·복구했다.

## 2026-09-04 — SMD 누락·회전·턱걸림 혼합 불량 동시 검증

- 정상 복구 검증 뒤 한 기판에 세 제어 불량을 동시에 구성했다: 우측 세로열
  맨 위 `smd_capacitor_05` 누락, 가운데 `smd_capacitor_03` 90도 회전,
  오른쪽 아래 가로형 `smd_capacitor_01` 소켓 턱걸림. SMD02·04와 나머지
  부품은 정상으로 유지했다.
- S22 3.5배 망원·플래시 OFF로 세 번 촬영했다(`143229`, `143333`,
  `143450`). 모두 4000×3000/환산 69 mm, 기판 직사각형도 `0.909`, 정합
  score `0.9870–0.9874`였다.
- PatchCore 제외 고정 슬롯 검사에서 3/3 모두 정확히 세 후보만 나왔다.
  SMD05는 `EMPTY` confidence `0.9999998–1.000`으로 `MISSING?`, SMD03은
  장축 각도 오차 `90°`로 `POSE?`, SMD01은 횡방향 이탈
  `1.259–1.338 mm`로 `POSE?`였다.
- 전체 PatchCore 검사에서 SMD03 score는 `0.504–0.608`, 빈 SMD05는
  `0.474–0.595`로 해당 슬롯 Heatmap이 반복됐다. SMD01은 이전 턱걸림
  장면의 `0.399–0.486`보다 낮은 `0.155–0.214`였지만 Heatmap은 여전히
  들린 부품·소켓 턱에 국소화됐다. 정상 SMD01 8장의 최대 score는
  `0.0038`이었다.
- 서로 다른 턱걸림 배치를 모두 포함하도록 SMD01 전용 PatchCore 하한만
  `0.25`에서 `0.10`으로 조정했다. presence `>=0.90`, 외곽 confidence
  `>=0.20`, mask 면적 `>=4400 px²` 조건은 그대로라 PatchCore 단독이나
  면적 단독으로는 후보를 만들 수 없다.
- 새 융합 규칙을 세 장에 적용한 결과 모두 정확히
  `SMD01:SEATING?`, `SMD03:POSE?`, `SMD05:MISSING?` 세 후보로 일치했다.
  가장 낮은 SMD01 score 장면 `143333`의 전체 재검사 리포트는
  `runtime/inspection/hybrid_smd_mixed_verified/20260904_144104_172098/`에
  저장했다. 직전 정상 프레임 `142508`도 새 기준으로 재검사해 후보 0개를
  확인했으며 결과는
  `runtime/inspection/hybrid_smd_mixed_normal_regression/20260904_144223_393938/`
  이다.
- Python compile과 회귀 테스트 `40 passed`를 통과했다. 모든 후보는 계속
  `ADVISORY_ONLY`, 최종 상태는 `UNKNOWN`이며 로봇·컨베이어 실제 명령은
  전송하지 않았다. 촬영 중 S22 overview만 일시 해제·복구했다.

## 2026-09-04 — 전체 SMD 정상 복구 3회 회귀 검증

- 턱걸림 시험을 끝낸 `smd_capacitor_01`을 포함해 SMD 5개를 모두 정상
  안착시킨 뒤 S22 3.5배 망원·플래시 OFF로 세 번 촬영했다(`142332`,
  `142427`, `142508`). 모두 4000×3000/환산 69 mm, 기판 직사각형도
  `0.909`, 정합 score `0.9875–0.9879`였다.
- 고정 슬롯 존재·geometry와 부품별 PatchCore를 모두 포함한 전체 검사를
  세 장에 각각 수행했다. 3/3 모두 advisory 후보 0개였고 SMD 5개 PatchCore
  score도 모든 프레임에서 `0.000`이었다.
- 정상 장면에서도 투영 mask 면적은 촬영별로 변동했다. 예를 들어 SMD01은
  최대 `4494 px²`, SMD04는 최대 `4687.5 px²`였지만 각 슬롯 규칙이 독립
  presence·외곽·mask·PatchCore의 동시 충족을 요구하므로 면적 하나만으로
  오검되지 않았다. SMD 횡방향 이탈도 모두 `0.612 mm` 이하로 0.84 mm
  표시 기준 안이었다.
- 최신 결과는
  `runtime/inspection/hybrid_all_smd_recovery_full_142508/20260904_142746_328777/`
  에 저장했으며 화면에서 빈 후보 Heatmap과 무색 오버레이를 확인했다.
- 이번 회귀 검증에서는 코드·threshold·판정 권한을 변경하지 않았다. 최종
  `UNKNOWN`은 필수 provider가 아직 `ADVISORY_ONLY`이기 때문이며 정상 장면에
  불량 후보가 있다는 의미가 아니다. 로봇·컨베이어 실제 명령은 전송하지
  않았고 촬영 중 S22 overview만 일시 해제·복구했다.

## 2026-09-04 — SMD 01 턱걸림 안착 불량 슬롯별 확장

- SMD05를 정상 복원하고 오른쪽 아래 가로형 `smd_capacitor_01`을 소켓 턱에
  걸쳐 기울인 제어 불량을 S22 3.5배 망원·플래시 OFF로 세 번 촬영했다
  (`140754`, `140856`, `141001`). 모두 4000×3000/환산 69 mm, 기판
  직사각형도 `0.908–0.909`, 정합 score `0.9865–0.9874`였다.
- 기존 횡방향 geometry가 세 장 모두 SMD01만 `POSE?`로 검출했다. 횡방향
  절대 이탈은 `0.846–0.870 mm >= 0.840 mm`, 전체 2D 중심 오차는
  `1.089–1.176 mm`였다. 따라서 이 배치는 높이 방향 턱걸림이면서 평면
  위치도 허용 범위를 벗어난 불량이다.
- 세 장의 독립 presence는 `PRESENT 0.9592–0.9905`, 외곽 confidence는
  `0.264–0.348`, mask 면적은 `4574–4644 px²`, PatchCore score는
  `0.399–0.486`이었다. 전체 Heatmap은 SMD01의 들린 몸체와 노출된 소켓
  경계에 국소화됐다.
- 검증 정상 5장을 현재 코드로 비교한 SMD01 외곽 confidence 최대는 `0.311`,
  mask 면적 최대는 `4215 px²`, PatchCore 최대는 `0.0038`, 횡방향 이탈
  최대는 `0.263 mm`였다. 이를 근거로 SMD01 전용 안착 표시를 presence
  `>=0.90`, 외곽 confidence `>=0.20`, mask 면적 `>=4400 px²`, PatchCore
  `>=0.25`의 네 조건 교차로 추가했다.
- 불량 중 PatchCore가 가장 낮은 `140754` 전체 재검사 결과 후보는 SMD01
  하나였고 주 원인은 `SEATING?`, 보조 코드는 `POSE?`였다. 정상 mask 최대
  프레임 `101935`은 SMD01 값 `0.273 / 4215 px² / 0.000`, 전체 후보 0개였다.
  결과는
  `runtime/inspection/hybrid_smd01_lip_seating_verified/20260904_141847_556412/`
  및
  `runtime/inspection/hybrid_smd01_lip_worst_normal_regression/20260904_141942_759205/`
  에 저장했다.
- Python compile과 회귀 테스트 `40 passed`를 통과했다. 원시 `POSE?` 근거를
  보존하면서 표시 우선 원인만 `SEATING?`으로 통일했다. 모든 근거는 계속
  `ADVISORY_ONLY`, 최종 상태는 `UNKNOWN`이며 로봇·컨베이어 실제 명령은
  전송하지 않았다. 촬영 중 S22 overview만 일시 해제·복구했다.

## 2026-09-04 — SMD 05 턱걸림·기울어짐 안착 불량 슬롯별 확장

- SMD02를 정상 복원하고 우측 세로열 맨 위 `smd_capacitor_05`를 소켓 턱에
  걸쳐 기울인 제어 불량을 S22 3.5배 망원·플래시 OFF로 세 번 촬영했다
  (`134552`, `134812`, `134919`). 모두 4000×3000/환산 69 mm였고 통합 검사
  정합 score는 `0.9861–0.9869`였다.
- 세 장 모두 독립 presence는 `PRESENT 0.9966–0.9997`, 보조 외곽 confidence는
  `0.547–0.613`, 투영 mask 면적은 `4811.0–4845.5 px²`, PatchCore score는
  `0.341–0.368`이었다. Heatmap은 SMD05의 들린 몸체·소켓 턱 가장자리에
  반복해서 국소화됐다. 보정 2D 중심 오차는 `0.515–0.556 mm`로 기존
  0.75 mm 평면 pose 기준만으로는 이 높이 방향 불량을 구분할 수 없었다.
- 같은 조건의 검증 정상 5장을 현재 코드로 재계측했을 때 SMD05 외곽
  confidence 최대는 `0.384`, mask 면적 최대는 `4438 px²`, PatchCore는 모두
  `0.000`이었다. 이를 근거로 SMD05 전용 규칙을 presence `>=0.90`, 외곽
  confidence `>=0.45`, mask 면적 `>=4600 px²`, PatchCore `>=0.25`의 네 조건
  교차로 추가했다.
- 가장 약한 불량 프레임 `134812`을 새 코드로 전체 재검사한 결과 유일한 후보가
  `smd_capacitor_05:SEATING?`이었고, 정상 최대 면적 프레임 `101724`은
  SMD05 값 `0.384 / 4438 px² / 0.000`과 전체 후보 0개를 유지했다. 불량
  리포트는
  `runtime/inspection/hybrid_smd05_lip_seating_verified/20260904_135902_468524/`,
  정상 경계 회귀 리포트는
  `runtime/inspection/hybrid_smd05_lip_worst_normal_regression/20260904_140210_168447/`
  에 저장했다.
- Python compile과 회귀 테스트 `38 passed`를 통과했다. 규칙은 실측된 SMD05에만
  적용하고 미검증 SMD01에는 일반화하지 않았다. 결과는 계속
  `ADVISORY_ONLY`, 최종 `UNKNOWN`이며 로봇·컨베이어 실제 명령은 전송하지
  않았다. 촬영 중 S22 overview만 일시 해제·복구했다.

## 2026-09-04 — SMD 02 턱걸림 안착 불량 슬롯별 확장

- SMD04를 정상 복원하고 우측 세로열 맨 아래 `smd_capacitor_02`를 소켓 턱에
  걸쳐 기울인 제어 불량을 플래시 OFF로 세 번 촬영했다(`132929`, `133042`,
  `133138`). 모두 4000×3000/환산 69 mm, 기판 직사각형도 `0.909–0.910`,
  정합 score `0.9869–0.9873`이었다.
- 기존 평면 geometry는 횡방향 이탈이 `0.791–0.874 mm`로 0.84 mm 표시
  경계에 걸려 세 장 중 한 장만 `POSE?`를 표시했다. 반면 SMD02 mask 면적은
  세 장 모두 `4623.5–4667.0 px²`, PatchCore score는
  `0.305–0.404`, 독립 presence는 `PRESENT >=0.9983`으로 반복됐다. Heatmap도
  SMD02의 들린 몸체와 노출된 소켓 턱에 국소화됐다.
- 검증 정상 5장의 SMD02 mask 면적 최대는 `4222.5 px²`였고 PatchCore는 모두
  `0.000`이었다. 이 실측으로 SMD02 전용 턱걸림 규칙을 추가했다: presence
  `>=0.90`, 외곽 confidence `>=0.20`, mask 면적 `>=4500 px²`, PatchCore
  `>=0.25`를 모두 만족해야 `SEATING?` 후보를 표시한다.
- 새 융합 함수를 세 불량 리포트에 재생했을 때 3/3 모두 주 후보가
  `smd_capacitor_02:SEATING?`으로 일치했다. 세 번째 장의 큰 횡이탈 `POSE?`
  근거도 JSON에는 함께 보존된다. 이전에 무표시였던 `133042` 전체 재검사 화면은
  `runtime/inspection/hybrid_smd02_lip_seating_verified/20260904_133903_494206/`
  에 저장했다.
- 정상 중 mask 면적이 가장 컸던 `101656`도 새 코드로 전체 재검사해 후보
  0개를 확인했다. Python compile과 회귀 테스트 `36 passed`를 통과했다.
- 규칙은 실측된 SMD02와 SMD04에만 독립적으로 적용하며 나머지 SMD 슬롯에는
  일반화하지 않았다. 계속 `ADVISORY_ONLY`, 최종 `UNKNOWN` 및 fail-safe 계약을
  유지한다. 촬영 중 S22 overview만 일시 해제·복구했으며 로봇·컨베이어 실제
  명령은 전송하지 않았다.

## 2026-09-04 — SMD 04 턱걸림·기울어짐 안착 불량 검출

- 사용자가 `smd_capacitor_04`는 슬롯 안에서 단순히 치우친 정상 상태가 아니라
  소켓 턱에 걸려 높이가 들리고 기울어진 실제 제어 불량이라고 정답을 확정했다.
  따라서 해당 장면(`125908`, `125954`, `130034`)은 정상 데이터에 포함하지 않고
  `SEATING` 불량으로 보존했다.
- 이 불량은 보정 후 중심 오차가 `0.523–0.602 mm`라 기존 0.75 mm 평면 pose
  기준을 통과했다. 그러나 세 장 모두 독립 presence는 `PRESENT >=0.9986`,
  segmentation 외곽 confidence는 `0.710–0.726`, 투영 mask 면적은
  `4809.5–4865.5 px²`, SMD PatchCore score는 `0.188–0.273`으로 같은
  SMD04 슬롯에서 반복됐다.
- 검증된 정상 5장 전체 SMD의 외곽 confidence 최대는 `0.474`였고, SMD04만의
  정상 외곽 confidence 최대는 `0.298`, mask 면적 최대는 `4490 px²`,
  PatchCore 최대는 `0.146`이었다. 직전 정상 복귀 장면은 각각 `0.261`,
  `4416 px²`, `0.000`이었다.
- 기존의 `약한 외곽 + PatchCore` SMD 들림 규칙은 그대로 유지하고, 실측이
  확보된 SMD04에만 두 번째 교차 근거를 추가했다. presence `>=0.90`, 외곽
  confidence `>=0.65`, mask 면적 `>=4700 px²`, PatchCore `>=0.17`을 모두
  만족해야 `SEATING?` 후보를 표시한다. `mask_area_px`와
  `normalized_slot_distance`도 pose evidence에 기록한다.
- 수정 후 불량 세 장 모두 다른 후보 없이 정확히
  `smd_capacitor_04:SEATING?` 하나였으며 후보 게이트 Heatmap도 SMD04의 턱·그림자
  경계에만 나타났다. 정상 복귀 사진 재검사는 후보 0개였다. Python compile과
  회귀 테스트 `34 passed`를 통과했다.
- 이 규칙은 SMD04·같은 촬영 조건에서만 검증됐으므로 다른 SMD 슬롯으로
  일반화하지 않았고 계속 `ADVISORY_ONLY`다. 최종 상태 `UNKNOWN`과 fail-safe
  융합 계약은 그대로이며, 로봇·컨베이어 실제 명령은 전송하지 않았다.

## 2026-09-04 — SMD 04 정상 복귀 반복 검증

- 사용자가 `smd_capacitor_04`를 슬롯 안에 완전히 다시 안착시킨 상태를 S22
  3.5배 망원·플래시 OFF로 세 번 독립 촬영했다(`121052`, `121150`,
  `121232`). 세 원본은 모두 4000×3000, 환산 초점거리 69 mm였고 기판
  직사각형도는 `0.908–0.909`였다.
- 세 장 모두 존재 분류 결과는 `PRESENT` confidence
  `0.9981–0.9987`, SMD04 횡방향 절대 이탈은 `0.122–0.193 mm`, 보조 pose
  상태는 `PASS`였고 advisory 후보는 0개였다. 직전 오른쪽 반안착 불량의
  횡방향 이탈 `0.857–0.900 mm`와 정상 복귀값이 반복 측정에서 분리됐다.
- 최신 사진에 부품별 PatchCore까지 포함한 전체 통합 검사를 다시 수행했다.
  정합 score는 `0.9872`, SMD04 PatchCore score는 `0.000`, 전체 advisory
  후보는 0개였으며 리포트는
  `runtime/inspection/hybrid_smd04_recovery_verified/20260904_121519_840006/`
  에 저장했다.
- 최종 상태 `UNKNOWN`은 이상 후보가 있어서가 아니라 presence·orientation·
  surface 제공자가 아직 계약상 `ADVISORY_ONLY`이기 때문이다. 정상 SMD05의
  원시 장축 편향은 최신 장면에서 `0.790 mm`로 기존 0.75 mm pose 허용치를
  조금 넘었지만, 횡방향은 `0.341 mm`였고 최종 후보로 표시되지 않았다.
- 이번 작업은 기존 threshold나 융합 권한을 변경하지 않은 정상 복귀 검증이다.
  S22 촬영 시 overview만 일시 해제·복구했으며 로봇·컨베이어 실제 명령은
  전송하지 않았다. 반대쪽 횡이탈 및 다른 조명 조건 검증 전까지 SMD 횡방향
  후보는 계속 `ADVISORY_ONLY`로 유지한다.

## 2026-09-04 — SMD 04 횡방향 반안착 표시 분리 검증

- 사용자가 `smd_capacitor_04`를 소켓에서 오른쪽으로 절반가량 벗어나 기울인
  제어 불량을 S22 3.5배 망원·플래시 OFF로 네 번 독립 촬영했다(`114218`,
  `114714`, `114807`, `115741`). 최신 촬영은 4000×3000, 환산 초점거리
  69 mm, 기판 직사각형도 `0.909`, 정합 score `0.987`이었다.
- 기존 전체 중심거리만 사용하면 SMD04 불량의 위치 오차 `0.908–0.926 mm`와
  정상 SMD05의 슬롯별 장축 편향 `0.856–0.890 mm`가 겹쳐, 단순 임계값을
  낮출 경우 정상 SMD05도 `POSE?`로 표시되는 것을 확인했다. 이 임시 기준은
  최종 동작에 남기지 않았다.
- 보조 segmentation 중심 오차를 부품 장축 방향과 그에 수직인 횡방향으로
  분해해 JSON에 각각 기록하도록 변경했다. SMD 위치 후보는 독립 presence가
  `PRESENT >=0.90`, 외곽 confidence `>=0.20`, 횡방향 절대 이탈
  `>=0.84 mm`를 모두 만족할 때만 `POSE?`로 표시한다. 프레임마다 슬롯
  기준을 재정렬하거나 실제 위치 오류를 정규화하지 않으며, 기존 0.75 mm
  원시 pose 상태와 fail-safe 융합은 그대로다.
- 저장된 정상 8장을 새 규칙에 재생했을 때 SMD 후보는 모두 0개였다. 같은
  SMD04 불량 4장은 횡방향 이탈 `0.857–0.900 mm`로 모두 SMD04 하나만
  `POSE?`였다. 최신 전체 GPU 통합 리포트는
  `runtime/inspection/hybrid_smd04_transverse_verified/20260904_120532_114429/`
  이며 정상 SMD05의 횡방향 값 `0.369 mm`는 표시에서 제외됐다.
- 최신 SMD04 PatchCore score는 `0.012`로 이 장면의 근거가 표면 모델이 아닌
  고정 슬롯 횡방향 geometry임을 확인했다. 현 기준은 정상 최대 `0.815 mm`와
  불량 최소 `0.857 mm` 사이의 좁은 실측 간격을 사용하므로 계속
  `ADVISORY_ONLY`다. 좌우 반대·상하 이탈, 다른 날짜와 조명 holdout을 더
  검증하기 전에는 자동 FAIL 권한을 부여하지 않는다.
- 회귀 테스트 `31 passed`, Python compile과 최신 RTX 전체 재추론을 통과했다.
  촬영 중 S22 overview만 일시 해제·복구했으며 로봇·컨베이어 실제 명령은
  전송하지 않았다.

## 2026-09-04 — SMD 03 누락·90도 방향 오류 반복 검증 및 HBM 경계 표시 안정화

- PM02를 정상 위치로 복원하고 `smd_capacitor_03`만 제거한 S22 장면을 세 번
  촬영했다(`s22_inspection_roi_20260904_104918.png`, `105220.png`,
  `105311.png`). 정합 점수는 `0.9878–0.9884`였다.
- 세 번 모두 SMD03 존재 분류 결과는 `EMPTY`, confidence
  `0.99999976–0.99999988`이었고 유일한 누락 후보는 `SMD 03 MISSING?`였다.
  첫 전체 추론의 고정 초과 PatchCore Heatmap도 동일한 빈 슬롯을 국소화했다.
- 마지막 프레임에서 정상 HBM06의 보정 후 중심 오차가 `0.769 mm`로 측정되어
  기존 `0.750 mm` 허용치를 `0.019 mm`만 넘었고, 앞선 두 프레임은
  `0.741/0.718 mm`였다. 이 경계 진동 때문에 정상 HBM06 `POSE?`가 1회
  표시됐다.
- CAD/측정 pose 상태와 원시 JSON은 그대로 보존하고 작업자 오버레이에만 최소
  표시 마진을 추가했다. 고신뢰 보조 pose는 위치가 허용치를 `0.10 mm` 이상
  넘거나, 실제 장축 검사를 수행한 각도가 허용치를 `1.0°` 이상 넘을 때
  `POSE?`로 표시된다. 독립 방향·존재·핀 검사는 영향을 받지 않는다.
- 수정 후 같은 세 장의 후보는 모두 `smd_capacitor_03:MISSING?` 하나로
  일치했다. 하이브리드·핀 회귀 테스트 `29 passed`, Python compile 통과.
  모델 권한은 계속 `ADVISORY_ONLY`, 최종 자동 판정은 fail-safe 계약을
  유지하며 로봇·컨베이어 명령은 전송하지 않았다. 표시 마진 자체는 추가 HBM
  위치 불량 샘플 검증 전까지 생산 판정 임계값이 아니다.
- SMD03을 다시 넣고 슬롯 중심에서 90도 회전한 장면도 세 번 촬영했다
  (`111122`, `111328`, `111413`). 매번 존재 분류기는 `PRESENT` confidence
  `0.9942–0.9964`, 보조 pose는 각도 오차 `90.0°`와 중심 오차
  `1.008–1.054 mm`를 측정했다. 세 결과 모두 다른 후보 없이
  `smd_capacitor_03:POSE?` 하나만 표시됐다.
- 첫 반복의 전체 PatchCore 점수는 `0.629`였으며 고정 초과 Heatmap이 같은
  SMD03 슬롯에 국소화됐다. 현재 SMD 독립 방향 provider는 미보정 상태이므로
  이 결과는 계속 `ADVISORY_ONLY`, 최종 상태는 `UNKNOWN`이다. 로봇 및
  컨베이어 실제 명령은 전송하지 않았다.
- 사용자 실측 정답이 슬롯에서 절반가량 벗어나 들린 `SMD03 안착 불량`인 장면을
  별도 검사했다. 기존 투영 중심/평면 장축은 중심 오차 `0.527–0.575 mm`
  (허용 `0.750 mm`)와 각도 오차 `0°`라 이 높이 방향 결함을 놓쳤다.
- 반면 3회 반복에서 존재 분류는 `PRESENT 0.9989–0.9993`, 보조 YOLO 외곽
  confidence는 `0.195–0.261`, SMD PatchCore는 `0.399–0.448`이었다. 정상
  5장×5개 SMD에서 측정된 PatchCore 최고값은 `0.146`이었다.
- SMD PatchCore 단독 `SURFACE?` 억제는 유지하면서 세 근거를 결합한 표시용
  gate를 추가했다: presence `>=0.90`, auxiliary outline confidence
  `[0.10,0.30)`, PatchCore score `>=0.25`. 조건 충족 시 `SEATING?`으로
  표시하며 확정 불량으로 승격하지 않는다.
- 같은 물리 배치 3회 모두 유일한 후보가 `smd_capacitor_03:SEATING?`이었고
  Heatmap은 노출된 슬롯 가장자리와 들린 부품에 국소화됐다. 테스트
  `32 passed`, Python compile 통과. 이 threshold는 다른 슬롯·방향·날짜·조명
  검증 전까지 `ADVISORY_ONLY`; 로봇·컨베이어 명령은 전송하지 않았다.
- SMD03을 완전 안착 상태로 복원해 세 번 재촬영했다(`113249`, `113457`,
  `113546`). 존재 confidence `0.9989–0.9993`, 중심 오차 `0.620–0.656 mm`,
  PatchCore score `0.000`이었고 세 검사 모두 advisory 후보 0개였다.
- 정상 상태에서도 auxiliary outline confidence가 `0.230–0.268`로 낮았지만
  PatchCore 근거가 없어서 `SEATING?`이 생성되지 않았다. 따라서 외곽 신뢰도
  하나에 의존하지 않고 세 근거를 모두 요구하는 gate의 정상 복구 동작을
  확인했다. 자동 판정 권한과 로봇·컨베이어 상태는 변경하지 않았다.

## 2026-09-04 — SMD/Power Module Heatmap 게이트 누락 수정

- 첨부 결과의 원본인 `s22_inspection_roi_20260903_215217.png`를 명시 입력으로
  재검사했다. `latest` ROI가 `20260904_095032` 사진으로 갱신돼 있었으므로 두
  장면을 섞지 않고 입력 SHA-256까지 확인했다.
- SMD PatchCore를 표면 단독 후보에서 제외하는 안전장치가 anomaly map 생성까지
  차단해, 실제 빈 `SMD 05`가 presence `EMPTY 0.9999996`, PatchCore `0.5842`로
  반응해도 Heatmap이 나오지 않던 문제를 수정했다.
- SMD는 여전히 PatchCore만으로 `SURFACE?` 후보를 만들 수 없다. 대신 presence,
  pose 등 독립 검사에서 슬롯이 지목된 경우에만 해당 SMD PatchCore map을 작업자
  화면에 표시한다. 수정 후 `SMD 05` 누락과 `SMD 03` 17.30도 방향 오류 슬롯에
  Heatmap이 표시됐다.
- 모든 부품에 동일하게 적용하던 pose 표시 confidence 0.80 때문에 내부 위치 FAIL인
  `Power Module 01`이 숨겨지던 문제를 고쳤다. 부품별 표시 조건에 따라 오차
  `1.328 mm > 0.750 mm`, confidence `0.677`인 PM 01을 `POSE?`로 표시하고 해당
  슬롯 Heatmap을 연결했다.
- 현재 Inductor 01은 위치 `0.691 mm`, 방향 마커 오차 `24.50도`, Inductor 02는
  위치 `0.758 mm`, 방향 마커 오차 `12.06도`다. 방향 허용치 50도 안이고 02의
  위치 초과는 `0.008 mm`뿐이어서 표시 노이즈로 처리했으며, 두 모델 추론 자체는
  정상 실행됐다.

### 검증 및 제한

- 하이브리드·핀 회귀 테스트 `24 passed`, Python compile 및 `git diff --check`
  통과. RTX 5070 Ti 재추론 정합 점수는 `0.980`이었다.
- Heatmap은 후보 위치를 설명하는 `ADVISORY_ONLY` 증거이며 확정 불량 확률이 아니다.
  전체 미검증 map은 별도 개발용 산출물로 계속 보존한다.
- 로봇 및 컨베이어 실제 명령은 전송하지 않았다.

## 2026-09-03 — 통합 검사 위치 편향·방향 오탐 및 Heatmap 표시 정리

- 사용자 확인 정답이 `VRM 03`, `SMD Capacitor 05` 누락이고 그 외 부품은
  존재하는 S22 실측 장면을 독립 점검 장면으로 사용했다. 존재 분류기는 두
  누락을 모두 검출했으며 `VRM 02`만 저신뢰 `UNKNOWN`이었다.
- YOLO segmentation 외곽 중심이 최신 장면의 정상 슬롯 전반에서 공통으로 약
  `(x=-0.033, y=-0.897) mm` 치우친 것을 확인했다. 계약의
  `common_projection_bias_max_mm=1.5` 범위 안에서 15개 고신뢰 후보 중앙값만
  공통 보정하고, 개별 슬롯 잔차는 위치 오류 판정에 그대로 남겼다.
- 원형 Inductor segmentation 장축은 방향 근거에서 제외하고 검정 방향 마커
  검사를 유지했다. HBM 방향점 검출에서는 반복되는 측면 핀 열을 제거하고 큰
  원형점을 우선해 정상 `HBM 02` 오탐을 해소했다.
- 정상 `VRM 02`를 `ROTATED 0.808929`로 오분류한 실측 결과를 반영해 VRM 상태
  후보의 최소 confidence를 `0.80`에서 `0.90`으로 높였다. `VRM 02`는 불량 표시
  대신 fail-safe `UNKNOWN`이고, 실제 빈 `VRM 03`은 `EMPTY 0.955024`로 유지된다.
- 전체 미검증 PatchCore 상대 Heatmap은 개발용 파일로 보존하되 작업자 화면은
  존재·위치·방향 검사에서 독립적으로 표시된 후보 슬롯에만 색을 보인다. 따라서
  정상 Inductor/GPU/HBM의 기준 초과 색은 메인 화면에서 제거됐다.
- 최신 화면 후보는 `HBM 04 DIR?`, `SMD 03 POSE?`(각도 오차 `16.34°`),
  `VRM 03/SMD 05 MISSING?` 4개다. HBM 04는 사진에서 큰 흰점이 우측 상단에
  있어 고정 기준인 좌측 하단 정방향과 불일치한다.
- 이후 불량 GPU로 교체한 `s22_inspection_roi_20260903_215217.png`에서 기존
  PatchCore는 정상 GPU `0.693`, 불량 GPU `0.743`으로 겹쳐 단독 임계값을 만들 수
  없었다. 반면 golden-reference 흰색 핀 연속성 검사는 직전 정상 GPU 우측을
  `RECHECK`, 불량 GPU 우측의 3번 핀 누락을 `LEG_PATTERN_DEFECT`로 구분했다.
- 이 독립 핀 근거를 통합 검사의 `GPU PINS?` 후보로 연결했다. 현재 HBM 핀 검사는
  정상 오탐이 남아 연결하지 않았고, GPU 핀 결과 역시 검증 승격 전까지
  `ADVISORY_ONLY`다.

### 검증 및 제한

- 하이브리드·핀 단위 테스트 `21 passed`; RTX 5070 Ti 전체 재추론 완료. 정상
  비교 입력의 정합 점수는 `0.979`, 불량 GPU 입력은 `0.980`이었다.
- 모델은 계속 `ADVISORY_ONLY`, 최종 상태는 fail-safe `UNKNOWN`이다. 별도
  controlled-defect 검증 전에는 자동 PASS/FAIL 권한을 부여하지 않는다.
- 로봇 및 컨베이어 실제 명령은 전송하지 않았다.

## 2026-09-03 — SMD 파지용 소형부품 검출 CHArUco 마커리스 전환

- `calibration/scripts/detect_small_part_dry_run.py`에서 CHArUco 의존성을 제거하고
  `/camera/camera` 기반 RGB-D 마커리스 검출로 바꿨다.
- 검출은 밝기 기반 후보 생성 + HSV 프로파일 + 예상 부품 면적 필터 + depth 샘플링을
  조합해 `part_center_base_mm`, `long_axis_angle_base_deg`를 산출한다.
- 기존 파지 실행 체인(`run_pick_smd_with_gripper_camera → full_pick_place_same_spot`)의
  입력 JSON 형식을 기존과 유지하여 별도 파이프라인 수정 없이 동작할 수 있게 했다.

### 검증 및 제한

- `python3 -m py_compile calibration/scripts/detect_small_part_dry_run.py` 통과.
- 온라인 실기기 검출 확인은 아직 수행하지 않았다.
- 로봇/그리퍼 실제 명령은 미실행 상태이며, 실명령 전환은 사용자 승인 후
  `--execute --confirm-full-cycle` 조건을 통해 수행한다.

## 2026-09-03 — 그리퍼 카메라 기반 SMD 파지 실행기 추가

- `/camera/camera`(color/image_raw/compressed, aligned depth) 기반으로
  `calibration/run_pick_smd_with_gripper_camera.sh`를 추가했다.
- 입력 검출은 기존 `calibration/scripts/detect_small_part_dry_run.py` 기반으로
  유지하고, 결과 JSON을 `calibration/data/smd_gripper_camera_last.json`에 저장한 뒤
  `run_full_pick_place_same_spot.sh`를 호출해 접근/하강/파지/회귀 동작을 한 번에 실행한다.
- `--slot-id`를 지정하면 `vision_assembly/config/physical_board.json`의 SMD 슬롯
  `nominal_size_mm`를 기본 부품 크기로 사용한다. 지정 없으면 기본
  `6.0 × 3.5 × 2.5 mm`로 동작한다.
- 슬롯별 실측 후보치수(예: `smd_capacitor_01` `6.7527 × 3.8244 × 3.0238`,
  `smd_capacitor_02~05` `3.8087 × 6.7805 × 3.0238`)는 기본 입력에 반영된다.
- 기본 동작은 `--scan-all-black-cells` 사용이며, 기존 `run_object_approach`,
  `run_vertical_test`, `run_grasp_place_cycle` 체인을 그대로 사용한다.

### 검증 및 제한

- 현재 구현 상태는 `--dry-run` 기준으로 점검했고, 실기기 `--execute --confirm-full-cycle`
 은 추가 사용자 승인 하에 동작한다.
- 로봇/그리퍼 실제 명령은 아직 실행하지 않았다.
- 실행 전 검증 조건은: 새로 생성한 타겟 JSON 신선도, 파지 전 접근 실패 시
  fail-safe 복귀, 기존 hand-eye 경고 메시지 준수.

## 2026-09-01 — 부품 슬롯별 PatchCore v1 후보

- 기판 전체 PatchCore의 해상도 한계를 줄이기 위해 GPU/HBM/Power Module/VRM/
  Inductor를 CAD·실측 슬롯별로 자르고 긴 축을 정규화하는 데이터셋 생성기를
  추가했다. SMD는 현재 모델 범위에서 제외했다.
- 정상 학습/검증 ROI는 각각 320/80개다. 위치가 기록되지 않은 혼합 결함 ROI
  260개는 잘못된 결함 정답으로 사용하지 않고 추론 전용으로 격리했다.
- RTX 5070 Ti에서 5개 PatchCore 체크포인트를 생성했고 현재 S22 ROI에 대한
  20슬롯 통합 추론과 overlay/JSON 저장을 검증했다. 정합 점수는 0.9745였다.
- 현재 이미지에서는 모든 후처리 점수가 1.0으로 포화되어 임계값의 도메인 이동을
  확인했다. 따라서 상태를 `UNVERIFIED_SCORE_ONLY`로 고정했고 자동 PASS/FAIL에는
  연결하지 않았다. 현재 카메라 조건의 정상 샘플과 슬롯별 결함 라벨이 추가로
  필요하다.
- 관련 테스트 18개 통과. 로봇·컨베이어 명령은 전송하지 않았다.

### 현재 촬영 조건 정상 데이터 및 v2 재학습

- 확정한 30단계 정상 촬영 계획으로 SMD 제외 정상 기판 ROI 30장을 수집했다.
  전체 ROI는 1600×1266, 면적 비율 0.104285~0.106949, rectangularity
  0.908050~0.910060 범위였다.
- 정상 보드 24장을 학습, 6장을 검증으로 분리했고 GPU/HBM/Power Module/VRM/
  Inductor 정상 학습 ROI는 총 480개다. 현재 카메라 조건으로 부품별 PatchCore
  v2 체크포인트 5개를 생성했다.
- 마지막 정상 기판에서 정합 0.988, 20개 슬롯 점수 0.000~0.260(평균 0.126),
  포화 점수 0개를 확인해 v1 도메인 이동 문제를 해소했다.
- 불량 위치 라벨이 없어 임계값과 PASS/FAIL은 아직 확정하지 않았다. 로봇 및
  컨베이어 실제 명령은 전송하지 않았다.
- 통합 추론기의 기본 체크포인트와 결과 경로를 현재 카메라용 v2로 전환해 별도
  옵션 없이 실행해도 구 v1 모델을 불러오지 않도록 했다.

### SMD 포함 정상 데이터 및 부품별 PatchCore v3

- SMD 5개가 모두 장착된 정상 기판을 기준으로 기판 이동, SMD/GPU/HBM/Power
  Module/VRM/Inductor 허용 위치 변화를 포함한 53장을 수집했다. 전부
  1600×1266이며 기판 면적 비율 0.103961~0.107039, rectangularity
  0.903334~0.910599로 검증했다.
- 정상 기판 39장을 학습, 14장을 held-out normal로 분리했다. 6개 부품 타입의
  정상 학습 ROI는 GPU 39, HBM 312, Power Module 156, VRM 195, Inductor 78,
  SMD 195로 총 975개이며 RTX 5070 Ti에서 체크포인트 6개를 생성했다.
- 마지막 held-out 정상 기판의 정합 점수는 0.98399였다. 25개 슬롯 점수는
  0.0000~0.45183(평균 0.21880)이었고 SMD 5개는 모두 0.0이었다. 이는 정상
  memory bank와 매우 가까운 점수이며 결함 판정을 뜻하지 않는다.
- 통합 추론 기본 모델/출력을 `pcb_components_smd_v3`/`component_live_v3`로
  변경하고 SMD 제외 메타데이터를 해제했다. 과거 mixed-defect 사진은 어떤 슬롯이
  불량인지 기록되지 않았고 당시 SMD 조건도 달라 학습 지표는 참고값뿐이다.
  상태는 계속 `UNVERIFIED_SCORE_ONLY`이며 결함별·슬롯별 검증 전 자동 합불이나
  컨베이어 분기에 사용하지 않는다. 학습·검증 중 로봇 및 컨베이어 명령은 보내지
  않았다.

### S22 실시간 촬영→부품별 PatchCore 단일 실행

- `run_s22_component_patchcore_inspection.sh` 하나로 현재 검사 위치의 S22 3.5배
  광학 사진을 새로 촬영하고 기판 ROI를 원근 보정한 뒤, v3의 6개 모델로 25개
  슬롯을 연속 추론하도록 구성했다.
- 실행 전후 파일 identity를 비교해 촬영 실패 시 과거 ROI를 재사용하거나 추론
  실패 시 이전 JSON을 새 결과로 표시하지 않는다. 결과 ROI·overlay·JSON과 전체
  파이프라인 event JSON 경로를 출력한다.
- 휴대폰을 조작하지 않는 `--skip-capture` 검증에서 정합 `0.98399`, 25슬롯,
  `UNVERIFIED_SCORE_ONLY` 결과 생성까지 완료했고 관련 테스트는 `4 passed`였다.
  실제 새 촬영은 사용자가 실행하도록 남겼으며 로봇·컨베이어 명령은 보내지 않았다.
- 현재 모델에는 결함별 검증 임계값이 없으므로 이 실행 결과는 이상 점수 확인용이며
  자동 PASS/FAIL이나 컨베이어 분기로 사용하지 않는다.

### 부품별 PatchCore 25슬롯 Heatmap 합성

- 부품별 v3 추론에서 점수 박스만 제공하던 제한을 수정했다. 6개 모델이 출력하는
  pixel anomaly map을 수집하고, 세로 부품 학습 시 적용된 90도 회전과 resize를
  역변환해 각 슬롯의 실제 기판 좌표로 되돌린다. 초기 합성에서 학습용 22% 문맥
  여백까지 표시해 사각 경계가 생긴 문제를 실측 화면으로 확인했고, 최종본은 문맥
  여백을 제거해 실제 부품 몸체 25곳만 표시한다.
- 결과는 `원본 / 상대 Heatmap / 원본+Heatmap overlay` 3단 패널과 별도의 순수
  Heatmap, overlay, 슬롯 점수 이미지를 저장한다. 기본 `component_patchcore_latest.png`
  링크도 3단 패널을 가리키도록 변경했다.
- 서로 다른 6개 모델의 raw map scale을 직접 섞지 않고 부품 타입별로 2~99.5
  percentile 상대 정규화한 후 합성한다. 최신 실제 ROI에서 정합 `0.98277`, 25슬롯
  및 4종 시각화를 직접 확인했고 관련 테스트 `7 passed`를 통과했다. Heatmap 색은
  검증된 불량 확률이나 PASS/FAIL 임계값이 아니다.
  로봇·컨베이어 명령은 보내지 않았다.

### SMD 포함 전체 기판 PatchCore v4 및 통합 실행

- SMD 5개가 포함된 정상 기판 53장 중 39장을 학습, 14장을 held-out normal로
  사용해 전체 기판 PatchCore v4를 RTX 5070 Ti에서 학습했다. 기존 640×512보다
  높은 `960×768`, coreset ratio `0.03`을 적용해 기판 전역의 예상 밖 형상 변화를
  보되 작은 핀 검사는 부품별 v3에 맡긴다.
- 과거 mixed-defect 13장을 사용한 참고 지표는 image AUROC `1.0`, F1
  `0.76923`이었다. 당시 사진은 결함 종류·슬롯 라벨이 없고 SMD 조건도 달라 이
  수치를 생산 성능이나 확정 임계값으로 사용하지 않는다.
- 최신 SMD 포함 기판에서 전체 모델은 `GOOD`, score `0.27388602`였고 전체 기판
  Heatmap을 직접 확인했다. `run_s22_component_patchcore_inspection.sh` 한 번으로
  새 광학 촬영 후 전체 v4와 25슬롯 부품별 v3를 순차 실행하도록 통합했다.
- 최신 ROI의 `--skip-capture` 통합 검증과 테스트 `7 passed`를 완료했다. 결과는
  여전히 검증 후보이며 자동 합불·컨베이어 분기에 연결하지 않았다. 로봇과
  컨베이어 명령도 보내지 않았다.

### 전체 기판 기본 검사로 단순화

- 부품별 상대 Heatmap이 정상 부품에도 색을 강제로 만들고 서로 다른 모델 점수를
  직관적으로 비교하기 어려운 실측 결과를 반영해, 기본 검사는 전체 기판 v4만
  실행하도록 변경했다. `run_s22_whole_board_inspection.sh`가 새 기본 명령이며
  부품별 v3는 명시적으로 `--with-components`를 넣을 때만 개발용으로 실행된다.
- 최신 ROI에서 전체 전용 경로만 실행되는 것을 확인했고 score는 `0.49285376`였다.
  일부 부품 변화가 있는 화면에도 모델 threshold가 `GOOD`을 출력했으므로 확정
  합격으로 오인하지 않게 표시를 `MODEL GOOD | UNVERIFIED`로 변경했다.
- 파이프라인 테스트를 포함해 `8 passed`를 확인했다. 현재 전체 모델은 Heatmap
  후보이며, 통제 불량별 임계값 검증 전에는 자동 PASS/FAIL이나 컨베이어 분기에
  연결하지 않는다. 로봇·컨베이어 명령은 보내지 않았다.

### 전체 Heatmap 색상 기준 고정

- 기존 테스트 모델 시각화가 각 사진의 anomaly map 최솟값·최댓값을 매번 0~255로
  늘려 같은 이상도 촬영마다 다른 색으로 보이던 원인을 확인했다. 모델과 전체 기판
  구조는 유지하고 프레임별 min-max 정규화만 제거했다.
- Anomalib의 고정 `0.0~1.0` anomaly scale을 모든 촬영에 동일하게 0~255 색으로
  변환한다. 최신 부품 변화 기판에서 `MODEL ANOMALY | UNVERIFIED`, score
  `0.63822502`와 일관된 전체 Heatmap 생성을 확인했다.
- 고정 변환·파이프라인 테스트 `10 passed`; 재학습과 로봇·컨베이어 명령은 없었다.
  모델 임계값 자체는 아직 생산 검증 전이므로 `UNVERIFIED` 표시는 유지한다.

### 전체 기판 v4 3단계 임계값 1차 튜닝

- held-out 정상 14장 score가 모두 `0.0`, 별도 확인 정상 최신 샘플이
  `0.27388602`, 기존 mixed-defect 13장이 `0.45584026~0.68317264`, 현재 확실한
  부품 변화 기판이 `0.63822502`인 실측 분포를 기준으로 1차 triage를 설정했다.
- `score <= 0.40`은 `NORMAL_CANDIDATE`, `0.40 < score < 0.55`는 `RECHECK`,
  `score >= 0.55`는 `ANOMALY_CANDIDATE`다. 이 기준에서 held-out 정상은 14/14
  정상 후보, mixed-defect는 재검 7/13·이상 후보 6/13으로 모두 정상 통과에서
  제외됐다.
- 정상 잡색을 억제하기 위해 pixel anomaly `0.35` 이하는 overlay에서 숨기고,
  그 이상은 고정 0~1 범위로 표시한다. 별도 정상 검증은 `NORMAL_CANDIDATE
  0.2739`로 Heatmap이 비었고 현재 변화 기판은 `ANOMALY_CANDIDATE 0.6382`로
  이상 위치가 남는 것을 확인했다.
- 기준은 `whole_board_patchcore_v4.json`으로 분리했고 테스트 `13 passed`다.
  mixed-defect의 세부 라벨이 없으므로 현재는 3단계 선별 기준이며 자동 컨베이어
  합불 명령은 보내지 않았다. 로봇 명령도 없었다.

### 엄격 정상 전용 전체 기판 PatchCore v5 후보

- 53장 증가 데이터의 부품별 허용 위치 이동 38장을 모두 정상으로 학습한 것이
  미세 위치·방향 오류 민감도를 낮춘 원인이었다. 정확 조립 및 기판 위치 변화만
  포함한 10장을 학습, 5장을 정상 검증으로 두고, 부품을 움직인 38장과 과거 혼합
  불량 13장을 이상 검증으로 재분류했다.
- `960×768`, coreset `0.1`의 strict v5를 학습했다. image AUROC `0.79570`, F1
  `0.84211`이며 현재 확실한 변화 기판은 score `1.0`으로 강하게 검출했다.
- 그러나 정상 5장 `0.39559~0.51147`과 미세 변화 38장 `0.42534~0.74627`이
  겹쳤다. 따라서 전역 score 임계값 하나로 정상 전량 통과와 미세 변화 전량 차단을
  동시에 달성할 수 없어 v5는 후보로 보존하고 기본 모델을 덮지 않았다.
- 완전 무인 운영 목표는 유지한다. 사람 확인은 개발 데이터 정답 검수 단계에만
  해당하며 최종 런타임에는 없다. 다음 필수 데이터는 부품을 움직이지 않은 strict
  normal 추가 30장 이상과 결함 종류별 단일 변경 자료다. 위치·방향 자동 판정은
  전체 Heatmap 전역 score가 아니라 슬롯별 segmentation/기하 판정으로 분리해야
  한다. 학습 중 로봇·컨베이어 명령은 보내지 않았다.

## 2026-08-13 — 6mm급 소형 부품 고해상도 OpenCV 검출

- 실제 출력 부품의 자 측정값은 약 `6.0 × 3.5 × 2.5 mm`; Unity/CAD 후보
  `cap_small`은 약 `6.80 × 3.84 × 3.02 mm`다.
- D435 RGB `1920×1080×15`에서 최종 자세의 marker 8 한 변은
  `104.25 px`, 국부 영상 스케일은 약 `0.1611 mm/px`였다.
- ChArUco top-view의 지정 검정 셀에서 contour와 `minAreaRect`로 중심·긴 축을
  검출하는 `calibration/scripts/detect_small_part_dry_run.py`를 추가했다.
- 0-based `column=2, row=2`에서 20/20프레임 검출에 성공했다. 추정 크기
  `7.624 × 4.356 mm`, 긴 축 `175.71°`, Board XY
  `[84.172, 84.623] mm`였다.
- 등록 높이 기반 Camera XYZ `[-6.979, -10.712, 212.499] mm`, Hand-Eye 적용
  Base XYZ `[-313.664, -58.659, -10.061] mm`였다.
- Base 반복성 중앙/최대 `0.013/0.069 mm`; 시각 검증 자료는
  `calibration/data/small_part_debug_verified/`에 저장했다.
- 2.5mm 높이는 depth 노이즈·동기화 영향이 커 이번에는 `depth invalid`였으며,
  검증된 board plane과 등록 부품 높이를 사용했다.

## 2026-08-13 — ROS 2 AI/Vision 서버 기반 구축

### 목적

- D435, Galaxy S22, GoPro의 역할을 분리하면서도 Main Server가 동일한 ROS 2
  인터페이스로 결과를 받을 수 있는 기반을 만든다.
- 실제 카메라와 학습 모델이 없는 환경에서도 부품 수량 및 PASS/FAIL 검사 흐름을
  먼저 검증한다.
- 이름은 팀명 접두사나 과도한 약어를 사용하지 않고 역할을 바로 이해할 수 있게
  정한다.

### 구성

```text
camera_manager → part_detector → assembly_inspector
                         └──────→ vision status
```

- ROS 2 패키지: `vision_interfaces`, `vision_server`
- 노드: `camera_manager`, `part_detector`, `assembly_inspector`, `vision_mock`
- 주요 토픽: `/vision/camera/d435`, `/vision/camera/s22`,
  `/vision/camera/gopro`, `/vision/detections`, `/vision/inspection`,
  `/vision/status`
- 검사 서비스: `/vision/run_inspection`

### 카메라 역할

- D435: 근접 Pick, aligned depth, 위치 보정, 조립 후 근접 재검사
- S22: 기판 도착·회전 확인, 전체 부품 수량, 최종 조립 검사
- GoPro: 전체 셀 관제 및 향후 보조 안전 감시. 초기 YOLO 대상에서는 제외

카메라가 발행하는 물리 토픽은 `cameras.yaml`에만 기록하고, 후속 노드는 위의
고정된 논리 토픽을 사용하도록 분리했다. 따라서 S22 연결 방식이 바뀌어도 검출·
검사 노드의 코드를 바꿀 필요가 없다.

### YOLO와 검사 규칙

- Ultralytics 구현은 `detectors/yolo_backend.py`로 격리했다. 추후 ONNX 또는
  TensorRT backend로 교체할 수 있다.
- 모델 기본 경로는 `models/best.pt`이며 모델이 없을 때 노드가 비정상 종료되지
  않고 `model_loaded=false` 상태를 발행한다.
- 조립 대상 규칙: GPU 1, HBM 8, 검정 블록 5, 소형 흰색·갈색 부품 5,
  표시 있는 흰색 부품 2, 긴 주황색 부품 4로 총 25개다.
- 현재 검사는 confidence, 클래스별 정확한 수량, 알 수 없는 클래스, 최근
  3프레임 안정성, 결과 timeout을 확인한다.
- 위치·방향·CAD slot 일치와 외관 불량 검사는 실제 모델 및 촬영 데이터가
  준비되면 `assembly_inspector`에 추가한다.

### 검증

- `colcon build --symlink-install` 빌드 성공
- 검사 규칙 단위 테스트 4개 통과
- Mock 정상 시나리오: `PASS 25/25`
- Mock HBM 1개 누락 시나리오: `FAIL 24/25`
- 실제 실행 Launch는 모델 파일이 없는 상태에서도 카메라 관리, 검출, 검사
  노드가 시작되고 모델 누락을 경고하도록 확인했다.

### 변경 파일

- `ros2_ws/src/vision_interfaces/`
- `ros2_ws/src/vision_server/`
- `ros2_ws/run_vision.sh`
- `ros2_ws/run_vision_mock.sh`

### 다음 작업

1. 장비 현장에서 S22와 GoPro의 실제 입력 토픽을 확인해 `cameras.yaml` 수정
2. 6개 부품 클래스의 실제·렌더·합성 데이터를 수집하고 라벨링
3. YOLO 학습 후 `models/best.pt` 배치 및 GPU 성능 측정
4. S22 기판 pose와 CAD slot 기반 위치·방향 검사 추가
5. D435 검출 결과에 aligned depth와 Hand-Eye Base 좌표를 결합

## 2026-08-13 — ChArUco 전체 검정 칸 소형 부품 자동 탐색

- 소형 부품 검출 범위를 특정 칸 `(2,2)`에서 ChArUco 보드의 모든 검정 칸으로 확장했다.
- 검정 칸 가장자리의 부품도 포함하도록 셀 ROI 여백을 12%에서 3%로 조정했다.
- 20프레임 수집 중 선택된 셀이 바뀌면 샘플을 폐기하고 다시 수집하도록 안정성 잠금을 추가했다.
- 옮긴 부품을 `(2,2)` 셀의 보드 좌표 `[92.746,72.102] mm`에서 재검출했다.
- 검출 외곽 크기 중앙값은 `7.722 x 4.367 mm`, Base 위치는
  `[-321.980,-71.312,-9.963] mm`, 프레임 jitter median/max는
  `0.013/0.074 mm`였다.
- 최신 결과를 `calibration/data/small_part_last.json`에 저장해 이동 단계가
  과거 하드코딩 좌표 대신 현재 검출 좌표를 읽을 수 있게 했다.

### 소형 부품 방향 좌표 추가

- 검출한 직사각형 장축을 ChArUco Board 좌표에서 Robot Base XY 좌표로
  회전 변환하고 `long_axis_angle_base_deg`로 저장하도록 확장했다.
- 현재 대각선 부품의 기존 영상에서는 Board 장축 45°가 검출됐지만, 변경 후
  재검증 시점에는 ChArUco 코너가 0개여서 새 결과 파일은 갱신하지 않았다.
- 보드가 다시 보이는 자세에서 재검출해야 방향 기반 이동을 사용할 수 있다.

### HSV 색상·크기·모양 결합 검출

- 소형 부품 후보를 밝기/크기만으로 고르던 방식에 HSV 색상 프로파일을 추가했다.
- 지원 프로파일: `light`(기본), `orange`, `brown`, `any`.
- 현재 밝은 베이지 부품을 `light` 프로파일로 검출했으며 median HSV는
  `[17,42,141]`, 셀 `(2,0)`, Base 위치는
  `[-318.692,-133.977,-9.937] mm`였다.
- 30프레임 Base jitter median/max `0.034/0.087 mm`로 안정 검출을 확인했다.
- 최대 Base jitter가 기본 0.5 mm를 초과하면 최신 목표 JSON을 갱신하지 않는
  안전 차단을 추가했다.
- 검정 부품은 검정 ChArUco 칸과 색 분리가 불가능하므로 밝은 트레이/배경 또는
  다른 검출 구성이 필요하다.

### 대각선 배치 XY 정밀도 개선

- 대각선에서만 커지는 XY 편차를 분석한 결과, 같은 프레임에서 회전 사각형
  중심과 contour centroid 차이는 약 0.2 px(약 0.03 mm)로 작았다.
- 보드 외곽 4점을 PnP로 재투영해 rectification하던 방식을, 검출된 ChArUco
  sub-pixel 코너 전체(최대 24개)에 대한 왜곡 보정 및 homography 방식으로
  변경했다. 작은 부품의 국소 XY와 대각선/셀 가장자리 편차를 줄이는 목적이다.
- Depth 조회 픽셀은 개선된 보드 좌표를 원래 왜곡 영상으로 다시 투영해 RGB와
  aligned depth의 픽셀 정의가 섞이지 않도록 했다.
- 변경 후 시험 시점에는 보드가 화면 밖에 있어 ChArUco 코너가 0개였으며,
  로봇을 보드 관측 자세로 복귀한 뒤 실영상 재검증이 필요하다.
- 실제 로봇 이동은 수행하지 않았고 기존 목표 JSON도 갱신하지 않았다.

## 2026-08-15 — 최신 Unity PCB Assembly Scene과 기존 좌표 비교

- `/home/hc/My project/Assets/Scenes/PcbAssemblyScene.unity`와
  `Assets/RobotArm/PcbPickCoordinates.csv`를 확인했다.
- 현재 Unity 메뉴 `Tools/Robot Arm/Build PCB Assembly Scene`은 prefab의 현재
  임의 배치를 그대로 추출하지 않고, `PcbAssemblySetup.cs`의 `SlotCentersMm`와
  `SlotYawDegrees`로 부품을 다시 슬롯에 배치한 뒤 CSV를 생성한다.
- 이전 KSMC 추출 좌표와 현재 CSV를 동일한 PCB 좌상단 기준으로 변환해 비교한
  결과, HBM 8개와 대부분의 슬롯은 최대 약 `0.001 mm` 차이로 사실상 동일했다.
- GPU 중심은 이전 대비 약 `1.60 mm` 차이가 났다.
- 기존 4개 흰색·갈색 소형 부품 슬롯은 현재 SMD Capacitor 01~04로 이름이
  바뀌었고 각 위치가 약 `0.76 mm` 차이 났다.
- 현재 모델에는 이전 파일에 없던 SMD Capacitor 05가 추가되어 총 25개가 되었고,
  이전 추출 모델은 24개였다.
- 기존 좌표의 `left_black_block`, `long_orange`, `right_white_black`은 현재
  Unity 모델에서 각각 VRM, Power Module, Inductor라는 이름으로 대응되지만,
  물리적 XY 위치는 동일한 슬롯으로 확인됐다.
- 현재 CSV의 `rotation_y_deg`는 Unity 루트 transform 회전값이고, 이전 JSON의
  `long_axis_deg_in_board`는 부품 형상 장축 방향이므로 두 값을 직접 비교하면
  안 된다. 높이값도 이전 JSON의 bounds 후보와 현재 렌더러 top-center 기준이
  달라 별도 실측이 필요하다.

## 2026-08-17 — S22 컨베이어 ROI 설정 노드 구현

- 컨베이어 상판이 준비되기 전에도 화면 구성을 진행할 수 있도록 S22 compressed
  영상에 `PRE-STOP`과 `STOP / ASSEMBLY` ROI를 표시하는 `conveyor_roi` 노드를
  추가했다.
- ROI는 입력 해상도에 종속되지 않는 0~1 비율 좌표로 관리하며 설정 파일은
  `vision_server/config/conveyor_roi.yaml`이다.
- 표시 영상 `/vision/conveyor/roi_image/compressed`, 두 픽셀 ROI와 영상 준비
  상태 토픽을 발행한다.
- 현재 단계는 시각적 위치 설정 전용이며 컨베이어 속도나 로봇 명령을 전혀
  발행하지 않는다. S22와 컨베이어가 최종 고정된 뒤 ROI를 확정하고 도착 검출과
  감속·정지 상태 머신을 연결한다.
- ROS 2 패키지 빌드 성공, ROI 좌표 변환 단위 테스트 `3 passed`, 노드 기동을
  확인했다.

### 첫 정지 시험용 단일 ROI로 단순화

- 사용자 요청에 따라 주황색 `PRE-STOP` 영역과
  `/vision/conveyor/prestop_roi` publisher를 제거했다.
- 초록색 `STOP / ASSEMBLY` ROI는 최초 세로형 설정 후, 기판이 기본적으로 가로
  방향으로 진입한다는 실제 조건에 맞춰 화면 비율
  `x=0.11, y=0.54, width=0.78, height=0.32`의 가로형으로 바로잡았다.
- 1920x1080 입력에서 가로형 ROI는 `x=211, y=583, width=1498,
  height=346 px`로 발행된다.
- 이 단계에서는 `/cmd_vel` publisher를 만들지 않아 TurtleBot 바퀴는 움직이지
  않는다. ROI 위치 확정 후 기판 진입 감지 dry-run을 먼저 연결한다.

### 박스 대신 기판 후단 통과 정지선으로 변경

- 기판 크기와 방향 변화에 박스 비율을 계속 맞추는 대신, 컨베이어 진행 방향과
  수직인 경계선을 두고 기판 후단이 통과하는 순간 정지하는 방식으로 변경했다.
- 기존 주황 영역이 왼쪽, 초록 영역이 오른쪽이었던 화면 구조를 근거로 초기 진행
  방향을 영상 왼쪽→오른쪽으로 정의하고 화면 폭 70% 지점에 세로선을 표시했다.
- 새 표시 토픽은 `/vision/conveyor/stop_image/compressed`, 정지선 위치는
  `/vision/conveyor/stop_line_normalized`, 준비 상태는
  `/vision/conveyor/stop_line_ready`다.
- 실제 S22 프레임에서 밝은 알루미늄 구조물 위에서도 보이도록 검정 외곽선과
  초록 중심선, 노란 진행 방향 화살표를 확인했다.
- 다음 단계는 기판 외곽 검출 결과의 후단 X 좌표를 여러 프레임 안정화해 정지선
  통과 trigger를 발행하는 dry-run이며, 아직 `/cmd_vel`은 발행하지 않는다.

### 실물 기판 현재 위치를 정지 기준으로 등록

- 사용자가 원하는 최종 정지 위치에 실물 기판을 놓은 S22 1920x1080 프레임에서
  기판 외곽과 후단을 측정했다.
- 어두운 직사각형, 면적, 종횡비, 직사각형 충실도 조건으로 기판을 검출하고 내부
  검색영역을 사용해 상단 검정 장비와 알루미늄 프레임 오검출을 분리했다.
- 현재 기판 후단은 약 `788~790 px`였으며 정지선 위치를 화면 폭의 `0.411`
  (`약 789 px`)로 확정했다.
- 실영상 dry-run에서 `board_detected=true`, 후단-정지선 오차 약 `3 px` 이내,
  5프레임 안정 조건 후 `stop_trigger=true`를 확인했다.
- 주석 화면에 파란 기판 외곽, 빨간 후단 십자, 남은 픽셀 거리와 dry-run trigger를
  추가했다. 아직 TurtleBot `/cmd_vel` 명령은 발행하지 않는다.

#### OpenCV ChArUco API 호환 및 재검증

- 현재 OpenCV의 `CharucoBoard`가 `getChessboardCorners()` 대신
  `chessboardCorners` 속성을 제공해 발생한 `AttributeError`를 수정했다.
- 두 API를 모두 자동 지원하도록 호환 분기를 추가했다.
- 대각선 부품을 30프레임 재검출한 결과 셀 `(3,1)`, Board XY
  `[127.520,39.701] mm`, Base XYZ `[-356.810,-103.374,-9.579] mm`,
  Base jitter median/max `0.023/0.053 mm`로 정상 완료했다.

### S22 컨베이어 최종 정지 위치 재등록

- 사용자가 기판을 실제로 멈추길 원하는 위치로 다시 옮긴 뒤 64프레임의 기판
  후단 X를 측정했다. 측정값은 약 `883.64~883.89 px`, 대표값은
  `883.8 px`로 안정적이었다.
- 1920픽셀 영상 기준 정지선을 `position=0.46055`로 변경했다
  (`0.46055 × 1919 ≈ 883.8 px`). 앞서 기록한 `0.411`은 기판을 옮기기 전의
  임시 위치이며 현재 설정으로 대체한다.
- 실제 컨베이어 모터 명령은 아직 연결하지 않고, 검출·정지 트리거만 확인하는
  dry-run 안전 단계로 유지한다.
- 재시작 뒤 확인한 한 프레임에서는 기판의 진행방향 후단(왼쪽 끝)이 영상 밖으로
  잘려 `BOARD NOT DETECTED`가 되었다. 저장한 883.8 px 기준은 유지하되, 카메라를
  고정하고 기판 전체가 프레임 안에 보이는 상태에서 최종 재검증한 뒤 모터 정지와
  연결해야 한다.

## 2026-08-20 — 최신 Unity 기판·부품 좌표 재계산

- `/home/hc/My project/Assets/RobotArm/PcbPickCoordinates.csv`의 최신 Unity
  export를 다시 읽었다. 모델 기판은 `140.000 × 110.337 mm`, 실물 기판은
  `139.000 × 110.000 mm`로 적용했다.
- Unity 좌측 최소 모서리 원점을 실물 기판 중심 원점으로 변환하고 X/Y 축별
  스케일 `139/140`, `110/110.337`을 적용했다.
- GPU 1, HBM 8, Power Module 4, VRM 5, Inductor 2, SMD Capacitor 5의 총
  25개 ID가 중복 없이 존재하는지 검증했다. 이전에 누락됐던 SMD Capacitor 05가
  포함됐다.
- 90도 회전 부품은 기판 축 기준 footprint X/Y를 교환해 충돌 검사가 실제 방향을
  반영하도록 했다. 모든 중심과 회전 footprint가 139×110mm 기판 내부임을 확인했다.
- 재생성 파일은 `board_layout_from_unity.{json,csv,svg}`와
  `assembly_layout_approx.json`이다. 반복 변환 도구는
  `tools/import_unity_pick_coordinates.py`다.
- Unity 좌표는 CAD 후보이므로 기존 `physical_board.json`의 D435 실측 SMD
  override는 덮어쓰지 않았다. 로봇 자동 배치 전 TCP 상공 검증이 필요하다.

## 2026-08-20 — S22 조립·검사 2중 정지선 비전

- 단일 기판/단일 정지선 검출을 복수 기판 contour와 `assembly`, `inspection`
  정지선 2개를 독립 추적하는 구조로 확장했다.
- 조립선은 기존 실측 정규화 위치 `0.46055`를 보존했고 검사선은 최종 장비 설치
  전 임시값 `0.82`로 두었다. 두 위치는 YAML에서 독립 조정할 수 있다.
- 현재 검출 기판의 진행축 픽셀 길이를 이용해 정지선 간격이
  `1.10 × 기판 길이 + 20 px` 이상인지 검사한다. 부족하면 비전 ready와 모든
  station trigger를 차단한다.
- station별 trigger·후단·거리 토픽과 전체 기판 수, 간격 유효성 토픽을 추가했다.
  기존 단일 정지선 토픽은 assembly 호환 별칭으로 유지했다.
- 표시 영상에는 조립선(초록), 검사선(하늘색), 검출 기판 수, station별 남은 거리,
  간격 정상/오류를 한 화면에 정리했다.
- 이 단계에서는 S22 실영상과 실제 기판 2장을 사용한 현장 검증을 하지 않았다.
  최종 고정 후 두 기판이 동시에 완전히 보이는 구도에서 선 위치를 재등록해야 한다.
## 2026-08-21 — GPU 반복 접근 좌표 고정 타임아웃 수정

- FR5가 정지한 상태에서도 Euler 각도가 동일한 자세를 `+180°`와 `-180°`로
  번갈아 보고할 때, 기존 코드가 이를 약 360° 이동으로 오판해 검출 이력을 계속
  초기화하던 원인을 수정했다.
- 로봇 회전 변화와 과거 pose 일치 검사는 최소 원형 각도 차이로 계산하고, 안정
  구간 회전 span은 unwrap 후 계산하도록 변경했다.
- 수정 후 GPU #1의 최신 Base 좌표 5개를 연속 수집했으며 최대 jitter는
  `0.149 mm`로 제한값 `1.0 mm` 이내였다. 로봇 이동 명령은 보내지 않았다.

## 2026-08-21 — GPU 긴 변 방향 기반 그리퍼 정렬

- 트레이 검출기의 GPU 영상 각도를 D435 optical frame 방향 벡터로 만든 뒤
  `T_base_flange @ T_flange_camera` 회전으로 변환해
  `long_axis_angle_base_deg`를 출력하도록 추가했다.
- 최신 좌표 고정 파일에는 Base 중심뿐 아니라 여러 프레임의 180도 주기 중앙
  방향각도 함께 저장한다.
- GPU #1 통합 접근은 안전 Z에서 `tool_y` 축을 GPU 긴 변에 최소 회전으로 맞춘
  다음 수평 이동과 100 mm 상공 접근을 수행하도록 변경했다. 회전 속도는 50%,
  이동 속도는 40%이며 표면 하강과 그리퍼 명령은 포함하지 않는다.

## 2026-08-21 — GPU 2개 검출 복구 및 대기자세 고속 모드

- 왼쪽 GPU는 검정 후보 면적비 `1.938`이 기존 상한 `1.8`을 조금 넘어 탈락한
  것으로 진단했다. 상한을 `2.2`로 조정하되 D435 돌출 비율과 형상 면적 검증은
  유지했다. 이후 GPU 두 개 모두 안정 검출되었다.
- 후보가 면적, 유효 Depth, 돌출 비율, 형상 면적 중 어디서 탈락했는지 확인할 수
  있도록 `gpu_candidate_diagnostics`를 결과 JSON에 추가했다.
- 1080p SIFT 연산 때문에 검출 영상이 평균 약 2.5~3 FPS로 떨어지는 것을 확인했다.
  현재 트레이 대기 flange pose를 `config/tray_view_pose.json`에 저장하고, 그
  자세 오차가 위치 1 mm·회전 0.3도 이내일 때만 고정 ROI를 활성화했다.
- 대기자세 고속 모드에서 GPU 2개와 Base 좌표가 유효함을 확인했으며, 검출 화면은
  실제 약 5.5 FPS로 개선됐다. 로봇이 대기자세를 벗어나면 검출은 즉시
  `NOT_REGISTERED`가 되어 다른 장면에 트레이 박스를 표시하지 않는다.
- 최초 고속 모드에서 기준 영상과 현재 영상의 크롭 차이를 무시하고 identity
  homography를 사용해 GPU 영역이 위로 어긋난 오류를 확인했다. 해당 가정은
  폐기하고 현재 대기 화면에서 SIFT로 검증한 `reference_to_live_homography`를
  `config/tray_view_pose.json`에 저장했다. 고속 모드는 이 행렬을 재사용하며,
  GPU 영역과 두 실측 박스가 SIFT 화면과 동일하게 정렬되는 것을 재확인했다.
- 이후 실제 화면 검토에서 실측 투영 박스가 GPU 픽셀 외곽과 정확히 일치하지 않는
  것을 확인했다. 색상 외곽은 그림자와 합쳐지고, Depth 우선 외곽은 D435 바닥
  노이즈로 합쳐져 두 방식 모두 정확한 segmentation 대체재가 되지 못했다.
  Depth 우선 실험은 폐기하고 두 GPU 중심을 안정 검출하던 색상+Depth 검증으로
  복구했다. 현재 파란 박스는 픽셀 외곽선이 아니라 `57 x 27 mm` 기반 파지 자세
  추정 박스이며, 정확한 회전 외곽은 향후 YOLO-OBB로 교체해야 한다.

## 2026-08-21 — GPU YOLO-OBB 전환 기반 구축

- 그림자와 D435 Depth 경계 노이즈 때문에 OpenCV contour만으로 GPU 외곽과 회전을
  안정적으로 맞추기 어렵다고 판단해 GPU 검출을 YOLO-OBB로 교체할 수 있는 경로를
  추가했다. 기존 색상+Depth 검출은 모델 학습 전까지 유지한다.
- AI/Vision 서버의 YOLO backend가 일반 bbox뿐 아니라 Ultralytics OBB의 네 꼭짓점,
  중심, 크기, 180도 주기 긴 변 각도를 읽어 기존 `Part` 메시지로 전달하도록 확장했다.
- D435 원본 압축 RGB에서 학습 이미지를 저장하는 도구, 네 꼭짓점 라벨 GUI,
  train/validation 분할, 학습, ROS 실행 설정과 실행기를 추가했다.
- 전용 환경 `vision_assembly/.venv_obb`에 Ultralytics `8.4.124`, Torch
  `2.13.0+cu130`, OpenCV `4.11.0`, NumPy `1.26.4`를 구성했다. 현재 NVIDIA
  드라이버를 사용할 수 없어 CUDA는 비활성 상태이며, 현장 GPU 환경에서 학습하는
  것이 적절하다.
- 동일한 첫 GPU 배치의 1920×1080 이미지 10장을 확보했다. 라벨과 다양한 위치·회전
  배치 데이터는 아직 수집 중이며, 학습 모델을 로봇 이동에 적용하지 않았다.
- `vision_server` ROS 패키지 빌드와 가상 OBB 결과 변환 시험은 통과했다. 실제
  `best.pt` 생성 후에는 정지 화면 검증을 거쳐야 하며 로봇 자동 이동은 별도 승인한다.
- 최초 동일 배치 10장과 추가로 위치·회전을 바꾼 2장에 GPU 2개씩 총 24개 OBB
  라벨을 저장하고 형식 검사를 통과했다. 데이터셋은 train 10장, validation 2장으로
  분할했지만 독립 배치 다양성이 3개뿐이므로 본 학습은 추가 촬영 후 진행한다.
- 이후 촬영분까지 포함해 1920×1080 GPU 이미지 35장을 모두 재검토했다. 각 이미지에
  GPU 2개씩 총 70개 OBB 라벨이 있고 누락·형식 오류는 없었다. 이전 분할 복사본을
  정리한 뒤 train 28장, validation 7장으로 재분할했다. 아직 학습 모델과 로봇 이동은
  실행하지 않았다.
- RTX 5070 Ti Laptop GPU와 CUDA 13.2는 정상 인식됐다. 초기 학습은 가상환경의
  cuDNN 9.20과 시스템 cuDNN 9.25 하위 라이브러리가 섞여 발생한
  `CUDNN_STATUS_SUBLIBRARY_VERSION_MISMATCH`로 중단됐다. 전용 환경 cuDNN을
  9.24.0.43으로 통일한 뒤 CUDA convolution 동작을 확인했고, 설치 스크립트에도
  같은 호환 버전을 명시했다. 학습 재실행은 사용자 터미널에서 진행한다.
- GPU OBB 1차 학습은 `YOLO26n-OBB`, 960px, batch 8, 100 epoch로 RTX 5070 Ti에서
  약 58초에 완료됐다. validation 7장 기준 precision `1.000`, recall `0.996`,
  mAP50 `0.995`, mAP50-95 `0.995`였다. 학습 데이터 수가 작으므로 이 수치는 현재
  촬영 조건에서의 기준 성능이며, 새 배치·조명·각도 검증이 반드시 필요하다.
- 최적 가중치 `runs/gpu_obb-2/weights/best.pt`를 ROS Vision Server 런타임 모델로
  배치하고 패키지를 재빌드했다. 학습에 사용하지 않은 `tray_reference_no_tape.jpg`
  에서 GPU 1개를 confidence `0.995`, OBB 4 꼭짓점 및 긴 변 각도 `92.45°`로
  검출하는 것을 확인했다. 로봇 이동 명령은 실행하지 않았다.

## 2026-08-24 — Unity 3D 모델 기반 PCB 합성 OBB 데이터 생성 경로 구축

- Unity `ITEAM.prefab`과 `PcbAssemblySetup.cs`를 점검해 실제 보드 슬롯을
  GPU 1개, HBM 8개, Power Module 4개, VRM 5개, Inductor 2개,
  SMD Capacitor 5개로 확인했다. 합성 데이터도 동일한 25개 slot을 기준으로 만든다.
- Unity 원본을 수정하지 않고, OBJ·PNG 텍스처를 Blender에서 읽어 RGB 렌더,
  YOLO-OBB 네 꼭짓점 라벨, slot/결함 metadata를 함께 생성하는 도구를
  `vision_assembly/synthetic/`에 추가했다.
- 정상 조립, 1~3개 누락, 1~5 mm 위치 오류, 15~60도 방향 오류와 카메라·조명
  변화를 생성한다. 누락은 탐지 클래스가 아니라 실제 검출 결과와 기대 slot을
  비교하는 검사 규칙에서 판정하도록 유지했다.
- 정상 조립 미리보기 1장에서 25개 OBB 라벨을 자동 생성하고, 이미지 위에 그린
  검증 영상을 통해 GPU/HBM/Power Module/VRM/Inductor/SMD 라벨 위치를 확인했다.
- 이 데이터는 `board_inspection_obb` 사전학습 전용이며, D435 트레이용
  `tray_pick_obb`와 분리한다. 최종 모델에는 고정된 S22 실제 조립 사진으로
  fine-tuning이 필요하며, 크랙 판정에는 D435 근접 실제 이미지가 필요하다.
- 실제 공정 정의에 맞춰 PCB를 단독 물체가 아니라 `지그+기판` 운반 단위로
  변경했다. Unity의 `RobotArm/Fixture/Cube.001.fbx`를 모든 정상·불량 합성
  장면에 항상 포함하고, 4핀 패턴 중심을 PCB 중심에 맞춘 뒤 지그를 기판 아래에
  밀착 배치한다. 손잡이 방향은 board `+Z(north)`로 고정했다.
- 지그는 컨베이어 운반·기판 고정·완성품 렉 이송 시 손잡이 파지에 사용되는
  구조물이며 조립 부품 OBB 6개 클래스에는 포함하지 않는다. 각 이미지 metadata에
  지그 소스, 포함 여부, 손잡이 방향과 역할을 별도로 기록한다.
- 지그 포함 정상 미리보기 1장과 부품 OBB 25개를 생성해 렌더 및 라벨 생성을
  검증했다. 로봇 동작이나 Unity 원본 수정은 수행하지 않았다.
- 1 mm 수동 오프셋은 실제 확인에서 과도한 것으로 판단해 폐기했다. Unity와 합성
  데이터 모두 임의 XY 오프셋을 0으로 복구하고, 지그 4핀 패턴 중심과 기판 안쪽
  4개 구멍 패턴 중심을 직접 정렬하는 방식을 사용한다.
- Unity에서 사용자가 지그 핀과 기판 구멍을 최종 육안 정렬한 위치를 자동 생성 시
  유지하도록 지그 미세 조정값 `X +0.31985 mm`, `Z +0.08084 mm`를 기준값으로
  저장했다. 합성 데이터도 같은 값을 사용하며, 이는 카메라/TCP 보정값과 무관한
  CAD 조립 상대 위치이다.
- 최초 Blender 미리보기는 Unity와 FBX 축 해석이 달라 손잡이가 반대쪽에 있었고,
  핀 최고점을 기판 밑면으로 잘못 취급해 지그 높이도 일치하지 않았다. 해당 결과는
  폐기하고 Blender FBX 평면을 180도 보정했으며, Unity와 동일한 넓은 지지면 탐색으로
  핀을 제외한 지지면을 기판 밑면에 밀착시켰다. 현재 손잡이는 저장된 Unity 씬과
  동일한 board `-Z` 쪽이고, 안쪽 4개 구멍에 핀이 배치된다.
- 이후 Unity 현재 씬을 움직이지 않고 직접 렌더하고 모든 직계 오브젝트의 Renderer
  Bounds를 내보내는 `PcbSceneValidation` 도구를 추가했다. 실제 Unity 출력은
  `runtime/unity_current_exact.{png,json}`이며 합성 생성기는 이 JSON을 지그 위치의
  최종 권위 데이터로 사용한다.
- Unity와 새 합성 샘플을 수치 비교한 결과 지그 중심 최대 오차 `0.000391 mm`,
  지그 크기 최대 오차 `0.000363 mm`, 부품 25개 중심 최대 오차 `0.000627 mm`였다.
  부품 Bounds 크기 차이는 모두 `0.01 mm` 미만이고 OBB 라벨도 `25/25` 생성됐다.
  그러나 이 검사는 Bounds 중심과 크기만 비교했기 때문에 FBX/OBJ 내부 메시 축,
  지그 핀 위치, 모델 방향까지 검증하지 못했다. 실제 영상 비교에서 지그 핀이
  구멍과 맞지 않고 Inductor/SMD/VRM 형상이 Unity와 다름을 확인했다. 따라서
  `unity_verified_preview` 판정도 철회하고 해당 결과를 삭제했다.
- Blender에서 Unity 모델을 재조립하는 경로는 최종 데이터 생성 방식으로 사용하지
  않는다. 이후 합성 데이터는 Unity 현재 씬을 원본으로 직접 렌더하고 Unity
  Renderer에서 라벨을 투영하는 Unity-native 방식으로 전환한다.
- Unity 원본 `ITEAM.prefab`에서 `SMD Capacitor 05` 하나만 기판 밖에 저장된 예외를
  확인했다. 전체 부품 재배치 로직은 다시 사용하지 않고, 빌드 시 해당 부품만 기존
  슬롯 정의로 복구하도록 수정했다. 검증 결과 중심은 Unity world 기준
  `[-41.934, 2.716, 39.305] mm`이며, Unity-native 출력에는 전체 부품 `25/25`가
  기판 내부에 유지된다. Pick Point와 CSV는 복구된 실제 Renderer Bounds를 기준으로
  다시 생성된다.
- Unity-native OBB exporter를 Renderer의 world AABB 방식에서 실제 Mesh vertex를
  카메라 영상에 투영한 최소면적 회전 사각형 방식으로 변경했다. 따라서 기판/부품
  또는 카메라가 회전해도 OBB가 실제 부품 방향을 유지한다.
- 원본 Unity Scene을 매 샘플 후 복원하면서 정상, 누락, 위치 오류, 방향 오류와
  기판 회전·카메라·조명 변화를 생성하는 `PcbObbDatasetGenerator`를 추가했다.
  24장 사전 검증에서 정상/변형 이미지는 25개, 누락 3장은 24개 라벨로 확인됐으며,
  카메라 여백과 보조 조명을 조정해 기판 잘림 및 밝은 부품 과노출을 줄였다.
- Unity-native 최종 데이터셋 300장(train 240/val 60)을 전수 검사했다. 정상 176,
  누락 38, 위치 오류 53, 방향 오류 33장이며 이미지/라벨/metadata 대응, OBB 좌표
  범위와 면적 검사를 모두 통과했다. 정상·변형은 25개, 누락 샘플은 정확히 24개
  라벨이다.
- RTX 5070 Ti에서 `YOLO26n-OBB`, 960px, batch 8, 100 epoch로 6개 클래스 합성
  사전학습을 완료했다. 합성 validation 전체 mAP50은 `0.989`, mAP50-95는 `0.886`이며
  클래스별 mAP50-95는 GPU 0.993, HBM 0.892, Power Module 0.964, VRM 0.897,
  Inductor 0.863, SMD Capacitor 0.709이다. 안정 모델은
  `vision_assembly/models/pcb_obb_unity_pretrain.pt`에 저장했다.
- 낮은 confidence의 raw detection 개수를 그대로 세면 중복·오검출이 남으므로 이
  모델만으로 최종 수량/PASS 판정을 하지 않는다. 실제 S22 이미지 fine-tuning 후
  기판 pose로 생성한 예상 슬롯과 검출 OBB를 1:1 할당하고, 슬롯별 존재·위치·방향을
  판정하는 방식으로 사용한다.
- 실제 조립 기판 사진 `/home/hc/Downloads/1000029143 (1).jpg`에 합성 사전학습
  모델을 시험했다. GPU는 검출됐지만 HBM은 일부만 검출됐고, VRM이 노란색 모듈로
  오검출되는 등 실제 판에 바로 사용할 수 없는 수준임을 확인했다. 결과 이미지는
  `runtime/actual_board_prediction`에 저장했으며, 다음 단계는 실제 S22/D435
  이미지 라벨을 추가해 fine-tuning하는 것이다.
- GPU 전용 OBB 모델의 실제 D435 영상 검증을 위해 기존 검출 메시지 토픽에 더해
  회전 박스, 중심점, 신뢰도, 장축 각도를 표시하는
  `/vision/gpu_obb/image/compressed` 시각화 토픽을 추가했다. 기존 검출 및 로봇
  이동 인터페이스는 변경하지 않았으며 `vision_server` 빌드를 완료했다.
- 원격 D435 1080p 영상에서 GPU OBB 시각화가 5 FPS로 제한되어 끊겨 보이던 설정을
  실시간 검증용으로 조정했다. 추론 입력은 960에서 768 px, 최대 추론/시각화 속도는
  5에서 12 FPS, 출력 JPEG 품질은 90에서 85로 변경했다. 원본 D435 영상 토픽과
  학습 모델, confidence 기준은 변경하지 않았다.
- 실제 GPU 영상에서 동일 물체에 OBB 두 개가 겹치는 중복 검출을 확인해 YOLO NMS
  IoU를 0.30으로 강화하고, 후처리에서도 같은 클래스 회전 사각형의 polygon IoU가
  0.25 이상이면 낮은 confidence 박스를 제거하도록 추가했다. 실시간 응답 개선을
  위해 추론 입력을 640 px, 시각화 JPEG 품질을 80으로 조정했다. 출력 중심과 각도는
  원본 영상 좌표로 복원되므로 D435 원본 해상도와 좌표계는 변경되지 않는다.
- 원격 GPU OBB 검출에서 RGB 압축 영상과 함께 1080p 정렬 Depth raw 토픽까지 항상
  구독해 Wi-Fi 대역폭을 크게 사용하는 병목을 확인했다. 기본 실행은 RGB compressed
  전용으로 분리하고, 실제 3D 위치가 필요한 경우에만 `GPU_OBB_USE_DEPTH=1`로
  RGB-D 설정을 선택하도록 변경했다. 학습·수량·중심·OBB 각도 검증에는 Depth를
  전송하지 않으며, 이 변경은 학습 모델이나 Hand-Eye 결과에 영향을 주지 않는다.
- 다중 부품으로 확장할 때 OBB 위의 신뢰도·각도 텍스트가 서로 겹치는 문제를 줄이기
  위해 기본 시각화에서는 부품명과 confidence만 표시한다. 각도 값은
  `/vision/gpu_obb/detections` 메시지에 계속 발행되며, 설정의 `draw_angle`을
  `true`로 바꾸면 디버깅 화면에서도 다시 표시할 수 있다.
- GPU 다음 실제 학습 대상으로 HBM을 선정하고, 향후 6개 부품에 공통으로 사용할
  D435 선명도 기반 이미지 수집기와 다중 클래스 4점 OBB 라벨러를 추가했다. 클래스
  매핑은 Unity 합성 데이터와 동일하게 GPU=0, HBM=1, Power Module=2, VRM=3,
  Inductor=4, SMD Capacitor=5로 고정했다. 현재 트레이의 첫 HBM 실제 이미지 1장을
  `vision_assembly/obb/real_multiclass/images/unlabeled`에 저장했으며 sharpness는
  157.9였다. 이 작업 중 로봇 및 컨베이어 명령은 전송하지 않았다.
- 사용자가 실제 HBM 이미지 라벨링을 완료한 뒤 파일을 검사했다. 최신 이미지
  `hbm_20260826_173452_400690918.jpg`에 class 1 HBM OBB가 16개 저장되어 현재
  트레이의 2세트 수량과 일치하며, 모든 행이 Ultralytics OBB 9필드 형식을
  만족했다.
- Power Module 실제 이미지 라벨링도 검사했다. 최신 이미지
  `power_module_20260826_180906_689373047.jpg`에 class 2 OBB 8개가 저장됐고,
  모든 라벨이 올바른 9필드 형식을 만족했다.
- 다중 클래스 OBB 라벨러에서 저장된 박스마다 부품명을 중앙에 표시해 주변의 작은
  부품을 가리던 문제를 수정했다. 박스는 클래스별 색상 선으로만 표시하고, 현재
  선택 클래스는 상단 상태 표시줄에서만 확인한다. 저장되는 클래스 ID와 라벨
  형식에는 변화가 없다.
## 2026-08-27 — S22 고정형 기판 Base 좌표 Localizer

- 기존 S22 컨베이어 기판 검출 결과를 재사용하는 고정형 기판 localizer를
  추가했다. 컨베이어 노드는 조립/검사 위치별 기판 외곽 4점을
  `/vision/conveyor/{station}/board_polygon_normalized`로 발행하고, localizer는
  저장된 Homography로 이를 FR5 `base`의 `PoseStamped`로 변환한다. 별도 영상
  디코딩·중복 기판 검출이 없어 S22 프레임 부하를 늘리지 않는다. 위치 유효성,
  calibration coverage, 실측 기판 크기를 함께 검사하며, 실물 지그 방향 판별이
  끝나기 전 yaw는 180° modulo로만 제공하고 `heading_valid=false`로 차단한다.

## 2026-08-31 — S22 망원 촬영 기반 PCB 전수검사

- S22 컨베이어 overview와 검사 촬영을 분리했다. overview는 최신 저지연 프레임으로
  정지 판정을 유지하고, 정지 후 Samsung Camera의 실제 3× 망원 렌즈와 3.5× 촬영을
  사용해 4000×3000 JPEG를 확보한다.
- 기판 외곽과 지그 손잡이를 분리한 뒤 139×110 mm 기판을 1600×1266으로 원근
  보정하고, 검사 방향에 맞춘 ROI·디버그 이미지·메타데이터를 저장한다.
- `full_board_inspector.py`는 정상 reference, Unity socket clearance, 부품별
  OpenCV 규칙을 사용해 25개 슬롯의 존재·위치·방향과 GPU/HBM 흰 다리를 검사한다.
  S22로 확정하기 어려운 VRM과 미세 외관은 D435 재검사 대상으로 분리한다.
- 검사 정지 trigger 뒤 0.35초 안정화, 망원 촬영, ROI 생성, 검사, 결과 발행까지
  연결했다. trigger one-shot/rearm gate, 중복 실행 lock, stale latest 거부를 포함한다.
  실제 컨베이어 정지 연동은 확인했으나 HBM 다리와 3D 프린트 편차 기준은 추가
  튜닝이 필요하다.

## 2026-08-31 — 조립 위치 빈 기판 슬롯 좌표 추출 및 물리 보정

- `/vision/conveyor/assembly/board_polygon_normalized` 20프레임의 중앙값과 S22
  무손실 캡처를 결합해 GPU 1, HBM 8, Power Module 4, VRM 5, Inductor 2,
  SMD Capacitor 5의 board-mm/image-pixel 좌표를 내보내는 도구를 추가했다.
- 첫 산출물에서 Inductor/SMD 상하 위치가 실제 홈과 반대인 것을 발견해 해당
  JSON/CSV/PNG와 아카이브를 제거했다. CAD 후보보다 `physical_board.json`의
  물리 override를 우선 적용하고, 알 수 없는 슬롯·부품 타입이면 export를 중단한다.
- 최종 번호는 S1 가로, S2~S5 오른쪽 세로열 아래→위, I1~I2 오른쪽 아래 원형 홈
  위→아래다. 새 오버레이에서 실제 홈과 일치하며 외곽 최대 jitter는 2.01 px였다.
- 관련 단위 테스트 20개를 통과했다. 로봇·컨베이어 명령은 보내지 않았고,
  S22 평면 Base 캘리브레이션이 없으므로 현재 좌표를 직접 FR5 하강점으로 사용하지
  않는다.

## 2026-08-31 — S22 입력 경로 scrcpy 단일화

- 사용하지 않는 구 스마트폰 앱 기반 USB·Wi-Fi 입력을 제거하고 S22 영상 입력을
  USB scrcpy로 단일화했다. `/camera2` 토픽, 컨베이어 정지선 검출과 검사 서비스
  계약은 유지했다.
- V4L2→ROS 최신 프레임 발행기는 `camera2_scrcpy/`로 이전했다. 18초 무동작
  실기동에서 3840×2160 캡처 약 29.8 FPS, ROS 15 FPS와 ROI 노드 시작을 확인했고,
  로봇·컨베이어 이동 명령은 전송하지 않았다.

## 2026-08-31 — 판정 분리형 AOI 데이터 수집

- 검사 정지마다 기존 규칙 기반 판정을 실행하지 않고 S22 광학 원본과 보정 ROI만
  보존하는 `capture_conveyor_dataset_once.py`와 관리형 실행기를 추가했다.
- 과거 촬영물에 불량품이 섞였음을 반영해 모든 신규 샘플을 `UNVERIFIED` 및
  `normal_training_allowed=false`로 잠근다. 정상-only 이상탐지 학습에는 사람의
  전수 검수 후에만 승격한다.
- 현재 SMD가 없는 기판은 `board_state=known_defect`,
  `known_defects=[missing_smd]`로 기록한다. 이 주석은 작업자 입력이지 자동 판정이
  아니다.
- 원본·ROI·upright·디버그·검출 메타데이터 중 하나라도 오래된 파일이면 샘플 생성을
  거부한다. 품질 통계와 조명 조건을 manifest/index에 함께 저장한다.
- 단위 테스트 5개를 통과했다. 코드 검증 중 로봇 및 컨베이어 실동작 명령은 보내지
  않았다.

## 2026-08-31 — 정지 판단과 UI 렌더링 분리

- `conveyor_roi`가 기판 검출 후 대시보드 전체를 그리고 JPEG로 압축한 다음에야
  stop trigger를 발행하던 순서를 수정했다. 두 정지선의 trigger·distance·polygon,
  spacing interlock과 ready heartbeat를 먼저 발행하고 UI는 이후 선택적으로 그린다.
- UI 구독자가 없으면 렌더링을 생략하고, 있을 때도 15 FPS로 제한한다. 실제 UI
  구독 실측은 약 12.4~13.1 FPS였지만 제어 입력은 29.2~29.8 FPS를 유지했다.
- 영상 header 기준 age가 0.20초를 넘으면 해당 검출을 사용하지 않고 ready=false를
  발행한다. timestamp/heartbeat 회귀 테스트를 포함해 전체 관련 테스트 30개를
  통과했다.
- 실제 컨베이어와 로봇 명령은 전송하지 않았다. 동일 0.10 m/s 실동작 재검증이
  남아 있다.

## 2026-08-31 — PatchCore용 PCB AOI 데이터셋 v1

- 2026-08-31 S22 망원 촬영분 중 사용자가 정상 조건 변화로 촬영한 ROI 20장과
  다양한 불량을 섞어 촬영한 ROI 13장을 분리했다.
- `vision_assembly/inspection/datasets/pcb_anomaly_v1`에 MVTec 호환 구조로
  `train/good=16`, `test/good=4`, `test/mixed_defect=13`을 구성하고 촬영 시각과
  원본 경로를 `manifest.csv`에 기록했다.
- 모든 입력은 동일한 1600×1266 원근 보정 ROI이고 해시 중복은 없다. 불량별 상세
  라벨은 촬영 시 기록되지 않아 현재 13장은 anomaly 평가 전용이며, defect-type
  분류에는 사후 검수 전까지 사용하지 않는다.
- 원본을 이동·삭제하지 않았고 로봇·컨베이어 실동작 명령도 보내지 않았다.

## 2026-08-31 — PatchCore 전체 기판 baseline 실측

- `train_pcb_patchcore.py`와 GPU 실행기를 추가하고 Anomalib 2.6.0
  PatchCore/Wide-ResNet50-2, 입력 640×512, coreset 0.1로 v1 데이터셋을
  학습·평가했다.
- held-out test의 image AUROC는 0.9583, image F1은 0.5455였다. 전체 test 17장
  재추론에서 정상은 4/4 GOOD, known abnormal은 7/13 ANOMALY로 나와 현재
  threshold 판정의 불량 recall은 부족하다.
- 17개 원본/heatmap/overlay와 `prediction_scores.csv`, checkpoint,
  `baseline_summary.json`을 저장했다. 기본 visualizer와 사용자 저장기의 마지막
  파일 경합도 제거하고 17개 모두 4800×1266 패널로 검증했다.
- 전용 venv의 cuDNN 9.20 sublibrary mismatch는 이 장비의 기존 YOLO 검증 버전인
  9.24.0.43으로 맞춰 GPU convolution과 전체 학습을 통과시켰다.
- 현재 모델은 baseline이며 생산 합불에는 사용하지 않는다. 추가 정상 데이터와
  부품별 고해상도 ROI 모델이 필요하다. 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-01 — S22 새 시점의 조립·검사 정지선 및 저지연 판정

- S22 실시간 시점을 메인 카메라 1.5배로 고정하고 두 기판을 동시에 검출했다.
  960px 처리 영상에서 수동 배치한 조립·검사 기판의 초기 trailing edge는
  `175.69px`, `574.67px`였으며 정지선을 `0.18301061`, `0.59861813`으로
  변경했다. 두 정지선 간격 `0.41560752`는 안전 간격 검사를 통과했다.
- 실제 0.10m/s 주행에서 기존 10px lead가 남긴 downstream overrun 보고를
  반영해 control trigger만 20px 앞당겼다. 화면의 선은 실제 목표 위치에 그대로
  남아 있어 정지 결과와 육안 비교가 가능하다.
- source-frame stale cutoff를 0.20초에서 0.15초로 줄였다. 검출은 한 crossing
  frame에서 즉시 확정하고 최신 1프레임 BEST_EFFORT 입력, 제어 우선 publish,
  UI 15 FPS 분리는 유지한다.
- 회귀 테스트 `35 passed`를 확인했다. 이번 변경 과정에서는 `/cmd_vel`을
  발행하지 않았으며, 실제 재주행 후 20px lead의 최종 잔차 검증이 필요하다.

## 2026-09-01 — 검사 촬영 프레이밍 기반 검사선 최종 이동

- 새 물리 위치에서 3.5배/4000×3000 망원 촬영과 1600×1266 기판 ROI 추출을
  확인했다. 기판 네 모서리와 전체 부품은 포함되고 지그 손잡이는 검사 ROI에서
  제외됐다. 검출 면적 비율은 `0.1067`, rectangularity는 `0.907`이었다.
- 동일 위치의 1.5배 제어 영상에서 trailing edge `503.7585/960px`를 측정해
  inspection line을 `0.52474848`로 변경했다. assembly line과 20px 선행
  trigger는 변경하지 않았다.
- 회귀 테스트 `35 passed`; 실제 로봇·컨베이어 명령은 전송하지 않았다.

## 2026-09-01 — 검사선 최신 위치 미세조정

- 최신 1.5배 화면에서 inspection trailing edge `485.0px`를 측정해 정규화
  검사선을 `0.50520833`으로 갱신했다. 조립선과 20px lead는 유지했다.
- 정지선 간격 `0.32219772`, 테스트 `35 passed`. 설정만 저장했으며 실행 노드와
  로봇·컨베이어는 조작하지 않았다.

## 2026-09-01 — Whole-board PatchCore 단일 ROI 추론

- PatchCore v3 checkpoint를 다시 학습하지 않고 최신 S22 기판 ROI 한 장에
  적용하는 `run_predict_pcb_patchcore.sh`와 단일 추론 스크립트를 추가했다.
  결과 CSV와 원본/heatmap/overlay 패널을 `runtime/inspection/patchcore/live`에
  저장한다.
- 최신 SMD 누락 기판은 `GOOD`, anomaly score `0.45852470`으로 예측됐다. 이는
  기존 16장 정상 학습·whole-board 640×512 축소 baseline이 작은 부품 누락을
  최종 판정할 수 없다는 실측 반례다. 결과는 개발 참고용이며 합격 신호로 쓰지
  않는다.
- RTX GPU 추론까지 정상 완료했으며 로봇·컨베이어 명령은 전송하지 않았다.

## 2026-09-01 — S22 하이브리드 무인 AOI 조합 고정

- D435 영상으로 학습한 팀원 Segmentation은 S22 AOI의 필수 의존성에서 제외했다.
  S22 입력으로 재학습된 모델만 선택 provider로 연결할 수 있으며, 외부 모델이
  없거나 성능이 낮아도 나머지 검사 단계는 계속 실행하는 구조로 고정했다.
- 공식 순서는 촬영 품질 gate, 1600×1266 기판 원근 정합, 25슬롯 유무·중심·각도,
  GPU/HBM 흰점과 부품별 비대칭 특징 방향 확인, 흰 핀/고해상도 슬롯 외관 검사,
  strict-normal 전체 기판 이상탐지, 결과 융합이다.
- S22 Segmentation·S22 OBB·슬롯 제한 기하 후보와 PatchCore·FR-PatchCore를 동일
  provider 계약 아래 교체할 수 있다. 단 FR-PatchCore는 외관 이상 보조에만 쓰며
  검출 대상인 슬롯 상대 위치·방향 오류를 정합으로 제거하면 안 된다.
- 검증되지 않았거나 신뢰도가 낮은 모델은 `ADVISORY_ONLY`로 남겨 최종 PASS/FAIL
  권한을 주지 않는다. 모든 필수 검사가 보정되고 PASS여야 최종 PASS이며, 필수
  결과가 없거나 충돌·저신뢰이면 `UNKNOWN`으로 자동 재촬영한 뒤 재시도 초과 시
  `NG_UNCERTAIN`/라인 정지한다. 목표 운영에는 사람 육안 판정을 포함하지 않는다.
- 이 결정은 strict v5의 정상 `0.39559~0.51147`과 미세 변화
  `0.42534~0.74627` 점수 중첩 및 전체 PatchCore 단독 판정 한계를 근거로 한다.
  정상 학습 데이터에는 검수된 정상 조립 S22 촬영만 허용한다.
- `vision_assembly/config/inspection_fusion_contract.json`과 검사 README에 설계
  계약을 저장했다. 아직 모든 provider와 최종 fusion runtime을 구현했다는 의미는
  아니며, 이번 작업 중 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-02 — S22 6클래스 Instance Segmentation 파이프라인 준비

- `s22_hybrid_aoi_v1`의 비어 있던 부품 유무·중심·각도 provider를 위해 D435 자료와
  분리된 S22 전용 촬영, 폴리곤 라벨링, 장면 단위 분할, YOLO26n-Seg 학습 및 단일
  ROI 추론 도구를 추가했다. 대상은 GPU 1, HBM 8, Power Module 4, VRM 5,
  Inductor 2, SMD Capacitor 5다.
- 촬영 자료는 3.5배 광학 원본에서 보정한 `1600×1266` 기판 ROI이며 새 파일 여부,
  SHA-256 중복, 해상도와 선명도를 확인한다. board state, scene, 예상 visible count와
  원 촬영 metadata를 손실 없이 함께 보관한다.
- Segmentation mask는 부품 몸체만 포함하고 소켓·그림자·GPU/HBM 핀·흰 방향점은
  제외한다. 핀과 방향점은 고정 검사 계약대로 후속 고해상도 특징검사에서 독립적으로
  판단한다. 라벨 UI는 우측 패널을 사용하고 정상 25개 count guard, 이전 사진 label
  복사와 커서 위치 polygon 삭제를 제공한다.
- 검수 완료 이미지에 한해 동일 scene 전체를 같은 split에 넣으며 malformed polygon,
  범위 초과, 퇴화 mask, 누락 클래스는 dataset build를 중단한다. 학습 기본값은
  `yolo26n-seg.pt`, 1280px, batch 4, 150 epochs, flip 없음과 약한 정합 오차
  augmentation이다.
- 추론 결과는 mask·중심·클래스 수량 화면과 provider-contract JSON으로 저장한다.
  슬롯 매칭과 통제 불량 검증 전에는 모든 검출을 `slot_id=null`, `UNKNOWN`,
  `ADVISORY_ONLY`로 출력해 최종 합불에 연결하지 않는다.
- 테스트는 단위 `3 passed`, 임시 10장/6클래스 dataset의 장면 분리
  `train 8 / val 2`, YOLO26n-Seg `3,126,280 parameters`, 최신 ROI 임시 보관
  선명도 `77.54`를 확인했다. 공식 사전학습 가중치 6.4 MB도 준비했다. 신규 S22
  실촬영·라벨·GPU 학습·슬롯 tolerance 연결은 아직 남았고, 로봇·컨베이어 명령은
  보내지 않았다.

## 2026-09-02 — S22 UI 수동 Segmentation 촬영 세션

- `run_capture_s22_segmentation_manual.sh`를 추가해 S22 Samsung Camera를 노트북
  scrcpy 조작창으로 직접 촬영하고, 창 종료 후 세션 중 새로 생긴 JPEG만 USB로
  일괄 가져오도록 했다. 관리형 overview는 촬영 동안 pause/resume하며 카메라
  동시 점유를 방지한다.
- 촬영 조건은 실제 3배 망원렌즈 기반 3.5배 프레이밍과 플래시 OFF로 preset한다.
  가져온 사진은 EXIF 35mm 환산 60mm 이상 검증, `1600×1266` ROI 원근 보정,
  SHA-256 중복 검사, scene/board-state/예상 count metadata 등록을 통과해야
  라벨링 원본이 된다. 원본 4000×3000 JPEG도 runtime 세션 폴더에 보존한다.
- 한 세션은 움직이지 않은 한 물리 배치의 2~3장만 포함하고, 배치를 바꾸면 scene을
  바꾸는 규칙을 README에 명시했다. `--label-after`로 기존 폴리곤 라벨러를 바로
  실행할 수 있다.
- shell 문법과 도움말만 검증했으며 실기 촬영은 수행하지 않았다. 모델은 슬롯
  매칭·통제 불량 검증 전 `ADVISORY_ONLY`이고 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-02 — 수동 S22 정상 scene 14장 등록

- 최초 UI 종료 시 scrcpy의 non-zero 종료 상태가 `set -e`를 작동시켜 import를
  건너뛴 원인을 수정했다. 이후에는 viewer 종료 코드가 아니라 세션 전·후 DCIM
  목록 차이와 유효 JPEG 수로 import 성공을 판정한다.
- 휴대폰의 신규 14장을 복구해 모두 `4000×3000`, 7.0mm/69mm-equivalent 망원
  원본임을 확인했다. flash fired 5장과 no-flash 9장은 같은 부품 배치를 공유하므로
  train/val 누수를 막기 위해 `normal_pose_01` 한 scene에 두고 각 metadata에 EXIF
  flash 값을 기록했다.
- 14/14 사진에서 `1600×1266` 기판 ROI가 생성됐고 rectangularity는
  `0.908~0.910`, sharpness는 `75.68~125.24`였다. 정상 25부품 조건으로 라벨링
  대기열에 등록하고 UI를 실행했다. 테스트 `3 passed`; 모델은 계속
  `ADVISORY_ONLY`이며 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-02 — SAM2 박스 프롬프트 라벨링 보조

- S22 6클래스 라벨러에 SAM2.1 Tiny의 box prompt를 추가했다. 부품 몸체를 왼쪽
  드래그하면 mask를 생성하고 prompt 주변 연결 contour를 단순화해 YOLO polygon으로
  넣는다. 짧은 클릭 수동 polygon, `D` 삭제, `U` undo와 기존 25개 count guard는
  유지한다.
- CUDA 자동 선택과 CPU fallback을 구현했고 공식 74.5MB 가중치는 Git 제외 로컬
  경로에 저장했다. HBM, VRM, SMD, Inductor 실제 ROI 시험에서 각각 17, 13, 13,
  25점의 유효 외곽선이 생성됐으며 작은 SMD와 검정색 VRM도 분할했다.
- 자동 생성 결과는 반드시 사람이 라벨 데이터로 검수하며 소켓·그림자·GPU/HBM
  핀·흰 방향점을 포함하면 삭제 후 재드래그하거나 수동 보정한다. 이는 개발 데이터
  작성 보조 기능이며 생산 PASS/FAIL 권한과 무관하다. 테스트 `5 passed`; 로봇·
  컨베이어 명령은 보내지 않았다.

## 2026-09-02 — 잘못된 기판 위치 scene 격리

- 사용자 확인에 따라 잘못된 기판 위치로 촬영한 `normal_pose_01` 14장을 활성
  S22 Segmentation 데이터에서 제외했다. label/review가 생성되기 전이었으며 이미지,
  metadata와 변경 전 manifest는 삭제하지 않고 runtime quarantine에 보존했다.
- 활성 images와 해당 scene manifest record가 모두 0개임을 확인했다. 재촬영
  import는 사진별 EXIF flash 값을 metadata notes에 자동 기록해 일반/발광 조건을
  구분한다. 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-02 — 올바른 위치 S22 scene 12장 등록

- 재배치 후 S22 3.5배 촬영 12장을 contact sheet로 확인하고
  `normal_correct_pose_01`에 등록했다. no-flash 6장, EXIF flash fired 6장이며
  모두 4000×3000, 7.0mm/69mm-equivalent 실제 망원 원본이다.
- ROI 생성은 12/12 성공했고 rectangularity `0.907~0.909`, sharpness
  `71.29~110.47`였다. 이전 잘못된 14장은 활성 데이터와 섞이지 않고 quarantine에
  남아 있다.
- 수동 세션 완료를 scrcpy 창 상태에만 의존하지 않고 실행 터미널 Enter로 명시할
  수 있게 수정했다. Enter 입력 시 viewer만 종료한 후 신규 DCIM import와 라벨러
  실행을 계속한다. 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-02 — 라벨러 클래스 선택 키·패널 보강

- OpenCV 창에서 숫자키가 GPU 클래스에 고정되는 실기 문제를 반영해 `waitKeyEx`로
  상단 숫자와 X11 숫자패드 `0~5`를 모두 처리한다. 오른쪽 클래스 행을 클릭하는
  마우스 선택도 추가해 키보드 레이아웃과 무관하게 클래스를 바꿀 수 있다.
- 선택 시 `selected` 표시와 상태 메시지를 즉시 갱신한다. 저장 전 GPU polygon
  1개만 있던 기존 프로세스를 교체했으며 label/review 파일 손실은 없다. 로봇·
  컨베이어 명령은 보내지 않았다.

## 2026-09-02 — `normal_correct_pose_01` 라벨 검수 완료

- 일반 6장과 flash fired 6장 총 12장의 S22 ROI에 6클래스 polygon 라벨과
  COMPLETE review를 저장했다. 강제 count override는 없으며 12장 모두 클래스별
  `1/8/4/5/2/5`를 만족한다.
- 총 300 instance의 클래스별 합계는 GPU 12, HBM 96, Power Module 48, VRM 60,
  Inductor 24, SMD 60이다. 현재 자료는 한 physical scene group이므로 누수 방지상
  train/val로 분리할 수 없고 추가 scene 수집 후 dataset build를 진행한다.
- 모델 학습이나 로봇·컨베이어 명령은 수행하지 않았다.

## 2026-09-02 — 추가 정상 배치 6 scene 등록

- 추가 촬영 12장을 원근 보정해 비교한 결과, 일반광/플래시 한 쌍씩 구성된 서로
  다른 6개 물리 배치였다. 데이터 누수 방지를 위해 각 쌍을
  `normal_correct_pose_02~07`로 분리해 등록했다.
- 모든 ROI는 `1600×1266`, 기대 부품 수는 정상 구성 25개다. 측정 sharpness는
  일반광 `85.76~115.37`, 플래시 `64.73~80.35`로 일반광 쪽이 더 높았다.
- 현재 활성 데이터는 images/metadata 24개, 완료 labels/reviews 12개이며 신규
  12장은 미라벨 상태다. 모델 학습 및 로봇·컨베이어 명령은 수행하지 않았다.

## 2026-09-02 — 추가 정상 배치 라벨 검수 완료

- `normal_correct_pose_02~07` 12장 모두 25개 polygon과 `COMPLETE` review를
  저장했다. 사진별 클래스 수는 `1/8/4/5/2/5`이며 강제 count override는 없다.
- 전체 활성 S22 Segmentation 데이터는 image/label/review 각각 24개, 물리 scene
  7개, 총 polygon 600개가 됐다. 데이터셋 build·학습 및 로봇·컨베이어 명령은
  수행하지 않았다.

## 2026-09-02 — S22 Segmentation v1 학습·실사진 점검

- scene 누수 없이 train 18장/450 instance, val 6장/150 instance로 구성하고
  YOLO26n-seg를 RTX GPU에서 1280px, 150 epoch 학습했다. 전체 validation Mask
  P/R/mAP50/mAP50-95는 `0.799/0.841/0.914/0.864`다.
- 실제 최신 ROI에서 동일 부품 중복 후보를 확인해 same-class box IoU 후처리를
  추가했다. 출력은 42개에서 23개로 정리됐고 GPU/HBM/VRM/Inductor는 기대 수와
  일치했으나 Power Module 1개와 SMD 1개를 놓쳤다.
- 후보 모델은 `ADVISORY_ONLY`로 유지한다. 테스트 `5 passed`; 생산 판정 및 로봇·
  컨베이어 명령은 수행하지 않았다.

## 2026-09-02 — 클래스 threshold와 25-slot 매칭 적용

- 동일 train ROI 누락 원인은 PM `0.185`, SMD `0.146`이 공통 `0.20` threshold에서
  탈락한 것이었다. raw floor `0.01` 뒤 PM/SMD `0.10`, 나머지 `0.20`의 클래스별
  문턱과 Unity+물리 override 기반 25개 고정 슬롯 매칭을 적용했다.
- 같은 클래스 중복은 IoU로 제거하고, 슬롯 허용 범위 안 가장 가까운 후보 하나만
  채택한다. 25개 슬롯 모두 provider-contract `slot_id`를 출력하며 미검출은 PASS가
  아닌 `UNKNOWN`으로 남긴다.
- 외곽점 평균 중심을 면적 모멘트 중심으로 고쳤고 화면 중심 마커는 제거했다. 같은
  ROI에서 클래스 수 `1/8/4/5/2/5`를 확인했다. 테스트 `7 passed`; 모델 권한은
  `ADVISORY_ONLY`, 로봇·컨베이어 명령은 수행하지 않았다.

## 2026-09-02 — VRM 고정 슬롯 존재 분류 준비

- 정상 조립만 학습한 Segmentation이 실제로 빈 VRM 소켓도 VRM으로 검출했다.
  질감·미세 색상 차를 원본 슬롯 crop에서 학습하는 `PRESENT/EMPTY` 분류기를
  주 provider로 올리고, Segmentation/OBB는 advisory 후보로 내리도록 융합 계약을
  보강했다. 미검증 모델은 `UNKNOWN/ADVISORY_ONLY`이며 단독 PASS/FAIL을
  만들지 않는다.
- `run_capture_vrm_presence.sh --all-present` 또는 `--empty vrm_XX`로 표준 S22 ROI의
  VRM 5-slot crop과 명시적 정답 manifest를 저장하는 수집기를 추가했다. 정확히 같은
  ROI hash는 중복 등록하지 않고, 유효하지 않은 슬롯 ID는 fail-closed로 중단한다.
- 유닛 테스트 `2 passed`, 임시 ROI로 `present 4 / empty 1` crop 및 preview/manifest
  생성을 확인했다. EfficientNet-B0는 빠른 전이학습 baseline이며 실물 scene
  분리 검증에서 EfficientNetV2-S 등과 비교한 후 최종 모델을 정한다. 실제 학습
  데이터·모델은 아직 없으며 로봇·컨베이어 실제 명령도 수행하지 않았다.

## 2026-09-02 — 고정 25-slot 하이브리드 AOI 런타임

- 4모듈을 `vision_assembly/hybrid_inspection/`에 구현했다. 입력 보드를 호모그래피·ECC로
  표준 `1600×1266` 프레임에 정합하고 YOLO 유무와 관계없이 Unity+실물 override
  25슬롯을 모두 crop한다. 존재 분류기→위치·방향→PatchCore의 필수 stage를
  `PASS/FAIL/UNKNOWN`으로 융합하며, authoritative FAIL만 FAIL을 만들고 모든 필수
  stage의 authoritative PASS가 있어야만 PASS를 발행한다.
- 원본 S22 색상을 존재 분류기·YOLO·PatchCore에 그대로 제공하고 OpenCV 국소
  검사에만 grayscale CLAHE `2.0/(8,8)`를 사용한다. GPU/HBM 흰점·핀과
  Inductor 검정 마커 각도를 독립 evidence로 구현했다. 실사진 오류 후보를
  발견했지만 통제 검증 전이므로 advisory를 유지한다.
- Anomalib 2.6 부품별 ckpt와 학습 crop 방향을 재사용했다. 부품별 통제 불량
  `pass_max/fail_min`이 없으면 임의 `0.5` 판정 대신 score·heatmap+
  `UNKNOWN`을 출력한다. 추론 시 timm의 불필요한 외부 weight 재조회도 차단했다.
- 실제 최신 ROI 드라이런은 alignment `0.971996`, 25-slot, `UNKNOWN 25`로 종료했다.
  테스트 `12 passed`; 샌드박스 CUDA 격리로 실제 GPU 추론은 현장 노트북 재검증이
  필요하다. 존재 분류기와 통제 PatchCore 임계값이 없어 아직 생산 PASS는 발행할
  수 없다. 로봇·컨베이어 실제 명령은 수행하지 않았다.

## 2026-09-02 — 검사 증거 3패널 UI·절대 heatmap 기준

- 25-slot이 모두 `UNKNOWN`으로 보이고 각 슬롯 이상 map이 독립 정규화되어
  정상 부위까지 화려하게 보이던 문제를 재현했다. 기존 색은 슬롯 내
  상대값일 뿐 슬롯 간 불량 강도 비교에 사용할 수 없었다.
- 사람이 증거 위치를 빠르게 개발 검수할 수 있도록 `정합 원본 / PatchCore
  초과 영역 / 합성 overlay` 3패널을 기본 `hybrid_report.png`로 변경했다.
  부품별 정상 검증셋 anomaly pixel `p99.9`를 초과한 부위만 절대 스케일
  Turbo 색으로 표시하며, 검정 배경 map과 원본 overlay를 따로 저장한다.
- 개발 후보는 `DIR?/MISSING?`, `POSE?`, `SURFACE?`로 분리했고 화면과
  JSON에 `ADVISORY_ONLY`, `confirmed_defect=false`를 명시했다. 이는 튜닝을
  위한 증거 표시이며 무인 운영의 authoritative 판정 권한이 아니다.
  고정 융합 계약의 fail-safe `PASS/FAIL/UNKNOWN` 규칙은 변경하지 않았다.
- provider 비활성 드라이런 alignment `0.971996`, 증거 후보 3개,
  신규 PNG·JSON 생성과 테스트 `7 passed`를 확인했다. CUDA PatchCore 전체
  재실행 결과는 노트북에서 추가 확인이 필요하다. 로봇·컨베이어
  실제 명령은 수행하지 않았다.

## 2026-09-02 — VRM 3상태 고정 슬롯 provider 데이터 수집

- 현재 VRM 누락·회전 배치를 플래시 on/off로 실제 GPU 검사했다.
  플래시에서 alignment가 `0.971996→0.937809`, advisory 후보가 `22→25`로
  악화되고 VRM 5개 score가 모두 `1.0`이 되어, 현재 학습·임계값에는
  사용할 수 없음을 확인했다. VRM 상태 분류는 ambient S22로 고정한다.
- 5-slot `EMPTY/CORRECT/ROTATED` 명시 라벨 수집기를 추가했다. 중복
  source hash, 잘못된 slot ID, empty/rotated 겹침을 거부하고 미리보기·crop·
  scene/illumination/label authority manifest를 함께 저장한다.
- 첫 실물 scene `vrm_state_ambient_01`은 당시 VRM04 회전·VRM05 정상으로
  기록했으나, 2026-09-04 원본·preview·Unity 방향 재감사에서 두 라벨이
  뒤바뀐 것을 확인했다. 실제 정답인 `vrm_01 EMPTY`, `vrm_05 ROTATED`,
  `vrm_02/03/04 CORRECT`로 crop과 manifest를 교정했다. 클래스 count는
  empty 1, rotated 1, correct 3으로 동일하다.
- EfficientNet-B0 학습·TorchScript export와 물리 scene holdout을 구현했다.
  클래스별 최소 4 scene guard, 모든 클래스가 train/validation에 존재하는
  split, 회전·flip 금지, class-weighted loss, macro/per-class recall을 사용한다.
  현재 1 scene이므로 학습을 거부했고 임의 모델은 만들지 않았다.
- 향후 model/metadata가 생기면 하이브리드 존재·방향 stage에
  `EMPTY/CORRECT/ROTATED`를 나눠 전달하도록 런타임을 연결했다. 검증 전
  권한은 `ADVISORY_ONLY`이며 단독 생산 PASS/FAIL을 만들지 않는다.
  테스트 `16 passed`; S22 촬영 외 로봇·컨베이어 실제 명령은 없었다.

## 2026-09-02 — VRM state ambient scene 02

- 플래시 off S22 망원 촬영(`4000×3000`, 69 mm 환산), ROI rectangularity
  `0.908`를 확인했다.
- `vrm_02 EMPTY`, `vrm_05 ROTATED`, `vrm_01/03/04 CORRECT`를 미리보기로
  검수한 후 scene 02로 등록했다. 누적은 2 physical scenes, 10 crops,
  `empty 2 / rotated 2 / correct 6`이다.
- 데이터 최소 조건 미달로 학습은 수행하지 않았다. 로봇·컨베이어
  실제 명령은 없었다.

## 2026-09-02 — VRM state ambient scene 03

- 플래시 off `4000×3000` S22 망원 입력에서 ROI rectangularity `0.909`를
  확인했다.
- `vrm_03 EMPTY`, `vrm_01 ROTATED`, `vrm_02/04/05 CORRECT`를 미리보기로
  검수하고 scene 03으로 등록했다. 누적 3 scenes/15 crops,
  `empty 3 / rotated 3 / correct 9`이다.
- 최소 scene 수와 전 슬롯 순환이 완료되지 않아 학습은 보류했다.
  로봇·컨베이어 실제 명령은 없었다.

## 2026-09-02 — VRM state ambient scene 04

- 플래시 off ROI rectangularity `0.908`, `vrm_04 EMPTY`, `vrm_02 ROTATED`,
  `vrm_01/03/05 CORRECT`를 미리보기로 확인하고 scene 04로 등록했다.
- 누적 4 scenes/20 crops, `empty 4 / rotated 4 / correct 12`로 최소 guard는
  충족했다. 다만 다음 scene에서 vrm_05 empty/vrm_03 rotated를 추가해 슬롯
  편향을 줄인 뒤 학습하기로 했다.
- 학습·모델 교체·로봇·컨베이어 실제 명령은 없었다.

## 2026-09-02 — VRM state v2 입력 계약 통일·후보 모델 검증

- scene 05를 `vrm_05 EMPTY`, `vrm_03 ROTATED`, 나머지 3개 CORRECT로
  명시 등록해 총 5 physical scenes/25 crops를 확보했다. 2026-09-04 사후
  라벨 감사 결과 EMPTY는 5개 슬롯을 한 번씩 포함하지만 ROTATED는
  VRM01/02/03이 한 번, VRM05가 두 번이고 VRM04가 없었던 것으로 정정했다.
  VRM04 회전 coverage는 이후 독립 scene `vrm04_90ccw_20260904_1637`로
  보완했으며, 잘못된 ambient-01 라벨로 학습된 당시 v2는 별도 백업 후
  교정 데이터 기반 v6으로 교체했다.
- 최초 v1 EfficientNet-B0는 저장 crop 전체 deterministic accuracy가
  `24/25`였지만 scene별 최고 확률이 낮았고(`0.372~0.828`), 하이브리드
  runtime의 scene 05는 `0.427~0.621`로 전부 low-confidence UNKNOWN이었다.
  임의 threshold 완화 대신 입력 불일치와 checkpoint 선택을 수정했다.
- `vrm_state_common.py`에 전역 정합 보드 기준 sub-pixel crop 계약
  `registered_board_getRectSubPix_margin0.24_square256_v2`를 정의했다. 수집기와
  runtime은 이 함수를 공유하며, model metadata의 crop pipeline ID가 다르면
  fail-closed UNKNOWN을 반환한다. 기존 v1 원본/라벨은 유지하고 동일한
  5개 source ROI를 v2로 재처리했다.
- 같은 macro recall에서는 validation loss가 더 낮은 checkpoint를 선택하도록
  학습기를 고쳤다. scene 04 holdout에서 3-class recall `1.0/1.0/1.0`, 정답
  확률 min/mean `0.8520/0.9476`; train deterministic accuracy `1.0`, 정답
  확률 최저 `0.9690`을 기록했다.
- 실제 통합 crop 경로 재검증에서 train scene 05는 CORRECT/CORRECT/ROTATED/
  CORRECT/EMPTY를 신뢰도 `0.9844~0.9997`로, unseen holdout scene 04는
  CORRECT/ROTATED/CORRECT/EMPTY/CORRECT를 `0.8770~0.9984`로 맞혔다.
  v2를 기본 `models/vrm_state.*`로 승격하고 v1은
  `models/vrm_state_v1_backup/`에 보존했다. evidence JSON에는 threshold 전
  raw class와 3-class 확률을 함께 남긴다.
- 5장면/홀드아웃 1장면은 생산 검증으로 부족하므로 authority는
  `ADVISORY_ONLY`, `validated=false`를 유지한다. 다른 provider를 비활성화한
  VRM 분리 검증에서 board `UNKNOWN`은 의도된 fail-safe 결과다. 추가 실물·조명
  조건에서 독립 confusion matrix와 오검출률을 확정하기 전까지 이 모델은
  단독 PASS/FAIL을 만들 수 없다.
- 테스트 `16 passed`, Python compile, JSON parse, launcher shell syntax를
  확인했다. 로봇·컨베이어 실제 명령은 수행하지 않았다.

## 2026-09-02 — S22 fresh capture 기반 전체 하이브리드 검사 실행기

- `run_s22_live_hybrid_inspection.sh` 하나로 현재 S22 화면의 새 광학 사진 촬영,
  PCB ROI 추출, 25-slot hybrid inspection을 순서대로 실행하도록 통합했다.
  fresh ROI의 실제 symlink target이 이전과 같으면 검사를 거부하며, 기본은
  flash off/3.5x다. 전체 검사가 기본이고 `--skip-yolo`, `--skip-patchcore`는
  진단용으로만 전달한다.
- 실기 검증은 `4000×3000`, focal 7.0mm, 35mm equivalent 69mm, flash off로
  촬영했다. ROI rectangularity `0.907`, hybrid alignment `0.983396`이며
  25개 슬롯 클래스 수 `1/8/4/5/2/5`를 모두 처리했다. managed overview는
  capture 동안 pause된 뒤 정상 복구됐다.
- GPU/HBM/Inductor/Power Module/SMD/VRM PatchCore 6개 모델을 CUDA에서
  실제 추론했고 최신 3패널 PNG와 JSON을 생성했다. 최종 `UNKNOWN`, advisory
  candidate 15, `confirmed_defect=false`다. 많은 `SURFACE?` 후보는 현재
  정상 기준과 실사진 분포가 아직 충분히 검증되지 않았음을 뜻하며 확정 불량이
  아니다.
- launcher shell syntax와 실제 end-to-end 완료를 확인했다. 로봇·컨베이어
  실제 이동 명령은 수행하지 않았다.

## 2026-09-02 — 비VRM 고정 슬롯 존재 데이터 수집기

- 최신 25-slot report에서 VRM 외 20개 슬롯의 presence stage가 전부 model/
  validation metadata missing임을 확인했다. 같은 report의 advisory code는
  `DIR? 2`, `MISSING? 1`, `POSE? 6`, `SURFACE? 13`이어서, 다음 우선순위를
  PatchCore 시각 임계값이 아닌 명시적 PRESENT/EMPTY provider로 정했다.
- 새 수집기는 fresh flash-off S22 ROI를 기준 프레임에 정합하고 GPU 1/HBM 8/
  PM 4/Inductor 2/SMD 5 총 20개 슬롯을 deterministic `256×256` crop으로
  저장한다. slot ID, component type, crop pipeline, alignment, illumination,
  명시 라벨 권한과 로봇·컨베이어 명령 여부를 manifest에 남긴다.
- 실제 빈 슬롯만 `--empty`에 지정하며 방향·핀·표면 결함은 presence label을
  바꾸지 않는다. unknown slot, duplicate source, low alignment, flash input은
  저장 전에 거부한다. 과거 random defect 사진은 슬롯별 정답이 없어 재사용하지
  않았다.
- 관련 전체 테스트 `19 passed`, compile/shell/help 검증을 통과했다. 데이터
  수집과 모델 학습은 아직 시작하지 않았고 로봇·컨베이어 명령은 없었다.

## 2026-09-02 — 비VRM presence 라벨 정정

- 실물 배치 확인에 따라 `component_presence_scene_20260902_192359_989158`의
  `hbm_01`을 EMPTY에서 PRESENT로 정정하고 crop 파일도 PRESENT 경로로
  이동했다. 이 장면의 실제 EMPTY는 `power_module_01` 하나다.
- manifest와 crop 경로의 일치를 확인했으며 로봇·컨베이어 명령은 없었다.

## 2026-09-02 — 비VRM 20슬롯 presence 1차 coverage 완료

- GPU 1/HBM 8/Power Module 4/Inductor 2/SMD 5의 전체 20슬롯에 대해 최소 1개
  EMPTY 장면을 확보했다. 현재 `component_presence_v1`은 23 scenes/460 records다.
- SMD 01~05의 단독 EMPTY 장면과 전체 EMPTY slot ID 20/20을 manifest에서
  확인했다. 단, GPU 등 일부 EMPTY 표본은 1장뿐이므로 학습·독립 검증 전이며
  authority 승격 없이 수집 단계로 유지한다.
- S22 촬영 중 overview pause/resume만 있었고 로봇·컨베이어 명령은 없었다.

## 2026-09-02 — presence 혼합 장면 수집 검증

- 9개 혼합 EMPTY 장면을 추가해 `component_presence_v1`을 32 scenes/640 records로
  확장했다. contact sheet로 실제 빈 슬롯과 manifest 라벨의 일치를 확인했다.
- class별 E/P crop은 GPU 10/22, HBM 17/239, PM 14/114, Inductor 11/53,
  SMD 9/151이다. 동일 실물·동일 날짜 데이터이므로 별도 holdout 전까지 모델은
  ADVISORY_ONLY를 유지해야 한다. 로봇·컨베이어 명령은 없었다.

## 2026-09-02 — component presence 후보 모델 runtime 연결

- scene-split EfficientNet-B0 모델 5개를 CUDA로 학습했다. 시각 감사로 혼합
  장면의 SMD 오라벨 5개를 EMPTY로 정정하고 SMD만 재학습했다.
- SMD holdout recall은 EMPTY/PRESENT 모두 1.0, 최저 정답 확률 0.9981이었다.
  최신 장면에서 실제 빈 `smd_capacitor_05`를 0.9999999 EMPTY, 나머지 SMD를
  0.997 이상 PRESENT로 판별했다.
- 수집·runtime crop pipeline을 동일하게 고정했고 mismatch는 UNKNOWN이다.
  모델은 독립 실물 검증 전 `ADVISORY_ONLY/validated=false`이며 로봇·컨베이어
  명령은 없었다.

## 2026-09-02 — all-present 신규 장면 검사

- 새 S22 all-present 사진에서 비VRM 20/20을 PRESENT로 맞혔으며 confidence는
  0.99398~0.99976이었다. VRM 02~05는 CORRECT, VRM 01은 CORRECT raw prediction
  0.7159로 threshold 미달 UNKNOWN이었다.
- 최종 UNKNOWN은 미검증 provider와 비활성화된 필수 단계에 따른 fail-safe이며
  presence 실패가 아니다. 로봇·컨베이어 명령은 없었다.

## 2026-09-02 — blind missing-component holdout 1

- 정답 비공개 새 장면에서 `inductor_02`, `power_module_01`,
  `smd_capacitor_03`, `vrm_02`를 EMPTY로 검출했고 사용자 사후 정답과 4/4
  일치했다. 비VRM EMPTY confidence는 0.9999996 이상, VRM 02는 0.9571이었다.
- 단일 blind scene이므로 모델은 계속 ADVISORY_ONLY이며 로봇·컨베이어 명령은
  없었다.

## 2026-09-02 — blind missing-component holdout 2

- 정답 비공개 장면에서 GPU/HBM 04·06/Inductor 01/PM 03/SMD 01/VRM 01·05를
  EMPTY로 검출했고 사후 정답과 8/8 일치했다. 비VRM confidence 0.99979 이상,
  VRM EMPTY confidence 0.9544 이상이었다.
- 학습 데이터에는 추가하지 않았고 authority는 ADVISORY_ONLY다. 로봇·컨베이어
  명령은 없었다.

## 2026-09-02 — blind orientation/pose 검증

- OpenCV 방향은 HBM 04 180°와 Inductor 01 90°/02 180°를 검출했지만 GPU
  180°는 UNKNOWN, VRM 05 90°는 EMPTY로 오분류했다.
- YOLO segmentation mask에 회전 사각형을 맞춘 auxiliary pose는 HBM 06·08
  미세 회전, PM 03 미세 회전/이동, SMD 01
  이동과 두 Inductor 회전을 실제 정답대로 OUTSIDE_LIMIT 후보로 검출했다.
- GPU/HBM 180°는 segmentation mask 장축만으로 구분할 수 없고 VRM pose 후보도 없으므로
  별도 방향 state provider가 필요하다. 로봇·컨베이어 명령은 없었다.

## 2026-09-02 — rotated-scene PatchCore 확인

- 기존 PatchCore는 GPU 180° 0.9866, HBM 04 180° 0.9963, VRM 05 90° 및 두
  Inductor 회전에 1.0으로 반응해 방향 anomaly 가능성을 확인했다.
- 정상 PM 01도 1.0이었고 HBM 미세 회전/정상 score가 역전되는 사례가 있어 현재
  모델·score는 단독 판정에 사용할 수 없다. fixed-slot strict-normal 재학습과
  controlled defect threshold 검증 전까지 ADVISORY_ONLY다. 로봇·컨베이어
  명령은 없었다.
## 2026-09-03 — S22 strict-normal capture set completed

- Confirmed 14 user-approved, fully assembled S22 captures (3.5x optical, flash off), including `s22_inspection_roi_20260903_102613.png`.
- Capture distribution: two evening images from 2026-09-02 and twelve morning images from 2026-09-03, providing limited ambient-light variation.
- Contact-sheet review found no obvious missing or reversed component. Existing automatic pose checks were not used for promotion because the expected slot centres still have a systematic offset against the current physical board.
- The source captures remain preserved as strict-normal PatchCore retraining candidates. Any resulting model remains `ADVISORY_ONLY` until controlled-defect validation and threshold calibration are complete.
- No robot or conveyor motion command was issued.

## 2026-09-03 — Fixed-slot strict-normal PatchCore v4 candidate

- Built `pcb_components_strict_v4` from 14 reviewed complete boards: 11 training boards and three time-separated normal holdouts. Crops use fixed slot coordinates and original RGB, with no pose normalization or CLAHE.
- Added only the ten user-identified manipulated slots from `s22_inspection_roi_20260902_211811.png` as controlled defects; unchanged slots were excluded from defect labels.
- Trained all six component-type PatchCore candidates under `runtime/inspection/patchcore/pcb_components_strict_v4`. Exploratory AUROC was GPU 0.50, HBM 1.00, Inductor 0.60, Power Module 1.00, SMD about 1.00, and VRM 0.875. Defect sample counts remain too small for authority.
- The controlled orientation scene produced anomaly evidence at the main manipulated regions, but relative per-component heatmap scaling still highlights some normal parts and the GPU score scale is unstable. The runtime default and decision thresholds were therefore not changed; v4 remains `ADVISORY_ONLY`.
- No robot or conveyor command was issued.

## 2026-09-03 — Full saved-model audit on current S22 scene

- Re-ran 50 saved trained artifacts under the flash-off S22 contract: seven YOLO best checkpoints, 30 PatchCore checkpoints, and 13 TorchScript presence/VRM-state files. The complete evidence is in `runtime/inspection/model_audit_20260903/README.md`.
- Registration scored 0.9866. Fixed-slot segmentation counted GPU 1, HBM 8, Power Module 4, VRM 4, Inductor 2, and SMD 5, correctly leaving the physically empty `vrm_03` unmatched. VRM state v2 independently classified `vrm_03` as EMPTY at 0.9838 confidence.
- All six tray/Unity OBB best models returned zero detections on the assembled S22 board, confirming that those domain-specific models are not assembly AOI providers.
- Five whole-board and six GPU-specific PatchCore generations were cross-tested on one independent normal, two real scratched-GPU captures, and the current scene. Older models saturated; newer models had overlapping or inverted normal/crack scores. The dedicated crack model returned 1.0 for every sample and retained its failed AUROC 0.5 result. No saved model localized only the physical scratch reliably.
- Classical full-board and package-leg checks detected some real GPU leg evidence but also failed normal HBM/Power Module slots. Hybrid fusion therefore remained UNKNOWN with 13 advisory candidates.
- No authority or threshold was changed. All unverified learned providers remain ADVISORY_ONLY. No robot or conveyor motion command was issued.

- The 4000×3000 S22 source contains only about 1240×980 projected board pixels; the 1600×1266 registered ROI is an interpolation enlargement, so recropping the source cannot recover additional crack detail.
- CLAHE, unsharp, black-hat, and edge diagnostics on the GPU face showed the 3D-print diagonal layer texture more strongly than the putative micro-crack. The normal and defective GPU are also different printed instances, making instance texture a stronger anomaly than the crack.
- Unknown-location black-on-black micro-crack inspection remains `UNKNOWN/ADVISORY_ONLY` under the current fixed frontal lighting. Grazing or multi-illumination acquisition is required before claiming reliable crack authority.

## 2026-09-03 — GPU interior crack PatchCore v1 experiment

- Built a normal-only GPU interior dataset with 14 training normals and nine normal holdouts. Two recent physical crack captures were excluded from training and used only as blind `test/crack` samples.
- Trained a higher-resolution PatchCore candidate using `layer1/layer2` features.
- Exploratory image AUROC was 0.5 and F1 was 0.364. Heat localized broadly to pin boundaries and printed surface texture rather than the physical micro-crack.
- The candidate was not wired into hybrid inspection and has no decision authority. Current limitations are insufficient black-on-black crack contrast/pixel width and imperfect interior masking.
- No robot or conveyor command was issued.

- Independent restored-normal GPU validation did not generalize: geometry was within tolerance (0.612 mm position error and 0.37-degree angle error), but PatchCore scored 0.644 versus held-out-normal p99 0.468. The internal AUROC/F1 of 1.0 therefore did not translate into acceptable normal false-positive behavior.
- Five repeated captures of the unchanged independent normal placement scored 0.597–0.652; all exceeded normal p99 0.468. This is a systematic generalization failure rather than one noisy frame. The 53 controlled defects span 0.500–1.000, so normal and defect scores overlap and no scalar threshold can safely separate them.
- GPU position/angle must therefore come from fixed-slot geometry and direction from the white-dot feature. PatchCore remains advisory evidence for surface/pin appearance only, not a GPU pose/orientation decision provider.

## 2026-09-03 — Suppressed uncalibrated SMD surface overlay

- The current SMD PatchCore normal pixel p99.9 is only 0.011, causing compression noise and reflections to appear like fine cracks.
- SMD PatchCore scores and raw evidence remain in JSON, but SMD heat and `SURFACE?` candidates are hidden from the operator overlay until normal/defect thresholds are independently recalibrated. Presence and pose providers remain active.
- GPU black-package micro-cracks are assigned to a separate high-resolution interior-surface ROI model; the current general component PatchCore is not granted crack authority without real crack validation samples.
- No robot or conveyor command was issued.

## 2026-09-03 — Depth-gated markerless SMD grasping

- Kept the ChArUco-free RGB size/color/contour detector and added robust local depth evidence from the aligned D435 stream: valid-pixel fraction, local median absolute deviation, inter-frame depth jitter, and Base-frame 3D jitter.
- The default acceptance limits are valid fraction >=0.55, local depth MAD <=2.0 mm, inter-frame depth jitter <=2.0 mm, and Base jitter <=0.5 mm over the requested stable frames. Rejected detections now exit nonzero without updating the target, preventing a previous coordinate from being reused as a fresh result.
- Approach and descent require a fresh target with `depth_quality.accepted=true`. Descent now computes one absolute final Base Z from the detected part Z instead of applying fixed 100 mm plus 5 mm moves; target age, XY alignment, depth quality, and computed descent range are fail-safe gates.
- Five Python files passed `py_compile` and four launch wrappers passed `bash -n`. The live ROS graph exposed only `/camera/camera/depth/image_rect_raw/compressedDepth`; color, CameraInfo, aligned raw depth, and robot state were absent, so no live detection or motion dry-run could be completed.
- No robot, gripper, or conveyor command was issued. The retained 5 mm below-surface TCP offset still requires a guarded low-speed physical calibration for the installed fingers, and no grasp-success sensor feedback exists yet.

## 2026-09-03 — SMD 50 mm alignment-approach mode

- Added `run_smd_approach_5cm.sh`: markerless RGB-D localization aligns the selected gripper tool axis to the detected part long axis, moves the TCP to detected Base Z +50 mm, and stops.
- Dedicated defaults are 20% horizontal, 15% vertical, and 20% rotation speed. The mode sends no gripper, grasp descent, lift, place, or teaching-point return command.
- Actual movement requires both `--execute` and `--confirm-approach-only` and is mutually exclusive with full-cycle confirmation. Static Python/shell checks were used; no robot, gripper, or conveyor command was issued.
- Hardened the dedicated wrapper against copied multiline commands whose indentation is preserved inside argument strings by trimming outer whitespace from forwarded arguments. The reported failure occurred during CLI parsing before camera subscription or any robot command.

## 2026-09-03 — GPU/HBM white-dot direction calibration

- Replaced the previous broad corner score with compact, circular connected-component selection inside constrained corner quadrants. This prevents package pin rows and the central white logo from outranking the physical direction dot.
- All 18 GPU normal candidates and five independent normal holdouts resolved as `lower_left/PASS`; all seven 180-degree GPU samples resolved as `upper_right/FAIL`.
- Position and small-angle defect samples intentionally remain direction-PASS when their dot stays in the correct corner. Fixed-slot geometry is responsible for those defect types.
- On the earlier physical HBM scene, all seven normal HBM slots passed and only reversed HBM 03 failed at the upper-right corner. Twelve regression tests passed; no robot or conveyor command was issued.
- Fixed the per-component override path so the pixel heatmap baseline now comes from the same override calibration as the component score baseline. GPU strict v4 remains `ADVISORY_ONLY` and cannot produce an automatic PASS or FAIL.

## 2026-09-03 — Fixed absolute PatchCore v4 heatmap

- Calibrated component score distributions and pixel p99.9 from the three held-out normal boards and saved them in the v4 `normal_calibration.json`.
- Removed per-frame/per-component min-max rendering from the standalone component visualizer. It now renders only response exceeding each component model's held-out-normal pixel p99.9 on one fixed excess scale.
- On the controlled orientation scene, the GPU 180-degree error produced a broad central response and HBM04/06/08, VRM05, and Inductor manipulations retained local evidence while most normal HBM, VRM, and SMD slots were suppressed. Power Module edges and Inductor background still need more data.
- Seven fixed-visualization regression tests passed. Decision thresholds and the runtime default were not changed; all v4 evidence remains `ADVISORY_ONLY`.
- No robot or conveyor command was issued.

## 2026-09-03 — Expanded controlled Inductor set and retraining

- Added five normal boards with both Inductors moved inside valid socket tolerance.
- Captured five examples per slot for 90/180/270-degree rotation and 19 outside-tolerance placements per slot. Four initial Inductor 02 placement captures were incorrectly tagged as slot 01; their manifests were corrected without changing source images and correction events were appended to the session index.
- Rebuilt strict v4 with 30 Inductor training-normal crops, eight normal holdouts, and 70 controlled defects, then retrained only the Inductor PatchCore candidate on the GPU. Exploratory image AUROC/F1 were 1.0/1.0.
- On the latest Inductor 02 placement holdout, normal Inductor 01 heat was suppressed while fixed excess heat localized to the displaced component outline and newly exposed socket boundary.
- The data remain dominated by one capture session, so the model stays `ADVISORY_ONLY` pending independent physical holdout validation. No robot or conveyor command was issued.

## 2026-09-03 — Independent Inductor blind validation

- A normal board produced Inductor 01/02 scores of 0.1999/0.1447, both below the held-out-normal p99 of 0.3091.
- For a second scene, the physical manipulation was withheld until after inference. The model identified Inductor 01 as normal (0.1851) and only Inductor 02 as anomalous (0.7128).
- The operator then revealed that Inductor 02 was centred but slightly rotated counter-clockwise. This matched the predicted anomalous slot, and fixed excess heat was localized to Inductor 02.
- One successful independent blind defect is useful evidence but not enough to grant authority across defect types and lighting. The model remains `ADVISORY_ONLY`, and PatchCore alone does not name pose versus orientation failure.
- No robot or conveyor command was issued.

- A further blind scene was predicted as anomalous in both slots: Inductor 01 scored 0.5961 and Inductor 02 scored 0.9662 versus the normal p99 of 0.3091.
- The operator then revealed a small upper-right displacement with near-normal orientation in slot 01 and an in-place 180-degree rotation in slot 02. Both manipulated slots were detected, with the 180-degree case receiving the larger score.
- Slot localization has matched both independent defect trials so far, but anomaly score alone is not used to name the defect type; geometry and marker evidence remain required for fusion.

- After restoring both Inductors to normal, an independent scene scored 0.1506/0.1316, again below the normal p99 of 0.3091, with fixed excess heat suppressed.
- The session sequence—normal, one subtle rotation, combined displacement plus 180-degree rotation, then restored normal—matched the physical state at every step. Inductor PatchCore v4 is therefore suitable as advisory anomaly evidence in fusion, but it is not granted standalone automatic decision authority.

## 2026-09-03 — Inductor PatchCore v4 wired into hybrid inspection

- Added a per-component PatchCore model-root override and wired only Inductor slots to `runtime/inspection/patchcore/pcb_components_strict_v4`; all other component PatchCore roots remain unchanged.
- Integrated validation on the independently restored-normal board produced Inductor 01/02 scores of 0.1504/0.1312, below normal holdout p99 0.3091, with registration score 0.9847.
- Reports now identify the default PatchCore root and every component-specific override root. Because controlled-defect decision thresholds are not yet promoted, Inductor surface evidence remains `UNKNOWN/ADVISORY_ONLY` and cannot independently produce PASS or FAIL.
- The existing auxiliary pose provider incorrectly reports the circular Inductor axis as 90 degrees. It remains advisory and cannot create an authoritative failure.
- All 12 relevant regression tests passed. No robot or conveyor command was issued.

## 2026-09-03 — GPU strict-v4 expansion and candidate retraining

- Reviewed 18 normal-orientation GPU captures spanning centre, cardinal, and corner placements inside the physical socket tolerance.
- Reviewed 52 physically possible controlled defects: 180-degree reversal, small clockwise/counter-clockwise rotation, and position outside tolerance in each cardinal direction. Impossible 90-degree placements were deliberately excluded.
- Rebuilt strict v4 GPU data as 25 train-normal, seven held-out normal, and 53 controlled-defect crops. GPU-only PatchCore retraining produced exploratory image AUROC/F1 of 1.0/1.0.
- Wired GPU, like Inductor, to the strict-v4 component model root in hybrid inspection. It remains `ADVISORY_ONLY` until an independent physical blind validation succeeds.
- No robot or conveyor command was issued.

## 2026-09-04 — Five-capture normal-board repeatability and PM display gate

- Excluded the first five-capture set from the normal baseline after the user disclosed that `hbm_04` was accidentally reversed. The white-dot provider correctly localized its dot at the upper-right and emitted `hbm_04 DIR?`.
- After restoring `hbm_04`, captured five fresh, unchanged normal boards at S22 3.5x telephoto with flash off (`20260904_101656`, `101724`, `101821`, `101851`, and `101935`). Every source was 4000x3000 at 69 mm full-frame-equivalent focal length. Board rectangularity was 0.908–0.909 and registration score was 0.9847–0.9869.
- Before the display adjustment, all five runs produced only one repeated advisory candidate: normal `power_module_02 POSE?`. Its angle error was 0.12–0.13 degrees and its residual position excess over the unchanged 0.75 mm CAD-plus-measurement allowance was 0.36–0.47 mm. The earlier user-confirmed displaced `power_module_01` control had 0.58 mm excess.
- Kept the underlying 0.75 mm pose limit and all raw JSON evidence unchanged. Raised only the unverified Power Module operator-candidate display excess from 0.30 to 0.50 mm. This removes the repeated normal overlay while retaining the known displaced control; it does not grant decision authority or alter the locked fail-safe fusion contract.
- Full rerun of the last normal capture scored 0.9869 alignment and produced zero advisory candidates. Final board status correctly remains `UNKNOWN` because required providers are not yet calibrated and authoritative.
- The user then created an independent controlled defect by shifting only PM02 left of its socket centre. The first measurement was 1.464 mm from nominal, 0.714 mm beyond tolerance. Because leaving the expected slot reduced auxiliary YOLO confidence to 0.138, the former display gate incorrectly hid the defect.
- Added a severe-displacement advisory route: a Power Module remains a `POSE?` candidate when the independent presence classifier reports `PRESENT` at >=0.90, auxiliary geometry remains available at >=0.10, and position excess is >=0.60 mm. This route remains `ADVISORY_ONLY` and has no automatic FAIL authority.
- Three independent captures of the unchanged PM02 control all produced PM02 as the sole `POSE?` candidate. Position error was 1.464–1.570 mm and presence confidence was 0.9957–0.9969; the first full run also scored PatchCore at 0.774 and localized heat to the exposed slot edge. The five normal captures retained zero displayed candidates.
- A separate PM02-missing control was repeated three times (`20260904_104219`, `104424`, and `104500`). Every run produced only `power_module_02 MISSING?`; the presence classifier returned `EMPTY` at 0.9999996–0.9999998 and the auxiliary YOLO outline was absent. The first full run scored PatchCore at 1.000 and filled the empty PM02 slot in the fixed excess heatmap.
- Twenty-seven regression tests and Python compilation passed. No robot or conveyor command was issued. Other displacement directions, magnitudes, dates, and lighting still require validation before authority can be promoted.

## 2026-09-04 — Closed-loop safety review of markerless SMD picking

- The review found that the initial implementation used one absolute observation, could confuse equal-size components in a whole-frame search, could accept smooth support-surface depth as component depth, averaged a 180-degree axis as a directed angle, allowed 10 mm pick XY error, and did not verify approach waypoint arrival.
- Initial selection is now center-prior and ambiguity rejecting, with a 12 px inter-frame tracking bound. After the initial 50 mm hover, the previous Base target is projected into the current camera view, followed by two bounded RGB-D correction passes (15 mm/20 degrees, then 5 mm/8 degrees), a third tracked detection, and final 1.0 mm/1.0-degree hover verification.
- Depth now separates the contour interior from a robust plane fitted to a surrounding annulus. Valid support requires interior validity/noise, support-plane MAD, temporal Z stability, and Base-Z component height consistent with the configured physical height within 2.0 mm. A synthetic 3 mm step recovered 3.0 mm, while a flat-depth false component was rejected.
- Rectangular orientation aggregation now uses a double-angle 180-degree axis mean and rejects more than 5 degrees of axis jitter. The former `[-89, +89] -> 0` failure now resolves to the equivalent -90-degree axis.
- Target files carry the active Hand-Eye SHA-256 and warning, and every motion stage checks that fingerprint. Full-cycle motion is blocked by default while the active calibration remains marked provisional and also requires an explicit physically measured `--grasp-z-offset-mm`. Non-contact 50 mm approach retains its separate confirmation path.
- Approach now checks robot/collision status and verifies every waypoint. Pre-grasp XY, Z, and axis limits are 1.0 mm, 1.0 mm, and 1.5 degrees. A dedicated gripper command verifies open/close completion states and gripper faults.
- Six SMD safety regression tests, calibration Python compilation, and shell syntax checks passed. No live markerless D435 accuracy or physical grasp-Z measurement was available; no robot, gripper, or conveyor command was issued. The hardware exposes no part-held feedback, so grasp success still cannot be asserted automatically.

## 2026-09-04 — Markerless six-profile gripper-camera picking implementation

- Generalized the closed-loop SMD detector/workflow into six selectable profiles: GPU, HBM, VRM, Power Module, Inductor, and SMD Capacitor. The new launcher loads dimensions, appearance segmentation, shape, and orientation behavior from `calibration/config/gripper_part_profiles.json`; neither ChArUco nor the team YOLO model is a runtime requirement.
- Dimensions are traceable to `vision_assembly/config/part_specs_candidate.json`. GPU 57×27×6 mm is the recorded user physical measurement. HBM 14.310×10.247×9.815 mm, VRM 14×11×5.203 mm, Power Module 59.989×12.130×4.785 mm, Inductor 9.369×9.369×8.522 mm, and SMD 6.801×3.836×3.024 mm remain CAD candidates requiring caliper checks.
- Added dark-foreground RGB-D segmentation for GPU/HBM/VRM, HSV orange segmentation for Power Module, bright RGB-D segmentation for SMD, and robust depth-plane protrusion segmentation for Inductor. Every candidate still requires separate top-surface and surrounding support-plane depth, configured physical height agreement, temporal depth stability, and Base-frame stability.
- Circular Inductor targets now carry `orientation_mode=preserve` with null long-axis fields. All downstream approach, descent, and grasp checks accept this axis-free contract and preserve current TCP orientation. Rectangular profiles retain 180-degree symmetric long-axis aggregation and alignment.
- Target reuse now verifies profile ID, exact configured dimensions, shape, segmentation mode, and orientation mode. All profiles are marked `detection_validated=false` and `full_pick_validated=false`, so even the first supervised 50 mm validation move requires an explicit unvalidated-profile override. Contact execution additionally requires measured gripper-close and grasp-Z values; the existing provisional Hand-Eye block remains active.
- Seventeen tests passed, covering an 8 mm raised object on a sloped synthetic depth plane, flat-plane rejection, dark/orange foreground masks, source-dimension consistency, aliases, circular orientation preservation, top-level and low-level unvalidated motion gating, explicit full-cycle command construction, and prior SMD safety behavior. Python, shell, and JSON syntax checks also passed.
- This task performed implementation and static/synthetic validation only. No live D435 trial and no robot, gripper, or conveyor command was issued. Remaining limits are CAD-only dimensions for five profiles, unmeasured per-part jaw span/force and grasp Z, unverified divider clearance, provisional Hand-Eye calibration, and no held-object sensor.

## 2026-09-04 — Live RGB-D non-SMD tray hover at 50 mm

- Added `run_tray_part_hover_5cm.sh` for the fixed tray waiting view. It consumes the already-running tray detector's aligned-D435 `/vision/tray/unity_state` plus `/vision/tray/registration`; it neither uses ChArUco nor starts another RealSense node. GPU, HBM, VRM, Power Module, and Inductor are supported, while SMD remains on its dedicated workflow.
- The capture gate requires fresh `TRACKING`, `at_trayhome=true`, `VALID_COORDINATES_ONLY`, `base_link/mm`, and at least ten upstream observations. Five distinct detector states must remain within 2.0 mm position and 3.0 degrees symmetric-axis jitter. Measured cross-machine registration latency reached 2.645 seconds, so live-state age is bounded at 3.5 seconds; the frozen target expires after 15 seconds.
- The live scene reported 5 VRMs, 4 Power Modules, 2 Inductors, 1 GPU, and 8 HBMs. Visible non-SMD surface coordinates occupied Base X `[-748.308,-506.620]`, Y `[-227.068,-24.103]`, and Z `[-47.836,-40.702]` mm. A reference-pixel-to-Base fit over all 20 targets had 1.893 mm maximum residual and projected the full non-SMD ROI union to X `[-786.945,-457.330]`, Y `[-258.050,121.221]` mm; the configured workspace adds margin around that full-tray range and rejects unrelated targets.
- Five-frame live dry-runs for instance 1 measured maximum position jitter of 0.498 mm GPU, 0.008 mm VRM, 0.016 mm Power Module, 0.019 mm Inductor, and 0.010 mm HBM. Their computed surface-plus-50-mm target Z values were 8.295, 2.764, 4.642, 4.789, and 2.202 mm respectively. Rectangular axis jitter printed as 0.000 degrees in each collection window.
- Rectangular parts automatically align Tool Y to the 180-degree-symmetric Base axis; circular/square Inductor preserves the current TCP attitude. Axis changes over 0.05 degrees complete at safe Z before translation, and each waypoint now verifies both XYZ (1.5 mm) and rotation-matrix attitude (1.0 degree). The generated path contains only an as-needed safe-Z raise, safe-Z rotation, horizontal translation, and a final vertical move to exactly surface Z+50 mm. Contact descent and all gripper calls are absent from this runner; the older full-pick implementation remains separate.
- Ten new tests and all 17 existing calibration tests passed (27 total), along with Python, shell, and JSON syntax checks. Four deliberately aged targets were rejected by the 15-second gate. Every hardware-connected run used `--dry-run`; no robot service, MoveCart, gripper, or conveyor command was issued. Physical 50 mm clearance, commanded-pose accuracy, Hand-Eye absolute error, and divider clearance remain to be measured under supervised motion.
- Created a 37-file robot/D435-PC overlay at `transfer/robot_d435_tray_hover_5cm_20260904/` plus a verified tarball. It deliberately excludes site Hand-Eye data and the team's running camera/detector implementation. Tarball SHA-256 is `515fa26b66d98bf9abcb110a6113bfa33d808a12d4b308bc75748d541c095e18`.
## 2026-09-09 Whole-board numbered countermeasure overview

- Added an optional 2400x1500 whole registered-board evidence PNG with numbered
  finding regions and a matching slot/reason list. Normal slots have no boxes;
  red requires confirmed_defect and AUTHORITATIVE, amber remains unverified.
  All provided defect names per slot are retained. No synthetic heatmap or
  inference/threshold/fusion change was introduced. No candidates is not PASS.
- Newly prepared API results include countermeasure_views slot_code ALL. Existing
  default report PNG, per-slot zooms, IDs, authentication and routing are preserved.
  Old archived results are not mutated. The teammate must select ALL for the sheet;
  the receiving application is not modified here. Missing geometry stays listed
  with located=false; legacy windows are not measured component outlines.
- Replayed archived inspection 1e2f3eab-3d28-4e4b-859b-2ff37b5676f7 (CAP-01 seating
  candidate, UNKNOWN) into runtime/inspection/countermeasure_overview_71fcljax.
  Visually checked the PNG. Generated a separate v2 workbook preview with original
  aspect ratio and crop removed; original Downloads workbook preserved. Small
  spreadsheet picture areas still require enlargement for readable printed lists.
- Validation: 102 offline integration tests and 2 localhost HTTP tests passed,
  including ALL selection, original endpoint preservation, authentication and
  integrity handling. Multi-finding and absent-geometry renderer tests passed.
  No fresh capture, live server restart, robot or conveyor command occurred.
  Full printed/OnlyOffice rendering and teammate end-to-end selection remain untested.
## 2026-09-09 Panel-free worksheet evidence photo

- Supersedes the sidebar overview for the ALL countermeasure view: full registered
  board only, numbered finding boxes, no header/sidebar/legend/text panel. Descriptions
  and number/slot mappings remain in rendering.findings; authoritative red and advisory
  amber meanings belong in the worksheet text. No inference or verdict changes.
- Read the supplied Downloads v2 drawing: extent 2022282x1600200 EMU. Output
  1600x1266 matches its ratio within rounding. The non-destructive workbook preview
  preserves that exact anchor extent and removes old image cropping. Original workbook
  and original archived reports were not edited.
- Archived CAP-01 UNKNOWN example regenerated under
  runtime/inspection/countermeasure_panel_free_u9qkg1p5; PNG visually inspected.
  102 offline integration tests passed (three socket tests excluded this run).
  JSON carries missing geometry explicitly; no annotation is not proof of PASS.
- Existing endpoints and optional per-slot zooms preserved. Teammate should fetch
  ALL and place the whole image, no crop. README and update note revised. No new
  capture, server restart, robot or conveyor command. OnlyOffice/printed rendering
  and teammate integration not tested; physical picture size limits fine details.
