# KSMC Smart Manufacturing Cell

FR5 + PGEA-100-40 + RealSense D435, S22 fixed camera, GoPro and a
TurtleBot-driven conveyor for semiconductor-package model assembly and
inspection.

## New computer

The first document for a person or Codex agent to read is:

> [CODEX_HANDOFF.md](CODEX_HANDOFF.md)

Recommended clone location is `$HOME/KSMC`, but runtime code resolves the
repository root automatically and does not require the Linux user name `hc`.

```bash
git clone <team-repository-url> "$HOME/KSMC"
cd "$HOME/KSMC"
cp config/ksmc.env.example config/ksmc.env
./scripts/setup_new_computer.sh
./scripts/doctor.sh
```

Do not execute robot motion merely because the build succeeds. Read the safety
and calibration sections in `CODEX_HANDOFF.md` first.
