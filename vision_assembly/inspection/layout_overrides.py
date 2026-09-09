"""Pure helpers for merging measured PCB slots into CAD candidate layouts."""

from __future__ import annotations

import copy
from typing import Any


def apply_component_slot_overrides(
    layout: dict[str, Any],
    physical_board: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Merge measured physical slots into a Unity-derived layout.

    Unity remains the source for nominal part dimensions and heights. A slot
    listed in ``component_slot_overrides`` gets its physical centre,
    orientation, and optional physical footprint from ``physical_board``.
    Missing or mismatched IDs fail closed instead of silently exporting a
    known-wrong CAD candidate.
    """
    merged = copy.deepcopy(layout)
    placements = {
        str(placement["slot_id"]): placement
        for placement in merged.get("placements", [])
    }
    applied: list[str] = []
    groups = physical_board.get("component_slot_overrides", {})
    for component_type, group in groups.items():
        source = str(group.get("source", "physical_board.json"))
        status = str(group.get("status", "physical override"))
        for override in group.get("slots", []):
            slot_id = str(override["slot_id"])
            placement = placements.get(slot_id)
            if placement is None:
                raise ValueError(f"physical override references unknown slot: {slot_id}")
            if placement.get("component_type") != component_type:
                raise ValueError(
                    f"physical override type mismatch for {slot_id}: "
                    f"expected {placement.get('component_type')}, got {component_type}"
                )
            placement["center_board_mm"] = {
                "x": float(override["x_mm"]),
                "y": float(override["y_mm"]),
            }
            placement["long_axis_deg_in_board"] = float(
                override["long_axis_board_deg"]
            )
            if "nominal_size_mm" in override:
                placement["nominal_size_mm"] = {
                    key: float(value)
                    for key, value in override["nominal_size_mm"].items()
                }
            placement["coordinate_source"] = source
            placement["coordinate_status"] = status
            applied.append(slot_id)
    return merged, applied
