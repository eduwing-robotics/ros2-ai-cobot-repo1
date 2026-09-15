#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import pytest


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import export_inspection_result as exporter  # noqa: E402
from export_inspection_result import build_package, send_package, slot_code  # noqa: E402


def test_invalid_production_ids_rejected(tmp_path):
    with pytest.raises(exporter.ExportError, match='inspection_id must be a UUID'):
        build_package(tmp_path/'missing', tmp_path/'config', tmp_path/'out', inspection_id='bad-id')
    with pytest.raises(exporter.ExportError, match='UUID'):
        build_package(tmp_path/'missing', tmp_path/'config', tmp_path/'out', job_id='22')
    with pytest.raises(exporter.ExportError, match='positive integer'):
        build_package(tmp_path/'missing', tmp_path/'config', tmp_path/'out', unit_id=True)


def test_redirect_refused():
    with pytest.raises(exporter.ExportError, match='redirects'):
        exporter.NoDeliveryRedirect().redirect_request(None,None,302,'',{},'http://elsewhere')


@pytest.mark.parametrize('authority', ['UNAVAILABLE', 'UNVERIFIED', '', None, 'ADVISORY_ONLY'])
def test_non_authoritative_fail_cannot_be_exported_as_confirmed(tmp_path, authority):
    path = _report(tmp_path, authoritative=True)
    report = json.loads(path.read_text())
    report['slots'][4]['stages']['presence']['authority'] = authority
    path.write_text(json.dumps(report))
    _, _, payload = build_package(path, _config(tmp_path), tmp_path/'out', create_archive=False)
    assert payload['summary']['confirmed_defect_count'] == 0
    assert not payload['overall']['formal_defect_report_allowed']


def test_candidate_cannot_self_grant_authority(tmp_path):
    path = _report(tmp_path)
    report = json.loads(path.read_text())
    report['advisory_candidates']['items'][0].update(authority='AUTHORITATIVE', confirmed_defect=True)
    path.write_text(json.dumps(report))
    _, _, payload = build_package(path, _config(tmp_path), tmp_path/'out', create_archive=False)
    assert payload['findings'][0]['authority'] == 'ADVISORY_ONLY'
    assert payload['summary']['confirmed_defect_count'] == 0


def test_bad_capture_is_unknown_and_diagnostics_are_preserved(tmp_path):
    path = _report(tmp_path, authoritative=True)
    report = json.loads(path.read_text())
    report['capture_quality'] = dict(blocks_decision=True, flags=['GROSS_BLUR_OR_TEXTURE_LOSS'])
    report['evidence_audit'] = dict(raw_fail_count=2, undisplayed_count=1, items=[])
    path.write_text(json.dumps(report))
    with pytest.raises(exporter.ExportError, match='quality recheck'):
        build_package(path, _config(tmp_path), tmp_path/'out', create_archive=False)
    report['status'] = 'UNKNOWN'
    path.write_text(json.dumps(report))
    _, _, payload = build_package(path, _config(tmp_path), tmp_path/'out', create_archive=False)
    assert payload['summary']['confirmed_defect_count'] == 0
    assert payload['diagnostics']['capture_quality'] == report['capture_quality']
    assert payload['diagnostics']['evidence_audit'] == report['evidence_audit']


def test_registration_failure_cannot_emit_confirmed_defects(tmp_path):
    path = _report(tmp_path, authoritative=True)
    report = json.loads(path.read_text())
    report['status'] = 'UNKNOWN'
    report['registration']['alignment_valid'] = False
    path.write_text(json.dumps(report))
    _, _, payload = build_package(path, _config(tmp_path), tmp_path/'out', create_archive=False)
    assert payload['summary']['confirmed_defect_count'] == 0


