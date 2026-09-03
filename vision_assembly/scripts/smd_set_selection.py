#!/usr/bin/env python3
"""Select one physical SMD set from a multi-set close-view layout."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def select_smd_set(
    items: Sequence[dict],
    layout: Mapping,
    set_index: int,
) -> list[dict]:
    """Return one configured row ordered left-to-right.

    ``required_count`` describes the full two-set fixture capacity. A cycle
    selects only ``parts_per_set`` detections, so the other set may be empty or
    populated without changing the cycle contract.
    """
    set_count = int(layout["set_count"])
    parts_per_set = int(layout["parts_per_set"])
    capacity = int(layout["required_count"])
    ranges = layout["canonical_y_ranges"]
    if set_count < 1 or parts_per_set < 1 or capacity != set_count * parts_per_set:
        raise RuntimeError("invalid SMD multi-set layout counts")
    if len(ranges) != set_count or not 1 <= set_index <= set_count:
        raise RuntimeError(f"SMD set index {set_index} is outside 1..{set_count}")

    low, high = map(float, ranges[set_index - 1])
    if not low < high:
        raise RuntimeError(f"invalid canonical Y range for SMD set {set_index}")
    selected = []
    for item in items:
        center = item.get("center")
        if center is None or len(center) != 2:
            raise RuntimeError("SMD detection has no canonical center")
        y = float(center[1])
        if low <= y < high:
            selected.append(item)
    if len(selected) != parts_per_set:
        raise RuntimeError(
            f"SMD set {set_index} requires {parts_per_set} detections in "
            f"canonical Y [{low}, {high}), got {len(selected)}"
        )
    return sorted(selected, key=lambda item: float(item["center"][0]))
