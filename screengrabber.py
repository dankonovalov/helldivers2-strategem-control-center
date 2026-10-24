from __future__ import annotations


def split_loadout_zone(zone: dict[str, int], slot_count: int = 4) -> list[dict[str, int]]:
    """Split one rectangle around the loadout into equal horizontal slots."""
    x = int(zone["x"])
    width = int(zone["width"])
    boundaries = [round(x + width * index / slot_count) for index in range(slot_count + 1)]
    return [
        {
            "x": boundaries[index],
            "y": int(zone["y"]),
            "width": boundaries[index + 1] - boundaries[index],
            "height": int(zone["height"]),
        }
        for index in range(slot_count)
    ]