def test_runtime_boundary_codes_and_primary_match_operator_image(tmp_path):
    path = _report(tmp_path)
    report = json.loads(path.read_text())
    candidate = report['advisory_candidates']['items'][0]
    candidate.update(slot_id='vrm_05', codes=['RIGHT?', 'MISSING?'], primary_code='MISSING?')
    path.write_text(json.dumps(report))
    _, _, payload = build_package(path, exporter.DEFAULT_CONFIG, tmp_path/'out', create_archive=False)
    finding = payload['findings'][0]
    assert finding['primary_defect_code'] == 'COMPONENT_MISSING'
    assert finding['defect_codes'][0]['defect_code'] == 'POSITION_ERROR'
    assert finding['confirmed_defect'] is False
    config = json.loads(exporter.DEFAULT_CONFIG.read_text())
    assert config['finding_codes']['ROT?']['defect_code'] == 'DIRECTION_ERROR'


def test_sequencer_uuid_preserved(tmp_path):
    import uuid
    import zipfile
    iid, jid = str(uuid.uuid4()), str(uuid.uuid4())
    folder, archive, payload = build_package(_report(tmp_path), _config(tmp_path),
        tmp_path/'out', inspection_id=iid, job_id=jid, unit_id=42)
    assert payload['inspection_id'] == iid
    assert payload['job_id'] == jid and payload['unit_id'] == 42
    assert payload['overall']['decision'] == 'UNKNOWN'
    with zipfile.ZipFile(archive) as bundle:
        assert any(name.endswith('raw/hybrid_report.json') for name in bundle.namelist())


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _config(tmp_path: Path) -> Path:
    config = {
        "schema_version": 1,
        "contract_id": "ksmc.vision-inspection.v1",
        "source_inspection_contract": "s22_hybrid_aoi_v1",
        "station_id": "VISION_INSPECTION",
        "camera_id": "S22_TELEPHOTO",
        "recipe_version": "assembly-r1",
        "component_types": {
            "GPU": {"part_id": "GPU", "display_name": "AI GPU", "product_code": None},
            "HBM": {"part_id": "HBM", "display_name": "HBM", "product_code": None},
            "Power Module": {"part_id": "PM", "display_name": "PM", "product_code": "TPS"},
            "VRM": {"part_id": "VRM", "display_name": "VRM", "product_code": None},
            "Inductor": {"part_id": "IND", "display_name": "Inductor", "product_code": None},
            "SMD Capacitor": {"part_id": "CAP", "display_name": "SMD", "product_code": None},
        },
        "finding_codes": {
            "MISSING?": {"defect_code": "COMPONENT_MISSING", "defect_name_ko": "부품 누락"},
            "POSE?": {"defect_code": "POSITION_ERROR", "defect_name_ko": "위치 오류"},
        },
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _report(tmp_path: Path, *, authoritative: bool = False) -> Path:
    image = tmp_path / "s22_inspection_roi_20260904_120000.png"
    image.write_bytes(b"source-image")
    visual = {}
    for key in (
        "report",
        "patchcore_excess_map",
        "patchcore_heatmap_overlay",
        "aligned_board",
        "slot_status_diagnostic",
    ):
        path = tmp_path / f"{key}.png"
        path.write_bytes(key.encode())
        visual[key] = str(path)
    component_types = (
        ["GPU"]
        + ["HBM"] * 8
        + ["Power Module"] * 4
        + ["Inductor"] * 2
        + ["SMD Capacitor"] * 5
        + ["VRM"] * 5
    )
    slot_ids = (
        ["ai_gpu"]
        + [f"hbm_{i:02d}" for i in range(1, 9)]
        + [f"power_module_{i:02d}" for i in range(1, 5)]
        + [f"inductor_{i:02d}" for i in range(1, 3)]
        + [f"smd_capacitor_{i:02d}" for i in range(1, 6)]
        + [f"vrm_{i:02d}" for i in range(1, 6)]
    )
    slots = []
    for slot_id, component_type in zip(slot_ids, component_types, strict=True):
        presence_status = "FAIL" if authoritative and slot_id == "hbm_04" else "UNKNOWN"
        presence_authority = "AUTHORITATIVE" if authoritative and slot_id == "hbm_04" else "ADVISORY_ONLY"
        slots.append(
            {
                "slot_id": slot_id,
                "component_type": component_type,
                "status": "FAIL" if presence_status == "FAIL" else "UNKNOWN",
                "reason": "test",
                "stages": {
                    "presence": {
                        "predicted_state": "EMPTY" if slot_id == "hbm_04" else "PRESENT",
                        "status": presence_status,
                        "authority": presence_authority,
                        "confidence": 0.97,
                        "reason": "TEST_PRESENCE",
                    },
                    "pose": {
                        "status": "UNKNOWN",
                        "authority": "ADVISORY_ONLY",
                        "reason": "TEST_POSE",
                        "measured": {
                            "offset_mm": [0.1, -0.2],
                            "position_error_mm": 0.224,
                            "axis_angle_error_deg": 1.0,
                        },
                    },
                    "orientation": {
                        "status": "UNKNOWN",
                        "authority": "ADVISORY_ONLY",
                        "reason": "TEST_DIR",
                    },
                    "surface": {
                        "status": "UNKNOWN",
                        "authority": "ADVISORY_ONLY",
                        "score": 0.42,
                        "reason": "TEST_SURFACE",
                    },
                },
            }
        )
    report = {
        "contract_id": "s22_hybrid_aoi_v1",
        "input_image": str(image),
        "input_sha256": _hash(image),
        "status": "FAIL" if authoritative else "UNKNOWN",
        "reason": "test board",
        "registration": {"alignment_valid": True, "alignment_score": 0.98},
        "slots": slots,
        "advisory_candidates": {
            "authority": "ADVISORY_ONLY",
            "confirmed_defect": False,
            "count": 1,
            "items": [
                {
                    "slot_id": "power_module_01",
                    "codes": ["POSE?"],
                    "details": ["AUXILIARY_POSE_OUTSIDE_LIMIT"],
                    "authority": "ADVISORY_ONLY",
                    "confirmed_defect": False,
                }
            ],
        },
        "visualization": visual,
        "robot_command_sent": False,
        "conveyor_command_sent": False,
    }
    path = tmp_path / "hybrid_report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def test_slot_codes_match_assembly_recipe(tmp_path: Path) -> None:
    config = json.loads(_config(tmp_path).read_text())
    assert slot_code("ai_gpu", "GPU", config) == "GPU-01"
    assert slot_code("hbm_08", "HBM", config) == "HBM-08"
    assert slot_code("power_module_04", "Power Module", config) == "PM-04"
    assert slot_code("smd_capacitor_05", "SMD Capacitor", config) == "CAP-05"
    assert slot_code("inductor_02", "Inductor", config) == "IND-02"
    assert slot_code("vrm_05", "VRM", config) == "VRM-05"


def test_demo_manufacturers_exported_without_decision_promotion(tmp_path):
    config = Path(__file__).resolve().parents[1] / 'config/db_inspection_handoff.json'
    _, _, payload = build_package(_report(tmp_path), config, tmp_path/'manufacturers',
                                  create_archive=False)
    expected = {'GPU': 'NVIDIA', 'HBM': 'SK hynix', 'PM': 'Texas Instruments',
                'VRM': 'Infineon Technologies', 'IND': 'TDK', 'CAP': 'Samsung Electro-Mechanics'}
    assert len(payload['slots']) == 25
    for row in payload['slots'] + payload['findings']:
        assert row['manufacturer'] == expected[row['part_id']]
        assert row['manufacturer_basis'] == 'DEMO_ASSIGNED_NOT_IMAGE_INFERRED'
    assert payload['overall']['decision'] == 'UNKNOWN'
    assert not payload['overall']['formal_defect_report_allowed']


def test_advisory_candidate_stays_unknown_and_package_is_portable(tmp_path: Path) -> None:
    package_dir, zip_path, payload = build_package(
        _report(tmp_path), _config(tmp_path), tmp_path / "outbox",
        production_cycle_id="CYCLE-22", job_id="00000000-0000-4000-8000-000000000022", board_id="PCB-2",
    )
    assert payload["overall"]["decision"] == "UNKNOWN"
    assert payload["schema_id"] == "ksmc.vision-inspection.v1"
    assert payload["schema_version"] == 1
    assert payload["overall"]["formal_defect_report_allowed"] is False
    finding = payload["findings"][0]
    assert finding["slot_code"] == "PM-01"
    assert finding["primary_defect_code"] == "POSITION_ERROR"
    assert finding["decision"] == "UNKNOWN"
    assert finding["confirmed_defect"] is False
    assert payload["production_cycle_id"] == "CYCLE-22"
    assert len(payload["slots"]) == 25
    assert all(not Path(image["file"]).is_absolute() for image in payload["images"])
    assert (package_dir / "inspection_result.json").is_file()
    assert (package_dir / "SHA256SUMS").is_file()
    assert zip_path.is_file()


def test_only_authoritative_failure_enables_formal_defect_report(tmp_path: Path) -> None:
    package_dir, _zip_path, payload = build_package(
        _report(tmp_path, authoritative=True),
        _config(tmp_path),
        tmp_path / "outbox",
    )
    findings = {row["slot_code"]: row for row in payload["findings"]}
    assert payload["overall"]["decision"] == "FAIL"
    assert payload["overall"]["formal_defect_report_allowed"] is True
    assert findings["HBM-04"]["confirmed_defect"] is True
    assert findings["HBM-04"]["primary_defect_code"] == "COMPONENT_MISSING"
    assert findings["PM-01"]["confirmed_defect"] is False
    assert (package_dir / "raw/hybrid_report.json").is_file()


def test_identical_result_can_be_retried_without_creating_a_duplicate(tmp_path: Path) -> None:
    report = _report(tmp_path)
    config = _config(tmp_path)
    first_dir, first_zip, first_payload = build_package(
        report,
        config,
        tmp_path / "outbox",
        production_cycle_id="CYCLE-RETRY",
    )
    second_dir, second_zip, second_payload = build_package(
        report,
        config,
        tmp_path / "outbox",
        production_cycle_id="CYCLE-RETRY",
    )
    assert second_dir == first_dir
    assert second_zip == first_zip
    assert second_payload["inspection_id"] == first_payload["inspection_id"]


def test_http_delivery_sends_idempotent_multipart(tmp_path: Path, monkeypatch) -> None:
    package_dir, _zip_path, payload = build_package(
        _report(tmp_path), _config(tmp_path), tmp_path / "outbox"
    )
    received: dict[str, object] = {}

    class Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({'data': {'stored': True, 'production_applied': False,
                'inspection_id': payload['inspection_id'], 'idempotency_key': payload['idempotency_key']}}).encode()

    def fake_urlopen(request, timeout: float):
        received["headers"] = {
            key.lower(): value for key, value in request.header_items()
        }
        received["body"] = request.data
        received["timeout"] = timeout
        return Response()

    from types import SimpleNamespace
    monkeypatch.setattr(exporter.urlrequest, "build_opener", lambda *args: SimpleNamespace(open=fake_urlopen))
    receipt = send_package(
        "http://db.example/api/v1/vision-inspections",
        package_dir,
        payload,
        token="test-token",
        timeout_seconds=5.0,
    )

    headers = received["headers"]
    body = received["body"]
    assert isinstance(headers, dict)
    assert isinstance(body, bytes)
    assert headers["idempotency-key"] == payload["idempotency_key"]
    assert headers["x-ksmc-schema"] == "ksmc.vision-inspection.v1"
    assert headers["authorization"] == "Bearer test-token"
    assert received["timeout"] == 5.0
    assert b'name="metadata"' in body
    assert b'name="image_annotated_report"' in body
    assert b'name="raw_hybrid_report"' in body
    assert receipt["http_status"] == 201
    assert (package_dir / "delivery_receipt.json").is_file()


def test_report_bytes_are_one_snapshot_even_when_live_file_changes(tmp_path, monkeypatch):
    report = _report(tmp_path)
    config = _config(tmp_path)
    original = report.read_bytes()
    original_hash = exporter._sha256
    def mutate_after_parse(path):
        if Path(path).name.startswith('s22_inspection_roi_'):
            changed = json.loads(original)
            changed['reason'] = 'a later inspection'
            report.write_text(json.dumps(changed))
        return original_hash(path)
    monkeypatch.setattr(exporter, '_sha256', mutate_after_parse)
    folder, _, payload = build_package(report, config, tmp_path/'out', create_archive=False)
    assert (folder/'raw/hybrid_report.json').read_bytes() == original
    assert payload['source']['hybrid_report_sha256'] == hashlib.sha256(original).hexdigest()


def test_input_replaced_during_copy_is_rejected(tmp_path, monkeypatch):
    report = _report(tmp_path)
    config = _config(tmp_path)
    copy = exporter.shutil.copy2
    def replacing_copy(source, destination, *args, **kwargs):
        if Path(destination).name.startswith('01_source_roi'):
            Path(source).write_bytes(b'replaced after hash verification')
        return copy(source, destination, *args, **kwargs)
    monkeypatch.setattr(exporter.shutil, 'copy2', replacing_copy)
    with pytest.raises(exporter.ExportError, match='Source ROI.*changed'):
        build_package(report, config, tmp_path/'out', create_archive=False)
    assert not list((tmp_path/'out').glob('*/inspection_result.json'))


def test_retry_rejects_modified_metadata_and_archive(tmp_path):
    report, config = _report(tmp_path), _config(tmp_path)
    folder, archive, payload = build_package(report, config, tmp_path/'out')
    metadata = folder/'inspection_result.json'
    original = metadata.read_bytes()
    payload['overall']['decision'] = 'PASS'
    metadata.write_text(json.dumps(payload))
    with pytest.raises(exporter.ExportError, match='integrity'):
        build_package(report, config, tmp_path/'out')
    metadata.write_bytes(original)
    archive.write_bytes(b'corrupt archive')
    with pytest.raises(exporter.ExportError, match='archive.*integrity'):
        build_package(report, config, tmp_path/'out')


@pytest.mark.parametrize('kind', ['absolute', 'traversal', 'symlink'])
def test_package_references_cannot_read_outside_package(tmp_path, kind):
    folder, _, payload = build_package(_report(tmp_path), _config(tmp_path),
                                       tmp_path/'out', create_archive=False)
    outside = tmp_path/'outside.png'
    outside.write_bytes(b'outside file must never be packaged')
    if kind == 'absolute':
        payload['images'][0]['file'] = str(outside)
    elif kind == 'traversal':
        payload['images'][0]['file'] = '../../outside.png'
    else:
        image = folder/payload['images'][0]['file']
        image.unlink()
        image.symlink_to(outside)
    with pytest.raises(exporter.ExportError):
        exporter._multipart_body(folder, payload)


@pytest.mark.parametrize('field,value', [
    ('registration', {'alignment_valid': 'false'}),
    ('capture_quality', {'blocks_decision': 'false'}),
    ('slots', [None] * 25),
])
def test_invalid_source_field_types_are_export_errors(tmp_path, field, value):
    report = _report(tmp_path)
    raw = json.loads(report.read_text())
    raw[field] = value
    report.write_text(json.dumps(raw))
    with pytest.raises(exporter.ExportError):
        build_package(report, _config(tmp_path), tmp_path/'out', create_archive=False)


def test_invalid_slot_status_and_duplicate_external_codes_are_rejected(tmp_path):
    report, config = _report(tmp_path), _config(tmp_path)
    raw = json.loads(report.read_text())
    raw['slots'][1]['status'] = 'NOT_A_DECISION'
    report.write_text(json.dumps(raw))
    with pytest.raises(exporter.ExportError, match='slot status'):
        build_package(report, config, tmp_path/'out', create_archive=False)
    raw['slots'][1]['status'] = 'UNKNOWN'
    raw['slots'][2]['slot_id'] = 'hbm_1'
    report.write_text(json.dumps(raw))
    with pytest.raises(exporter.ExportError, match='duplicate external slot'):
        build_package(report, config, tmp_path/'out', create_archive=False)


@pytest.mark.parametrize('relative', ['/etc/passwd', '../outside.png', 'images/../../outside.png'])
def test_manifest_paths_are_confined_before_reading(tmp_path, relative):
    with pytest.raises(exporter.ExportError, match='file reference'):
        exporter._package_file(tmp_path, relative)
