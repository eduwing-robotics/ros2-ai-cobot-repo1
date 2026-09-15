import json

import pytest

from fr5_process_sequences.real_contract import (
    Action,
    ContractError,
    ContractLimits,
    Event,
    OperationEvent,
    parse_operation,
)


JOB = "11111111-1111-4111-8111-111111111111"
OP = "22222222-2222-4222-8222-222222222222"


def pick(**overrides):
    payload = {
        "job_id": JOB,
        "operation_id": OP,
        "action": "robot.pick",
        "order": 1,
        "part_id": "HBM",
        "slot_code": "HBM-01",
        "approach_dz_mm": 100.0,
        "retract_dz_mm": 100.0,
        "grasp_opening_percent": 18.0,
        "release_opening_percent": 25.0,
    }
    payload.update(overrides)
    return payload


def test_pick_contract_round_trips_without_cartesian_coordinates():
    operation = parse_operation(json.dumps(pick()))
    assert operation.action is Action.PICK
    assert operation.order == 1
    assert operation.part_id == "HBM"
    assert operation.slot_code == "HBM-01"
    assert "x" not in operation.to_dict()


def test_rejects_sequencer_cartesian_fields_and_missing_required_fields():
    with pytest.raises(ContractError, match="unexpected fields"):
        parse_operation(pick(x_mm=100.0, rz_deg=90.0))
    payload = pick()
    del payload["slot_code"]
    with pytest.raises(ContractError, match="missing fields"):
        parse_operation(payload)


def test_rejects_invalid_uuid_range_and_opening():
    with pytest.raises(ContractError, match="valid UUID"):
        parse_operation(pick(job_id="not-a-uuid"))
    with pytest.raises(ContractError, match="approach_dz_mm"):
        parse_operation(pick(approach_dz_mm=201.0))
    with pytest.raises(ContractError, match="release_opening_percent"):
        parse_operation(pick(release_opening_percent=101.0))


def test_backend_owned_limits_are_configurable_without_yaml():
    limits = ContractLimits(maximum_approach_dz_mm=120.0)
    assert parse_operation(pick(approach_dz_mm=120.0), limits=limits).approach_dz_mm == 120.0


def test_move_joint_requires_six_finite_degree_values():
    payload = {
        "job_id": JOB,
        "operation_id": OP,
        "action": "robot.move_joint",
        "joint_point": [1, 2, 3, 4, 5, 6],
    }
    assert parse_operation(payload).joint_point == (1, 2, 3, 4, 5, 6)
    payload["joint_point"] = [1, 2, 3]
    with pytest.raises(ContractError, match="J1 through J6"):
        parse_operation(payload)


def test_transfer_and_place_exact_shapes_are_accepted():
    place = {
        "job_id": JOB,
        "operation_id": OP,
        "action": "robot.place",
        "order": 1,
        "part_id": "HBM",
        "slot_code": "HBM-01",
        "approach_dz_mm": 100.0,
        "retract_dz_mm": 100.0,
        "release_opening_percent": 25.0,
    }
    assert parse_operation(place).action is Action.PLACE
    transfer = {
        "job_id": JOB,
        "operation_id": OP,
        "action": "robot.transfer",
        "object_id": "assembled_pcb",
        "approach_dz_mm": 100.0,
        "retract_dz_mm": 100.0,
        "assembled_pcb_drop_approach_dz_mm": 150.0,
        "grasp_opening_percent": 0.0,
        "release_opening_percent": 100.0,
    }
    assert parse_operation(transfer).action is Action.TRANSFER


def test_event_json_has_required_callback_fields():
    callback = OperationEvent(
        JOB, OP, "robot.pick", "RETRACT", Event.OPERATION_COMPLETED
    )
    assert json.loads(callback.to_json()) == {
        "job_id": JOB,
        "operation_id": OP,
        "action": "robot.pick",
        "phase": "RETRACT",
        "event": "OPERATION_COMPLETED",
        "error_code": "",
        "message": "",
    }
