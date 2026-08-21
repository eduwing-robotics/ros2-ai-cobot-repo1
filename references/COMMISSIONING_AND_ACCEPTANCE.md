# FR5 Cell Commissioning and Acceptance

Operator-provided candidate home and part-gripper values are preserved in [`PROVISIONAL_COMMISSIONING_VALUES.md`](PROVISIONAL_COMMISSIONING_VALUES.md). They are commissioning inputs and are not production-approved or automatically loaded by the runtime.

## 1. Principle

Production readiness is proven by repeatable evidence, not by a successful demo or RViz motion. Each gate freezes the software build, robot/gripper configuration, tool and recipe revisions, calibration hashes, test data, alarms, and deviations.

Safety validation is performed by the responsible safety engineer and certified hardware/controller chain. ROS software tests confirm command inhibition and state reporting; they do not certify the safety function.

## 2. Gate model

| Gate | Environment | Exit evidence |
|---|---|---|
| G0 Architecture/design review | offline | ownership, interfaces, units, frames, fault taxonomy, stop semantics approved |
| G1 Mechanical/tool release | bench/CAD | finger CAD, strength/moment, fasteners, ESD, payload/CoG, collision meshes approved |
| G2 Unit and SIL | CI/fake backends | transition, validation, recipe, transform, retry, cancellation tests pass |
| G3 Digital Twin | Gazebo baseline | every approved recipe path and fault scenario executes with API parity |
| G4 HIL dry run | guarded real cell, no part | device transport, stop/cancel, Home/Ready/Approach/Retract repeatability proven |
| G5 Grip qualification | dummy then real parts | grip window, damage, slip, release, width/current signatures approved |
| G6 Integrated process | real cell, reduced speed | vision, pick, assembly, conveyor, inspection, OK/NG, trace correlation pass |
| G7 Endurance/capability | production-like | takt, success/capability, recovery, thermal and log retention criteria pass |
| G8 Production release | controlled release | all deviations closed or formally accepted; versions frozen |

No gate may be bypassed by increasing retry count or disabling a guard.

## 3. Unit and contract tests

### State machine

- Every allowed transition has event, guard, entry action, exit condition, timeout, and failure transition.
- Every forbidden transition is tested.
- `EMERGENCY_STOP` and safety fault cannot transition directly to production.
- `FAULT` exits only through cause-clear verification and initialization.
- `MOVE` or `ASSEMBLY` interruption cannot resume a stale trajectory.
- Recipe change during active cycle is rejected.
- Retry budgets are per fault and per cycle; exhaustion latches the configured outcome.

### Vision

Inject and reject:

- NaN/infinite/malformed values;
- stale capture timestamp;
- unsynchronized clock;
- product/cycle/trigger mismatch;
- duplicate detection ID;
- low confidence or excessive covariance;
- wrong camera/frame/calibration ID;
- offset/jump/workspace limit violation;
- stale/missing TF;
- collision after correction;
- response after action timeout/cancel.

Acceptance: no rejected result can modify a motion target, and every rejection has a structured code and trace row.

### Coordinates

- Golden transforms for camera-to-base, fixture, conveyor, pallet, inspection, and each tool/grasp frame.
- Round-trip and inverse transform checks.
- Unit and angle-convention tests.
- Composition-order tests for workpiece-plane corrections.
- Calibration mismatch and stale-transform rejection.

### Recipe

- JSON-schema validation and unknown-field policy.
- Range and cross-field validation.
- tool/site/calibration compatibility.
- immutable hash and approval lifecycle.
- atomic activation and rollback.
- pre-planning of named poses and approach/retract paths.

### Motion

- finite values, joint/workspace margins, singularity policy, collision scene age.
- speed/acceleration profile allowed by state and payload.
- controller reject, timeout, cancellation, feedback loss, and final-tolerance failure.
- `MoveJ`, `MoveL`, and `MoveC` geometry-specific validation.
- completion means final measured tolerance, not action acceptance.

### Grip

- empty full-close, obstruction, timeout, device fault, width/current window failure.
- slip after micro-lift and during acceleration profile.
- release failure and hook jam.
- unknown state blocks transfer and assembly.

## 4. Digital Twin parity

Run the same interface-level scenario against real and simulation backends. Compare:

```text
request/result schema
state transitions
fault/rejection codes
target and actual trajectory identity
TCP path and final tolerance
gripper width/object attachment semantics
collision scene/tool/recipe/calibration versions
cancel/stop behavior
I/O event order
cycle and command trace linkage
```

Digital Twin acceptance limits are configuration with an owner and rationale. Simulation ground truth is not substituted for the calibrated/noisy sensor behavior used by the application. Fault injection includes communication delay/loss, stale vision, gripper miss, collision prediction, controller rejection, and disk-full logging.

## 5. HIL commissioning sequence

