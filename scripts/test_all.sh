#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${PROJECT_DIR}/scripts/ksmc_env.sh"
export PYTHONPATH="${PROJECT_DIR}/ros2_ws/src/fr5_process_sequences:${PROJECT_DIR}/ros2_ws/src/vision_server:${PROJECT_DIR}/vision_assembly/scripts:${PROJECT_DIR}/assembly_integration${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONDONTWRITEBYTECODE=1

# The tests replace hardware/GUI boundaries with fakes. Sourcing ROS here only
# makes message types available; this script does not start the assembly stack.
python3 -B -m pytest -p no:cacheprovider \
  "${PROJECT_DIR}/ros2_ws/src/fr5_process_sequences/test" \
  "${PROJECT_DIR}/ros2_ws/src/vision_server/test" \
  "${PROJECT_DIR}/vision_assembly/tests" \
  "${PROJECT_DIR}/scripts/tests" \
  "${PROJECT_DIR}/assembly_integration/test_assembly_progress.py" \
  -q

# Check syntax without writing bytecode into the working tree or touching
# installed/vendor packages. compile() parses code; it never imports a module.
python3 -B - "${PROJECT_DIR}" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
count = 0
for relative in ("calibration/scripts", "vision_assembly/scripts", "ros2_ws/src", "assembly_integration"):
    for path in sorted((root / relative).rglob("*.py")):
        if any(part in {"__pycache__", "build", "install", "vendor"} for part in path.relative_to(root).parts):
            continue
        compile(path.read_bytes(), str(path), "exec")
        count += 1
print(f"Python syntax checked: {count} files (no imports or bytecode writes).")
PY

bash -n "${PROJECT_DIR}/run_fr5_assembly_stack.sh" "${PROJECT_DIR}/run_fr5_cycle.sh" "${PROJECT_DIR}/scripts/test_all.sh"

echo "All offline source tests and syntax checks passed; no hardware execution."
