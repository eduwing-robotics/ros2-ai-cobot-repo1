#!/usr/bin/env python3
"""Read-only integration checks: no imports of application code or hardware access."""
import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
errors = []
def check(ok, message):
    if not ok: errors.append(message)

sources = json.loads((ROOT/'docs/integration/sources.json').read_text())
for row in sources:
    check((ROOT/row['path']/'README.md').is_file(), f"Missing component: {row['path']}")
    check(len(row['commit']) == 40, 'Incomplete source commit')

provider = ROOT/'vision-server/ros2_ws/src/vision_interfaces/srv'
consumer = ROOT/'main-server/ASSEMBLY_SEQUENCER/src/vision_interfaces/srv'
normalized = lambda p: '\n'.join(line.split('#',1)[0].strip() for line in p.read_text().splitlines() if line.split('#',1)[0].strip())
service_count = 0
for p in consumer.glob('*.srv'):
    check((provider/p.name).exists(), f'Missing inspection provider service: {p.name}')
    if (provider/p.name).exists():
        check(normalized(p) == normalized(provider/p.name), f'Inspection service differs: {p.name}')
        service_count += 1
check(service_count > 0, 'No inspection services checked')
check((ROOT/'main-server/Ros2UnityEndopoint_PKG/run.sh').stat().st_mode & 0o111, 'Endpoint run.sh is not executable')
check((ROOT/'COLCON_IGNORE').exists(), 'Missing root colcon boundary')

paths = subprocess.check_output(['git','ls-files','-z'], cwd=ROOT).decode().split('\0')
python_count = 0
for rel in paths:
    if not rel: continue
    p = ROOT/rel
    if p.suffix == '.py' and p.is_file():
        try: ast.parse(p.read_bytes(), filename=rel); python_count += 1
        except (SyntaxError, ValueError) as exc: errors.append(f'{rel}: {exc}')
    if p.name in {'.env', '.env.real', '.env.mock', 'ksmc.env', 'id_rsa', 'id_ed25519'}:
        errors.append(f'Local configuration/key tracked: {rel}')
for rel in ['robot-server/run_fr5_assembly_stack.sh','robot-server/scripts/run_fairino_endpoint.sh']:
    result = subprocess.run(['bash','-n',str(ROOT/rel)],capture_output=True,text=True)
    check(result.returncode == 0, f'Shell syntax: {rel}: {result.stderr}')
report = dict(python_files=python_count, inspection_services=service_count, errors=errors, hardware_executed=False)
print(json.dumps(report,ensure_ascii=False,indent=2))
sys.exit(bool(errors))
