from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger("HelldiversParser.StratagemCatalog")

NAME_ALIASES = {
    "anti_material_rifle": "anti_materiel_rifle",
    "eagle_re_arm": "eagle_rearm",
    "ems_sentry": "ems_mortar_sentry",
    "illumination_flare": "orbital_illumination_flare",
    "machine_sentry": "machine_gun_sentry",
    "spear_launcher": "spear",
}


def normalize_stratagem_key(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return NAME_ALIASES.get(key, key)


class StratagemCatalog:
    """Load stratagem names and input sequences without image dependencies."""

    def __init__(self, mapping_file: str | Path) -> None:
        self.mapping_file = Path(mapping_file)
        self.stratagem_data: dict[str, dict[str, Any]] = {}
        self.display_names: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        self.stratagem_data.clear()
        self.display_names.clear()

        try:
            with self.mapping_file.open(encoding="utf-8") as mapping:
                data = json.load(mapping)
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Could not load %s: %s", self.mapping_file, exc)
            return

        compact_records = data.get("stratagems", {})
        if isinstance(compact_records, dict) and compact_records:
            for key, record in compact_records.items():
                if not isinstance(record, dict):
                    continue
                normalized_key = normalize_stratagem_key(key)
                metadata = dict(record)
                metadata.setdefault("name", record.get("display_name", key))
                self._add(normalized_key, metadata)
        else:
            for category, records in data.items():
                if not isinstance(records, list):
                    continue
                for record in records:
                    if not isinstance(record, dict) or not record.get("name"):
                        continue
                    metadata = dict(record)
                    metadata["category"] = category
                    self._add(normalize_stratagem_key(record["name"]), metadata)

        logger.info(
            "Loaded %d stratagem records from %s",
            len(self.stratagem_data),
            self.mapping_file,
        )

    def _add(self, key: str, metadata: dict[str, Any]) -> None:
        self.stratagem_data[key] = metadata
        self.display_names[key] = str(metadata.get("name", key))

    def get_display_name(self, key: str | None) -> str | None:
        if not key:
            return None
        return self.display_names.get(key, key.replace("_", " ").title())

    def get_code(self, key: str | None) -> list[str]:
        if not key:
            return []
        code = self.stratagem_data.get(key, {}).get("code", [])
        return [str(direction).lower() for direction in code]

    def get_stratagem_info(self, key: str | None) -> dict[str, Any]:
        if not key:
            return {}
        return dict(self.stratagem_data.get(key, {}))
