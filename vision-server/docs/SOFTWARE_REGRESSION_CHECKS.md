# Offline regression and deployment checks

## What was hardened

The Sept 8 parallel pass covered camera capture/stream lifecycle, conveyor
freshness/interlocks, fixed-slot inspection/provider isolation, evidence/API
integrity, and robot target numeric validation. It did not tune model weights,
defect thresholds, stop-line geometry, camera resolution, zoom or network/token
settings. New source takes effect when its process next starts; no running
equipment server was restarted during this work.

## Repeat the software checks

From the KSMC root:

```bash
python3 scripts/run_offline_checks.py
```

The allowlisted eight groups run at most two at a time: hybrid inspection,
API/bundle, camera, ROS conveyor, robot/tray, viewer, runner tests, and source
syntax. They use synthetic inputs, mocks and inert child processes, not camera
capture or motor publishers. Python/ML and ROS overlays must already be installed;
missing dependencies produce UNAVAILABLE and an unsuccessful overall result.
Nothing is installed automatically. No GPU training or inference runs in this tool.

Useful options:

```bash
python3 scripts/run_offline_checks.py --list
python3 scripts/run_offline_checks.py --jobs 2 --timeout 120 --with-loopback
```

`--with-loopback` includes two temporary local socket tests; no production server
is contacted. Without it, those tests are explicitly deselected. Source syntax uses
Python AST parsing and `bash -n`, never executes the inspected scripts. The runner
does not source private device config or emit tokens. Reports and per-group logs
go to a new directory under `runtime/software_checks`; an explicit `--output`
must also be new. Timeouts/cancellation clean up owned test processes, never
search-and-kill live equipment processes.

## Recorded verification

Final approved local-loopback run:
`runtime/software_checks/20260908T012722Z_4c4de5ed/report.json`.

| Group | Result |
| --- | --- |
| Hybrid inspection | 159 Python tests |
| API and server bundle | 84 Python tests, including loopback |
| Camera | 65 Python tests |
| ROS conveyor | 123 Python tests |
| Robot and tray | 57 Python tests |
| Offline runner | 6 Python tests |
| Viewer | 2 JavaScript tests |
| Source syntax | 191 Python and 106 shell files |

All passed: 494 Python + 2 JavaScript tests. This is not a count of physical
inspection samples or proof of defect accuracy. The initial run during parallel
edits included unfinished-test failures and a sandbox socket restriction; only
the final report above represents the integrated result.

One separate host-GPU replay of the saved Sept 7 17:23:49 board image retained
all 25 PatchCore scores exactly and the same four advisory candidates. Final
UNKNOWN remains. Comparison and an unbound, test-only JSON/PNG viewer are in
`runtime/inspection/parallel_hardening_20260908/review/`. No new photograph was taken.

## Operational implications and remaining checks

- Zero, future, stale or undecodable source frames now inhibit conveyor readiness
  instead of refreshing it. Camera and receiver clocks must be consistent; review
  the reject reason if readiness disappears. No geometry/stop-distance change.
- A duplicate request for the same active conveyor move does not restart/pulse
  motion or extend its deadline. Lost interlocks still stop/fault. Monitor-only
  retains the existing zero-speed HOLD behavior; it is not a passive observer.
- S22 snapshot service rejects frames older than 0.20 seconds and preserves the
  actual frame timestamp. Optical-capture abort cleans up only its owned resources.
- GoPro recovery and close cannot race to resurrect a decoder. V4L2 driver-blocked
  teardown and physical USB/WiFi quality/latency remain hardware checks.
- Malformed/failed learned providers remain UNKNOWN while independent stages run.
  HBM white-pin checks are explicitly unavailable, not silently counted as complete.
  The displayed 13 unavailable/disabled stage entries in the saved replay are
  eight unvalidated HBM pin checks plus five pre-existing disabled experimental
  VRM seating candidates—not 13 confirmed defective components.
- API result state and evidence must survive persistence/copy checks; failed
  results do not expose partially completed PASS/image-ready fields. Checksums
  detect corruption, not malicious replacement by an actor controlling the files.
- Robot target guards reject nonfinite timestamps, XYZ, relevant depth metrics,
  dimensions and CLI floats before motion decisions; existing finite tolerances,
  tool/calibration gates and explicit confirmations remain. Robot hardware was not
  exercised and this is not a safety certification.

Plan a coordinated idle restart only after the teammate has no request in flight.
The existing ROS install resolves to the source tree via the build symlink on this
machine, verified read-only; no rebuild/restart was needed for tests. Then perform
an actual camera/stop/request/capture/result trial under supervision. That trial,
micro-lip/height discrimination, reliable HBM pins, fine-crack generalization, and
production PASS calibration remain outstanding. No check was removed to make the
prototype appear successful.
