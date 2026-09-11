# Heartbeat incident recovery and rollback note

## Previous recovery method (keep as fallback)

When an interrupted run leaves the controller in `FAULT` or `MANUAL_STOP`, the
old safe recovery is explicit and operator-controlled:

1. Leave the PCB stationary and do not send a move request.
2. Confirm `/conveyor/state` reports `moving=false` and command speed `0`.
3. Call `/conveyor/reset` once, only after the area and robot are confirmed
   clear. The response must say the controller is `IDLE`.
4. Confirm `/vision/conveyor/stop_line_ready=true` and its heartbeat is fresh.
5. Press Unity's new-process button. The first request is then the normal
   start-position to assembly move.

`/conveyor/reset` is a state-changing service. This note does not authorize an
automatic reset or a robot move. A human or the Sequencer must bind the new Job
and Unit before starting again. Calling `/conveyor/stop` leaves `MANUAL_STOP`;
it is not the reset operation.

## Current latency mitigation and rollback boundary

The incident fix is the laptop-side Fast DDS profile in
`config/fastdds_laptop.xml`, selected by `KSMC_FASTDDS_PROFILE` in the local
ignored `config/ksmc.env`, plus the default `rmw_fastrtps_cpp` selection in
`scripts/ksmc_env.sh`. It limits DDS to `lo`, the cell Wi-Fi `wlo1`, and the
wired `enp129s0`, keeps local SHM, and enables non-blocking UDP. The 150 ms
S22 freshness watchdog stays enabled.

To return to the prior transport behavior, stop only the owned camera/ROI/
bundle launchers, remove `KSMC_FASTDDS_PROFILE` from the local environment (or
unset it before launching), and do not remove the source changes. Then run the
same read-only heartbeat audit. Do not roll back by killing unrelated ROS
processes. The current source/config snapshot and measurements are under
`runtime/conveyor/heartbeat_repair_20260910/`; `restart_private.json` is mode
0600 and may contain inherited environment values, so do not publish it.

## Current preflight state

The latest read-only preflight reports `MANUAL_STOP`, `moving=false`, command
speed `0`, fresh `vision_ready=true`, no active target and no arrival record.
Therefore Unity's move request will be rejected until the explicit reset step
above (or an equivalent Sequencer reset) completes. No reset or move was sent
by this investigation.

After the TurtleBot was power-cycled, `192.168.11.101` became unreachable
(ARP incomplete, no ICMP response after a 20-second wait), and the ROS domain
showed `/cmd_vel` with one publisher and zero subscribers. The laptop cable is
still physically up, but no robot Ethernet address or DHCP lease is visible.
Start the TurtleBot bringup locally on its console, or restore an authorized
SSH path, before running Unity. Do not diagnose a missing robot subscriber as a
camera or conveyor stop-line fault.
