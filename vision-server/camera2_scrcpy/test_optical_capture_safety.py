"""Exercise only shell helpers in a harness; never run the capture entrypoint."""

import os
from pathlib import Path
import re
import subprocess

import pytest


SCRIPT = Path(__file__).with_name("capture_optical_inspection.sh")


def run_helpers(tmp_path, body, *, settings=None, traps=False):
    source = SCRIPT.read_text()
    # No project environment sourcing, camera commands, capture or launcher
    # execution. Reuse only variable declarations and top-level shell helpers.
    declarations = source.split('phone_serial="', 1)[1].split("\nlog() {", 1)[0]
    definitions = re.findall(r"^\w+\(\) \{\n.*?^\}", source, re.M | re.S)
    trap_lines = "\n".join(re.findall(r"^trap .+$", source, re.M)) if traps else ""
    harness = "\n".join((
        "set -Ee; exec 3>&1",
        'phone_serial="' + declarations,
        *definitions,
        # The shell function replaces adb entirely; even cleanup redirection
        # cannot hide accidental calls because the stub reports on fd 3.
        'adb() { printf "FORBIDDEN_DEVICE_STUB %s\\n" "$*" >&3; }',
        trap_lines,
        body,
    ))
    env = {
        "PATH": os.defpath,
        "project_dir": str(tmp_path),
        "PHONE_SERIAL": "offline-test",
        "S22_CAMERA_CONTROL_DIR": str(tmp_path / "control"),
        "S22_INSPECTION_DIR": str(tmp_path / "inspection"),
    }
    env.update(settings or {})
    return subprocess.run(
        ["bash", "--noprofile", "--norc"], input=harness,
        text=True, capture_output=True, env=env, timeout=3,
    )


def test_cleanup_without_ownership_preserves_other_capture(tmp_path):
    lock = tmp_path / "control/optical_capture.lock"
    lock.mkdir(parents=True)
    pause = tmp_path / "control/pause.request"
    pause.write_text("other-capture-pid\n")
    result = run_helpers(tmp_path, "cleanup")
    assert result.returncode == 0, result.stderr
    assert "FORBIDDEN_DEVICE_STUB" not in result.stdout
    assert lock.is_dir()
    assert pause.read_text() == "other-capture-pid\n"


def test_owned_cleanup_is_idempotent_and_releases_own_lock(tmp_path):
    lock = tmp_path / "control/optical_capture.lock"
    lock.mkdir(parents=True)
    pause = tmp_path / "control/pause.request"
    pause.write_text("owned\n")
    result = run_helpers(tmp_path, """
lock_owned=1
camera_owned=1
pause_requested=1
cleanup
cleanup
""")
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("FORBIDDEN_DEVICE_STUB") == 1
    assert not lock.exists()
    assert not pause.exists()


@pytest.mark.parametrize("signal,status", [("INT", 130), ("TERM", 143)])
def test_capture_signal_exits_instead_of_continuing(tmp_path, signal, status):
    result = run_helpers(tmp_path, f"kill -{signal} $$\nprintf 'CONTINUED\\n'", traps=True)
    assert result.returncode == status
    assert "CONTINUED" not in result.stdout
    assert "FORBIDDEN_DEVICE_STUB" not in result.stdout


@pytest.mark.parametrize("setting,value", [
    ("S22_INSPECTION_ZOOM", "3.6"),
    ("S22_INSPECTION_FLASH", "auto"),
    ("S22_INSPECTION_FOCUS_X_PERCENT", "0"),
    ("S22_INSPECTION_FOCUS_Y_PERCENT", "100"),
    ("S22_INSPECTION_FOCUS_X_PERCENT", "08"),
    ("S22_INSPECTION_FOCUS_Y_PERCENT", "nan"),
])
def test_invalid_settings_rejected_without_device_or_lock_changes(tmp_path, setting, value):
    result = run_helpers(tmp_path, "validate_capture_settings", settings={setting: value})
    assert result.returncode == 1, result.stderr
    assert "ERROR:" in result.stderr
    assert "FORBIDDEN_DEVICE_STUB" not in result.stdout
    assert not (tmp_path / "control").exists()


@pytest.mark.parametrize("zoom", ["3", "3.0", "3.5", "4", "4.0", "4.7"])
@pytest.mark.parametrize("flash", ["on", "off", "ON", "1", "false"])
def test_existing_zoom_and_flash_choices_are_unchanged(tmp_path, zoom, flash):
    result = run_helpers(tmp_path, "validate_capture_settings", settings={
        "S22_INSPECTION_ZOOM": zoom,
        "S22_INSPECTION_FLASH": flash,
    })
    assert result.returncode == 0, result.stderr
    assert "FORBIDDEN_DEVICE_STUB" not in result.stdout


def test_validation_and_lock_precede_cleanup_registration_and_device_mutation():
    source = SCRIPT.read_text()
    validate = source.index("\nvalidate_capture_settings\n")
    first_device = source.index("\ncommand -v adb")
    acquire = source.index('\nmkdir "${lock_dir}"')
    arm_cleanup = source.index("\ntrap cleanup EXIT")
    own_camera = source.index("\ncamera_owned=1\n")
    force_stop = source.index('\nadb -s "${phone_serial}" shell am force-stop')
    assert validate < first_device < acquire < arm_cleanup < own_camera < force_stop
