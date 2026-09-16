"""Offline tests for the GoPro-only launcher override; no camera or ROS starts."""
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / 'gopro_camera3/run_gopro_camera3_wifi.sh'


def run_override(**values):
    block = LAUNCHER.read_text().split('# Opt-in per-process transport;', 1)[1]
    block = '# Opt-in per-process transport;' + block.split('GOPRO_RUNTIME_DIR=', 1)[0]
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('KSMC_GOPRO_', 'CYCLONEDDS_', 'RMW_IMPLEMENTATION'))}
    env.update(SCRIPT_DIR=str(ROOT / 'gopro_camera3'), RMW_IMPLEMENTATION='rmw_fastrtps_cpp')
    env.update(values)
    return subprocess.run(['bash', '-eu', '-c', block + '\nprintenv RMW_IMPLEMENTATION'],
                          env=env, text=True, capture_output=True)


def test_default_preserves_common_rmw():
    result = run_override(RMW_IMPLEMENTATION='inherited_rmw')
    assert result.returncode == 0
    assert result.stdout.strip() == 'inherited_rmw'


def test_cyclone_is_opt_in():
    result = run_override(KSMC_GOPRO_RMW='rmw_cyclonedds_cpp')
    assert result.returncode == 0
    assert result.stdout.strip() == 'rmw_cyclonedds_cpp'


def test_fastdds_rollback():
    result = run_override(KSMC_GOPRO_RMW='rmw_fastrtps_cpp')
    assert result.returncode == 0
    assert result.stdout.strip() == 'rmw_fastrtps_cpp'


def test_missing_profile_rejected():
    result = run_override(KSMC_GOPRO_RMW='rmw_cyclonedds_cpp',
                          KSMC_GOPRO_CYCLONEDDS_PROFILE='/does/not/exist.xml')
    assert result.returncode == 2


def test_unknown_override_rejected():
    assert run_override(KSMC_GOPRO_RMW='typo').returncode == 2


def test_profile_is_monitor_wlan_only():
    ns = {'c': 'https://cdds.io/config'}
    root = ET.parse(ROOT / 'config/cyclonedds_gopro_laptop.xml').getroot()
    interfaces = root.findall('.//c:NetworkInterface', ns)
    assert [x.attrib['name'] for x in interfaces] == ['wlo1']
    assert root.find('.//c:MaxMessageSize', ns).text == '1400 B'
    assert root.find('.//c:FragmentSize', ns).text == '1280 B'
