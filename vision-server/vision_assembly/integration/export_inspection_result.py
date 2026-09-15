#!/usr/bin/env python3
"""Build and optionally deliver one DB-safe S22 hybrid inspection package.

The source hybrid report is deliberately not re-decided here.  In particular,
ADVISORY_ONLY candidates remain UNKNOWN and cannot become confirmed defects in
the DB payload.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import socket
import sys
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest
import uuid
import zipfile
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = (
    PROJECT_ROOT
    / "runtime/inspection/hybrid_fixed_slot/hybrid_report_latest.json"
)
DEFAULT_CONFIG = PROJECT_ROOT / "vision_assembly/config/db_inspection_handoff.json"
DEFAULT_OUTBOX = PROJECT_ROOT / "runtime/inspection/db_outbox"
ALLOWED_STATUS = {"PASS", "FAIL", "UNKNOWN"}
REQUIRED_IMAGE_ROLES = {
    "source_roi": ("input_image",),
    "annotated_report": ("visualization", "report"),
    "candidate_heatmap": ("visualization", "patchcore_excess_map"),
    "candidate_heatmap_overlay": (
        "visualization",
        "patchcore_heatmap_overlay",
    ),
}
OPTIONAL_IMAGE_ROLES = {
    "registered_board": ("visualization", "aligned_board"),
    "slot_diagnostic": ("visualization", "slot_status_diagnostic"),
    "gpu_pin_debug": ("visualization", "gpu_pin_continuity_debug"),
}


class ExportError(RuntimeError):
    """Raised when a report cannot be handed off without ambiguity."""


class NoDeliveryRedirect(urlrequest.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ExportError('Delivery redirects refused; verify the configured endpoint')


def _read_json_snapshot(path: Path) -> tuple[dict[str, Any], bytes, float]:
    try:
        with path.open('rb') as stream:
            raw = stream.read()
            modified_at = os.fstat(stream.fileno()).st_mtime
        value = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise ExportError(f"Could not read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExportError(f"Expected one JSON object in {path}")
    return value, raw, modified_at


def _read_json(path: Path) -> dict[str, Any]:
    return _read_json_snapshot(path)[0]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_token(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-.")
    return cleaned or fallback


def _nested(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = data
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _capture_time(report: dict[str, Any], report_path: Path, modified_at: float | None = None) -> datetime:
    image_name = Path(str(report.get("input_image", ""))).name
    match = re.search(r"(20\d{6})[_-](\d{6})", image_name)
    if match:
        return datetime.strptime(
            "_".join(match.groups()), "%Y%m%d_%H%M%S"
        ).replace(tzinfo=ZoneInfo("Asia/Seoul"))
    return datetime.fromtimestamp(
        report_path.stat().st_mtime if modified_at is None else modified_at,
        tz=ZoneInfo("Asia/Seoul")
    )


def slot_code(slot_id: str, component_type: str, config: dict[str, Any]) -> str:
    metadata = config["component_types"].get(component_type)
    if not isinstance(metadata, dict):
        raise ExportError(f"No DB component mapping for {component_type!r}")
    part_id = str(metadata["part_id"])
    if slot_id == "ai_gpu":
        return "GPU-01"
    match = re.search(r"_(\d+)$", slot_id)
    if not match:
        raise ExportError(f"Could not derive external slot code from {slot_id!r}")
    return f"{part_id}-{int(match.group(1)):02d}"


def _compact_measurements(slot: dict[str, Any]) -> dict[str, Any]:
    stages = slot.get("stages", {})
    presence = stages.get("presence", {})
    pose = stages.get("pose", {})
    orientation = stages.get("orientation", {})
    surface = stages.get("surface", {})
    pins = stages.get("pins", {})
    measured = pose.get("measured", {})
    offset = measured.get("offset_mm")
    x_error = _float_or_none(offset[0]) if isinstance(offset, list) and len(offset) > 1 else None
    y_error = _float_or_none(offset[1]) if isinstance(offset, list) and len(offset) > 1 else None
    return {
        "presence_state": presence.get(
            "predicted_state", presence.get("predicted", "UNKNOWN")
        ),
        "presence_confidence": _float_or_none(presence.get("confidence")),
        "registered_image_x_error_mm": x_error,
        "registered_image_y_error_mm": y_error,
        "position_error_mm": _float_or_none(measured.get("position_error_mm")),
        "longitudinal_error_mm": _float_or_none(
            measured.get("longitudinal_offset_mm")
        ),
        "transverse_error_mm": _float_or_none(
            measured.get("transverse_offset_mm")
        ),
        "axis_angle_deg": _float_or_none(measured.get("axis_angle_deg")),
        "axis_angle_error_deg": _float_or_none(
            measured.get("axis_angle_error_deg")
        ),
        "orientation_feature": orientation.get("measured", {}).get("winner"),
        "surface_score": _float_or_none(surface.get("score")),
        "pin_status": pins.get("status"),
    }


def _compact_stage(stage: dict[str, Any]) -> dict[str, Any]:
    return {
        key: stage.get(key)
        for key in ("status", "authority", "confidence", "score", "reason")
        if stage.get(key) is not None
    }


def _slot_rows(
    report: dict[str, Any], config: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for slot in report["slots"]:
        slot_id = str(slot["slot_id"])
        component_type = str(slot["component_type"])
        component = config["component_types"].get(component_type)
        if not isinstance(component, dict):
            raise ExportError(f"No DB component mapping for {component_type!r}")
        stages = slot.get("stages", {})
        row = {
            "slot_id": slot_id,
            "slot_code": slot_code(slot_id, component_type, config),
            "part_id": component["part_id"],
            "part_type": component_type,
            "part_name": component["display_name"],
            "product_code": component.get("product_code"),
            "manufacturer": component.get("manufacturer"),
            "manufacturer_basis": component.get("manufacturer_basis"),
            "product_code_basis": component.get("product_code_basis"),
            "decision": slot.get("status", "UNKNOWN"),
            "reason": slot.get("reason"),
            "measurements": _compact_measurements(slot),
            "stages": {
                name: _compact_stage(stage)
                for name, stage in stages.items()
                if isinstance(stage, dict)
            },
        }
        rows.append(row)
        by_id[slot_id] = row
    return rows, by_id


def _authoritative_stage_findings(slot: dict[str, Any]) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for name, stage in slot.get("stages", {}).items():
        if not isinstance(stage, dict) or stage.get("status") != "FAIL":
            continue
        if stage.get("authority") != "AUTHORITATIVE":
            continue
        code = {
            "presence": "MISSING?",
            "pose": "POSE?",
            "orientation": "DIR?",
            "pins": "PINS?",
            "surface": "SURFACE?",
        }.get(name)
        if code and code not in {item[0] for item in findings}:
            findings.append((code, str(stage.get("reason", f"{name.upper()}_FAIL"))))
    return findings


def _findings(
    report: dict[str, Any],
    config: dict[str, Any],
    slots_by_id: dict[str, dict[str, Any]],
    inspection_id: str,
) -> list[dict[str, Any]]:
    source_slots = {str(row["slot_id"]): row for row in report["slots"]}
    grouped: dict[str, dict[str, Any]] = {}
    advisory = report.get("advisory_candidates", {})
    for item in advisory.get("items", []):
        slot_id = str(item["slot_id"])
        grouped[slot_id] = {
            "codes": list(dict.fromkeys(str(code) for code in item.get("codes", []))),
            "details": list(dict.fromkeys(str(v) for v in item.get("details", []))),
            "primary_code": item.get('primary_code'),
            # A display candidate cannot grant itself production authority.
            "authority": "ADVISORY_ONLY",
            "confirmed_defect": False,
        }

    for slot_id, source_slot in source_slots.items():
        if (report.get('status') != 'FAIL' or source_slot.get('status') != 'FAIL'
                or not report.get('registration', {}).get('alignment_valid', False)
                or report.get('capture_quality', {}).get('blocks_decision', False)):
            continue
        stage_findings = _authoritative_stage_findings(source_slot)
        if not stage_findings:
            continue
        target = grouped.setdefault(
            slot_id,
            {"codes": [], "details": [], "authority": "AUTHORITATIVE", "confirmed_defect": True},
        )
        target["codes"] = list(
            dict.fromkeys([*target["codes"], *(item[0] for item in stage_findings)])
        )
        target["details"] = list(
            dict.fromkeys([*target["details"], *(item[1] for item in stage_findings)])
        )
        target["authority"] = "AUTHORITATIVE"
        target["confirmed_defect"] = True
        target['primary_code'] = stage_findings[0][0]

    findings: list[dict[str, Any]] = []
    for slot_id, item in grouped.items():
        slot = slots_by_id.get(slot_id)
        if slot is None:
            raise ExportError(f"Candidate references unknown slot {slot_id!r}")
        normalized = []
        for source_code in item["codes"]:
            code_info = config["finding_codes"].get(source_code)
            if not isinstance(code_info, dict):
                code_info = {
                    "defect_code": "UNCLASSIFIED_ANOMALY",
                    "defect_name_ko": "미분류 이상",
                }
            normalized.append(
                {
                    "source_code": source_code,
                    "defect_code": code_info["defect_code"],
                    "defect_name_ko": code_info["defect_name_ko"],
                }
            )
        confirmed = bool(item["confirmed_defect"] and item["authority"] == "AUTHORITATIVE")
        primary = normalized[0] if normalized else {
            "source_code": "?",
            "defect_code": "UNCLASSIFIED_ANOMALY",
            "defect_name_ko": "미분류 이상",
        }
        primary = next((entry for entry in normalized if entry['source_code'] == item.get('primary_code')), primary)
        findings.append(
            {
                "finding_id": f"{inspection_id}-{slot['slot_code']}",
                "slot_id": slot_id,
                "slot_code": slot["slot_code"],
                "part_id": slot["part_id"],
                "part_type": slot["part_type"],
                "part_name": slot["part_name"],
                "product_code": slot["product_code"],
                "manufacturer": slot.get("manufacturer"),
                "manufacturer_basis": slot.get("manufacturer_basis"),
                "product_code_basis": slot.get("product_code_basis"),
                "decision": "FAIL" if confirmed else "UNKNOWN",
                "authority": item["authority"],
                "confirmed_defect": confirmed,
                "primary_defect_code": primary["defect_code"],
                "primary_defect_name_ko": primary["defect_name_ko"],
                "defect_codes": normalized,
                "details": item["details"],
                "measurements": slot["measurements"],
                "evidence_image_roles": [
                    "source_roi",
                    "annotated_report",
                    "candidate_heatmap",
                    "candidate_heatmap_overlay",
                ],
            }
        )
    return sorted(findings, key=lambda row: row["slot_code"])


def _validate_report(report: dict[str, Any], config: dict[str, Any]) -> None:
    expected_contract = str(config["source_inspection_contract"])
    if report.get("contract_id") != expected_contract:
        raise ExportError(
            f"Expected source contract {expected_contract!r}, got {report.get('contract_id')!r}"
        )
    status = str(report.get("status"))
    if status not in ALLOWED_STATUS:
        raise ExportError(f"Invalid hybrid board status: {status!r}")
    for section, flag in (('registration', 'alignment_valid'), ('capture_quality', 'blocks_decision')):
        value = report.get(section, {})
        if not isinstance(value, dict) or type(value.get(flag, False)) is not bool:
            raise ExportError(f'{section}.{flag} must be a boolean when provided')
    operational = report.get('operational_decision') or {}
    provisional_reject = (operational.get('mode') == 'PROVISIONAL_BINARY_V1'
                          and operational.get('validated') is False
                          and operational.get('status') == status == 'FAIL')
    if report.get('capture_quality', {}).get('blocks_decision') and status != 'UNKNOWN' and not provisional_reject:
        raise ExportError('Capture quality recheck may only be exported as UNKNOWN')
    slots = report.get("slots")
    if not isinstance(slots, list) or len(slots) != 25:
        raise ExportError(
            "The S22 hybrid contract requires exactly 25 slot objects"
        )
    for row in slots:
        if (not isinstance(row, dict) or not isinstance(row.get('slot_id'), str)
                or not row['slot_id'] or not isinstance(row.get('component_type'), str)):
            raise ExportError('Every slot requires a string slot_id and component_type')
        if not isinstance(row.get('status', 'UNKNOWN'), str) or row.get('status', 'UNKNOWN') not in ALLOWED_STATUS:
            raise ExportError(f"Invalid hybrid slot status for {row['slot_id']!r}")
    slot_ids = [row['slot_id'] for row in slots]
    if len(set(slot_ids)) != 25:
        raise ExportError("Hybrid report contains duplicate slot IDs")
    external_codes = [slot_code(row['slot_id'], row['component_type'], config) for row in slots]
    if len(set(external_codes)) != 25:
        raise ExportError('Hybrid report contains duplicate external slot codes')
    if not bool(report.get("registration", {}).get("alignment_valid", False)):
        # Registration failure is a valid UNKNOWN result and must still reach DB.
        if status != "UNKNOWN" and not provisional_reject:
            raise ExportError("Invalid registration may only be exported as UNKNOWN")


def _copy_images(
    report: dict[str, Any], package_dir: Path
) -> list[dict[str, Any]]:
    image_dir = package_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=False)
    copied: list[dict[str, Any]] = []
    roles = {**REQUIRED_IMAGE_ROLES, **OPTIONAL_IMAGE_ROLES}
    for index, (role, key_path) in enumerate(roles.items(), start=1):
        raw = _nested(report, key_path)
        if not raw:
            if role in REQUIRED_IMAGE_ROLES:
                raise ExportError(f"Required evidence image is absent: {role}")
            continue
        source = Path(str(raw)).expanduser().resolve()
        if not source.is_file():
            if role in REQUIRED_IMAGE_ROLES:
                raise ExportError(f"Required evidence image does not exist: {source}")
            continue
        suffix = source.suffix.lower() or ".bin"
        destination = image_dir / f"{index:02d}_{role}{suffix}"
        shutil.copy2(source, destination)
        relative = destination.relative_to(package_dir).as_posix()
        copied.append(
            {
                "role": role,
                "file": relative,
                "mime_type": mimetypes.guess_type(destination.name)[0]
                or "application/octet-stream",
                "sha256": _sha256(destination),
                "size_bytes": destination.stat().st_size,
                "authority": (
                    "ADVISORY_ONLY"
                    if role in {"candidate_heatmap", "candidate_heatmap_overlay"}
                    else "EVIDENCE"
                ),
            }
        )
    return copied


def _atomic_symlink(target: Path, link: Path) -> None:
    temporary = link.with_name(f".{link.name}.{uuid.uuid4().hex}.tmp")
    temporary.symlink_to(target.resolve())
    os.replace(temporary, link)


def _package_file(package_dir: Path, relative: str) -> Path:
    """Package references must be portable regular files, never symlink escapes."""
    if (not isinstance(relative, str) or not relative
            or any(char in relative for char in '\\\r\n\x00')
            or any(part in ('', '.', '..') for part in relative.split('/'))):
        raise ExportError('Invalid package file reference')
    path = package_dir
    if path.is_symlink():
        raise ExportError('Package directory must not be a symlink')
    for part in relative.split('/'):
        path = path / part
        if path.is_symlink():
            raise ExportError('Package file reference must not contain symlinks')
    if not path.is_file():
        raise ExportError(f'Package file is missing: {relative}')
    return path


def _verified_package_files(package_dir: Path, payload: dict[str, Any]) -> dict[str, bytes]:
    """Verify metadata and evidence together, then use exactly those read bytes."""
    try:
        manifest = _package_file(package_dir, 'SHA256SUMS').read_bytes()
        files: dict[str, bytes] = {}
        for line in manifest.decode('utf-8').splitlines():
            digest, relative = line.split('  ', 1)
            if not re.fullmatch('[0-9a-f]{64}', digest) or relative in files or relative == 'SHA256SUMS':
                raise ExportError('Invalid package integrity manifest')
            data = _package_file(package_dir, relative).read_bytes()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ExportError(f'Package integrity check failed: {relative}')
            files[relative] = data
        if json.loads(files['inspection_result.json']) != payload:
            raise ExportError('Package metadata integrity mismatch')
        roles = set()
        for image in payload['images']:
            role = image['role']
            if role not in {**REQUIRED_IMAGE_ROLES, **OPTIONAL_IMAGE_ROLES} or role in roles:
                raise ExportError('Invalid or duplicate package image role')
            roles.add(role)
            data = files[image['file']]
            if (hashlib.sha256(data).hexdigest() != image['sha256']
                    or len(data) != image['size_bytes']):
                raise ExportError('Package image integrity check failed')
            if not re.fullmatch(r'[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+', image['mime_type']):
                raise ExportError('Invalid package image MIME type')
        if not set(REQUIRED_IMAGE_ROLES) <= roles:
            raise ExportError('Required package image roles are missing')
        raw = files[payload['source']['hybrid_report_file']]
        if hashlib.sha256(raw).hexdigest() != payload['source']['hybrid_report_sha256']:
            raise ExportError('Package raw report integrity check failed')
        files['SHA256SUMS'] = manifest
        return files
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ExportError(f'Package integrity check failed: {type(exc).__name__}') from exc


def _verify_archive(package_dir: Path, zip_path: Path, files: dict[str, bytes]) -> None:
    try:
        expected = {f'{package_dir.name}/{name}': data for name, data in files.items()}
        with zipfile.ZipFile(zip_path) as archive:
            if len(archive.namelist()) != len(expected) or set(archive.namelist()) != set(expected):
                raise ExportError('Existing archive failed integrity check: file list mismatch')
            if any(archive.read(name) != data for name, data in expected.items()):
                raise ExportError('Existing archive failed integrity check: file content mismatch')
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ExportError('Existing archive failed integrity check') from exc


def _archive_package(package_dir: Path, zip_path: Path) -> None:
    files = _verified_package_files(package_dir, _read_json(package_dir / 'inspection_result.json'))
    temporary = zip_path.with_name(f".{zip_path.name}.{uuid.uuid4().hex}.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative, data in sorted(files.items()):
            archive.writestr(f'{package_dir.name}/{relative}', data)
    os.replace(temporary, zip_path)


def _reuse_existing_package(
    package_dir: Path,
    zip_path: Path,
    output_root: Path,
    idempotency_key: str,
    schema_id: str,
    supplied_ids: dict[str, Any],
    create_archive: bool = True,
) -> tuple[Path, Path, dict[str, Any]]:
    payload_path = package_dir / "inspection_result.json"
    if not payload_path.is_file():
        raise ExportError(f"Incomplete package already exists: {package_dir}")
    payload = _read_json(payload_path)
    if payload.get("idempotency_key") != idempotency_key:
        raise ExportError(f"Existing package identity mismatch: {package_dir}")
    if payload.get("schema_id") != schema_id:
        raise ExportError(f"Existing package schema mismatch: {package_dir}")
    for field, supplied in supplied_ids.items():
        if payload.get(field) != supplied:
            raise ExportError(
                f"Existing package has a different {field}: {payload.get(field)!r}"
            )
    files = _verified_package_files(package_dir, payload)
    if create_archive:
        if zip_path.exists():
            _verify_archive(package_dir, zip_path, files)
        else:
            _archive_package(package_dir, zip_path)
    _atomic_symlink(payload_path, output_root / "inspection_result_latest.json")
    if create_archive:
        _atomic_symlink(zip_path, output_root / "inspection_package_latest.zip")
    return package_dir, zip_path, payload


def build_package(
    report_path: Path,
    config_path: Path,
    output_root: Path,
    *,
    production_cycle_id: str | None = None,
    job_id: str | None = None,
    unit_id: int | None = None,
    board_id: str | None = None,
    inspection_id: str | None = None,
    create_archive: bool = True,
) -> tuple[Path, Path, dict[str, Any]]:
    if inspection_id is not None:
        try:
            inspection_id = str(uuid.UUID(inspection_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ExportError('inspection_id must be a UUID') from exc
    report_path = report_path.expanduser().resolve()
    if job_id is not None:
        try:
            job_id = str(uuid.UUID(job_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ExportError('job_id must be a UUID') from exc
    if unit_id is not None and (type(unit_id) is not int or unit_id <= 0):
        raise ExportError('unit_id must be a positive integer')
    config_path = config_path.expanduser().resolve()
    output_root = output_root.expanduser().resolve()
    if not report_path.is_file():
        raise ExportError(f"Hybrid report not found: {report_path}")
    report, report_bytes, report_modified_at = _read_json_snapshot(report_path)
    config = _read_json(config_path)
    _validate_report(report, config)

    input_path = Path(str(report["input_image"])).expanduser().resolve()
    if not input_path.is_file():
        raise ExportError(f"Source ROI not found: {input_path}")
    expected_input_hash = str(report.get("input_sha256") or "")
    actual_input_hash = _sha256(input_path)
    if expected_input_hash and actual_input_hash != expected_input_hash:
        raise ExportError("Source ROI SHA-256 does not match the hybrid report")

    report_hash = hashlib.sha256(report_bytes).hexdigest()
    key_material = ":".join(
        (str(report["contract_id"]), actual_input_hash, report_hash)
    ).encode("utf-8")
    idempotency_key = hashlib.sha256(key_material).hexdigest()
    captured_at = _capture_time(report, report_path, report_modified_at)
    inspection_id = inspection_id or (
        f"INSP-{captured_at.strftime('%Y%m%d-%H%M%S')}-{idempotency_key[:10].upper()}"
    )
    output_root.mkdir(parents=True, exist_ok=True)
    package_dir = output_root / _safe_token(inspection_id, "inspection")
    zip_path = output_root / f"{package_dir.name}.zip"
    if package_dir.exists():
        return _reuse_existing_package(
            package_dir,
            zip_path,
            output_root,
            idempotency_key,
            str(config["contract_id"]),
            {
                "inspection_id": inspection_id,
                "production_cycle_id": production_cycle_id,
                "job_id": job_id,
                "unit_id": unit_id,
                "board_id": board_id,
            },
            create_archive=create_archive,
        )
    package_dir.mkdir(parents=True)
    try:
        raw_dir = package_dir / "raw"
        raw_dir.mkdir()
        raw_report = raw_dir / "hybrid_report.json"
        raw_report.write_bytes(report_bytes)
        images = _copy_images(report, package_dir)
        if next(image['sha256'] for image in images if image['role'] == 'source_roi') != actual_input_hash:
            raise ExportError('Source ROI changed while evidence was being copied')

        slots, slots_by_id = _slot_rows(report, config)
        findings = _findings(report, config, slots_by_id, inspection_id)
        status = str(report["status"])
        confirmed_count = sum(bool(row["confirmed_defect"]) for row in findings)
        counts = {
            state: sum(row["decision"] == state for row in slots)
            for state in ("PASS", "FAIL", "UNKNOWN")
        }
        payload = {
            "schema_id": config["contract_id"],
            "schema_version": int(config["schema_version"]),
            "inspection_id": inspection_id,
            "idempotency_key": idempotency_key,
            "production_cycle_id": production_cycle_id,
            "job_id": job_id,
            "unit_id": unit_id,
            "board_id": board_id,
            "recipe_version": config["recipe_version"],
            "station_id": config["station_id"],
            "camera_id": config["camera_id"],
            "captured_at": captured_at.isoformat(),
            "inspected_at": datetime.fromtimestamp(
                report_modified_at, tz=ZoneInfo("Asia/Seoul")
            ).isoformat(),
            "source_host": socket.gethostname(),
            "operational_decision": report.get("operational_decision"),
            "validated_decision": report.get("validated_decision"),
            "overall": {
                "decision": status,
                "reason": report.get("reason"),
                "route": {
                    "PASS": "CONTINUE",
                    "FAIL": "ROUTE_NG",
                    "UNKNOWN": "RECAPTURE_THEN_HOLD_NG_UNCERTAIN",
                }[status],
                "formal_defect_report_allowed": bool(
                    status == "FAIL" and confirmed_count > 0
                ),
                "alignment_score": _float_or_none(
                    report.get("registration", {}).get("alignment_score")
                ),
                "alignment_valid": bool(
                    report.get("registration", {}).get("alignment_valid", False)
                ),
            },
            "summary": {
                "expected_slots": 25,
                "slot_decisions": counts,
                "finding_count": len(findings),
                "confirmed_defect_count": confirmed_count,
                "advisory_candidate_count": sum(
                    row["authority"] == "ADVISORY_ONLY" for row in findings
                ),
            },
            "findings": findings,
            "slots": slots,
            "diagnostics": {
                "capture_quality": report.get('capture_quality'),
                "evidence_audit": report.get('evidence_audit'),
                "provider_health": report.get('provider_health'),
                "pose_display_audit": report.get('pose_display_audit'),
                "note": "Diagnostic raw flags are not confirmed defects; missing old fields mean not evaluated.",
            },
            "images": images,
            "source": {
                "inspection_contract": report["contract_id"],
                "hybrid_report_file": "raw/hybrid_report.json",
                "hybrid_report_sha256": report_hash,
                "input_sha256": actual_input_hash,
                "robot_command_sent": bool(report.get("robot_command_sent", False)),
                "conveyor_command_sent": bool(
                    report.get("conveyor_command_sent", False)
                ),
            },
        }
        payload_path = package_dir / "inspection_result.json"
        payload_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        manifest_lines = [
            f"{_sha256(path)}  {path.relative_to(package_dir).as_posix()}"
            for path in sorted(package_dir.rglob("*"))
            if path.is_file()
        ]
        (package_dir / "SHA256SUMS").write_text(
            "\n".join(manifest_lines) + "\n", encoding="utf-8"
        )
    except Exception:
        shutil.rmtree(package_dir, ignore_errors=True)
        raise

    if create_archive:
        _archive_package(package_dir, zip_path)
    _atomic_symlink(package_dir / "inspection_result.json", output_root / "inspection_result_latest.json")
    if create_archive:
        _atomic_symlink(zip_path, output_root / "inspection_package_latest.zip")
    return package_dir, zip_path, payload


def _multipart_body(
    package_dir: Path, payload: dict[str, Any]
) -> tuple[bytes, str]:
    files = _verified_package_files(package_dir, payload)
    boundary = f"----KSMC-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    def add_file(field: str, relative: str, mime: str) -> None:
        chunks.extend(
            (
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{field}"; '
                    f'filename="{Path(relative).name}"\r\n'
                ).encode(),
                f"Content-Type: {mime}\r\n\r\n".encode(),
                files[relative],
                b"\r\n",
            )
        )

    add_file(
        "metadata",
        "inspection_result.json",
        "application/json",
    )
    for image in payload["images"]:
        add_file(
            f"image_{image['role']}",
            image["file"],
            image["mime_type"],
        )
    add_file(
        "raw_hybrid_report",
        payload["source"]["hybrid_report_file"],
        "application/json",
    )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


def send_package(
    endpoint: str,
    package_dir: Path,
    payload: dict[str, Any],
    *,
    token: str | None = None,
    timeout_seconds: float = 45.0,
) -> dict[str, Any]:
    body, boundary = _multipart_body(package_dir, payload)
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
        "Idempotency-Key": payload["idempotency_key"],
        "X-KSMC-Schema": payload["schema_id"],
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urlrequest.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urlrequest.build_opener(NoDeliveryRedirect()).open(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            try:
                ack = json.loads(response_body)['data']
                if (ack.get('stored') is not True
                        or ack.get('inspection_id') != payload['inspection_id']
                        or ack.get('idempotency_key') != payload['idempotency_key']
                        or ack.get('production_applied') is not False):
                    raise ValueError('receipt identity or storage status mismatch')
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                raise ExportError('Server did not acknowledge matching file storage; package retained') from exc
            receipt = {
                "delivered": True,
                "endpoint": endpoint,
                "http_status": response.status,
                "response": response_body[:4096],
                "delivered_at": datetime.now(tz=ZoneInfo("Asia/Seoul")).isoformat(),
                "inspection_id": payload["inspection_id"],
                "idempotency_key": payload["idempotency_key"],
            }
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        raise ExportError(
            f"DB delivery failed; package remains in the outbox: {exc}"
        ) from exc
    (package_dir / "delivery_receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package a 25-slot S22 hybrid report for the DB/backend team."
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTBOX)
    parser.add_argument("--production-cycle-id")
    parser.add_argument("--job-id")
    parser.add_argument("--unit-id", type=int)
    parser.add_argument("--board-id")
    parser.add_argument(
        "--endpoint",
        help="Optional DB HTTP endpoint. Omit to create an offline ZIP only.",
    )
    parser.add_argument(
        "--token-env",
        default="KSMC_DB_API_TOKEN",
        help="Environment variable containing an optional Bearer token.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        package_dir, zip_path, payload = build_package(
            args.report,
            args.config,
            args.output_root,
            production_cycle_id=args.production_cycle_id,
            job_id=args.job_id,
            unit_id=args.unit_id,
            board_id=args.board_id,
        )
        print(f"DB_INSPECTION_ID={payload['inspection_id']}")
        print(f"DB_DECISION={payload['overall']['decision']}")
        print(f"DB_FINDINGS={payload['summary']['finding_count']}")
        print(f"DB_PACKAGE_DIR={package_dir}")
        print(f"DB_PACKAGE_ZIP={zip_path}")
        if args.endpoint:
            token = os.environ.get(args.token_env)
            receipt = send_package(
                args.endpoint,
                package_dir,
                payload,
                token=token,
                timeout_seconds=args.timeout_seconds,
            )
            print(f"DB_HTTP_STATUS={receipt['http_status']}")
        else:
            print("DB_DELIVERY=NOT_REQUESTED (offline package created)")
        return 0
    except ExportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
