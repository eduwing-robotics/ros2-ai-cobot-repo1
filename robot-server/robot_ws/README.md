# KSMC FR5 ROS 2 workspace

This workspace isolates the FR5 runtime from the classroom workspace
`~/fr5_jazzy_test_ws`.

## Licensing policy

- FAIRINO's C++ SDK repository declares Apache-2.0.
- The official `frcobot_ros2` repository is public, but as checked on
  2026-08-13 it does not expose a repository-wide LICENSE and several ROS
  package manifests contain `TODO: License declaration`.
- Therefore `src/vendor/` is intentionally excluded from this project's Git
  history. The project records the official upstream URL and pinned commit,
  while each developer fetches the dependency locally.

Upstream: <https://github.com/FAIR-INNOVATION/frcobot_ros2>

Pinned commit: `867cb32bc24a73c1e60bef4e6c16762e7357c5e1`

## Setup

On this development laptop, run:

```bash
./robot_ws/setup_fairino_vendor.sh --from-classroom-workspace
./robot_ws/build_robot_ws.sh
```

On a teammate's laptop, run:

```bash
./robot_ws/setup_fairino_vendor.sh --from-official
./robot_ws/build_robot_ws.sh
```

Run the command server with:

```bash
./robot_ws/run_command_server.sh
```

KSMC launch scripts resolve and source `robot_ws/install/setup.bash`
internally, so users do not need to type the source commands manually.