1. Verify guarded area, safety chain, controller mode, limits, and stop authority.
2. Record hardware serials, software/firmware versions, network configuration, and backups.
3. Start read-only state acquisition; compare FR5 WebApp, ROS state, and physical robot.
4. Validate command inhibition for every interlock before enabling motion.
5. Calibrate and activate empty-tool payload/TCP at maintenance speed.
6. Test one joint at a time, then short Cartesian moves, with independent stop readiness.
7. Verify Home/Ready/Safe region paths and stop/cancel at multiple points.
8. Connect PGEA read-only state; verify activation, width, current/force estimate, and faults.
9. Test open/close without parts over usable stroke.
10. Install approved Custom Finger and repeat payload/TCP/collision verification.
11. Run dry Pick/Place paths with no part and conservative geometry margins.
12. Run dummy-part grip qualification over a catch fixture.
13. Introduce vision correction and each external subsystem one at a time.
14. Run integrated cycles at staged speed/acceleration levels.
15. Perform endurance and fault-injection tests before release.

## 6. Grip qualification matrix

For every part revision and grip strategy, record:

```text
part dimensions, mass, material, revision, contact-zone approval
finger/tool revision and calibration hash
commanded/actual width
commanded force limit and measured/estimated force/current
close speed and settle time
micro-lift and transfer acceleration profile
post-grip pose shift and slip
surface damage/ESD/particle result
release success and residual engagement
cycle count, failures, retries, and confidence interval
```

Test nominal, minimum, and maximum part tolerances; clean/contaminated states where applicable; expected temperature range; lowest and highest approved force; worst-case transfer direction; and release at every destination.

Numeric success, capability, damage, and takt limits must come from the process owner. Example targets are not release criteria.

## 7. Recovery and fault injection

| Scenario | Expected invariant |
|---|---|
| Grip miss | no transfer without validated held-part state; bounded retry only |
| Slip after lift | transfer stops; safe return/manual path selected from known state |
| Vision timeout/stale | old result never reused; robot holds at qualified checkpoint |
| Offset over limit | corrected motion is never issued |
| Robot/gripper communication loss | command permit revoked and state becomes unknown |
| Joint/workspace limit | request rejected before movement where possible |
| Predicted collision | plan rejected; no blind retry |
| Physical collision | latched stop and manual inspection by default |
| Inspection NG | product route changes without equipment fault unless inspection device failed |
| E-stop/guard event | software actions cancel; no automatic resume/reset |
| PLC heartbeat loss | cycle cannot advance; fault policy is deterministic |
| Logger disk full/corruption | defined degraded/fault behavior; no silent trace loss |
| Process restart/power cycle | no stale command, recipe, vision, or trajectory resumes |

For each test, capture precondition, injected fault, physical response, ROS state/event order, WebApp/controller state, recovery decision, final checkpoint, operator action, and trace references.

## 8. Endurance and capability

Qualify with a staged plan agreed by process/quality owners:

- repeated no-part paths;
- repeated dummy-part grips;
- repeated nominal production cycles;
- tolerance-extreme parts;
- planned NG/rework/eject cycles;
- intermittent vision and communication faults;
- warm system after sustained operation;
- planned shutdown and restart with empty and held-part scenarios.

Track at minimum:

```text
cycle time distribution and tail latency
motion planning/execution duration
vision latency, rejection, and correction distribution
grip width/current/force/slip distribution
grip and release failure rates
inspection OK/NG and false-route events
fault frequency and recovery success
manual intervention time
TCP/pose drift and recalibration events
CPU/memory/network/control-loop timing
database size, write latency, and dropped-event count
```

## 9. Trace acceptance

- Every cycle has exactly one start and terminal outcome.
- Every motion, vision, grip, inspection, alarm, and recovery links to the cycle and command IDs.
- Active recipe/tool/calibration/software versions are reconstructable.
- Event ordering uses monotonic timing where needed and UTC for cross-system trace.
- Abrupt termination leaves recoverable SQLite/JSON evidence.
- CSV export totals reconcile to canonical database queries.
- Retention, archive, privacy, and disk quota behavior are tested.

## 10. Production-release checklist

- [ ] Interfaces, units, QoS, time source, namespaces, and error codes frozen.
- [ ] Custom Finger mechanical release and accurate collision model approved.
- [ ] TCP/payload/CoG and all fixed frames calibrated and versioned.
- [ ] Real FR5/PGEA backends pass HIL timing, watchdog, stop, reconnect, and feedback tests.
- [ ] Software interlock and certified safety matrix responsibilities are signed off.
- [ ] Every active recipe is schema-valid, compatible, approved, and pre-planned.
- [ ] Every state transition and recovery policy has automated or HIL evidence.
- [ ] Vision stale/mismatch/limit data cannot move the robot.
- [ ] Grip success detects empty close, slip, and release failure for each part family.
- [ ] Real/sim API parity passes for approved scenarios.
- [ ] Integrated and endurance criteria meet approved process limits.
- [ ] Logging, replay, retention, and troubleshooting documents are complete.
- [ ] Open deviations have owner, risk assessment, expiry, and formal approval.
