from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("HelldiversI18n")

SUPPORTED_LANGUAGES = ("uk", "en")
DEFAULT_LANGUAGE = "uk"


def _resource_roots() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    roots.append(Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)))
    return list(dict.fromkeys(roots))


class Translator:
    """Load small JSON dictionaries and resolve dotted translation keys."""

    def __init__(self, language: str = DEFAULT_LANGUAGE) -> None:
        self._catalogs = {code: self._load_catalog(code) for code in SUPPORTED_LANGUAGES}
        self.language = DEFAULT_LANGUAGE
        self.set_language(language)

    def _load_catalog(self, language: str) -> dict[str, object]:
        for root in _resource_roots():
            path = root / "locales" / f"{language}.json"
            if not path.is_file():
                continue
            try:
                with path.open(encoding="utf-8") as stream:
                    data = json.load(stream)
                if isinstance(data, dict):
                    return data
            except (OSError, json.JSONDecodeError):
                logger.exception("Failed to load translation catalog: %s", path)
        logger.error("Translation catalog not found: %s", language)
        return {}

    def set_language(self, language: str) -> None:
        self.language = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

    def translate(self, key: str, **values: object) -> str:
        translated = self._resolve(self._catalogs.get(self.language, {}), key)
        if translated is None:
            translated = self._resolve(self._catalogs.get("en", {}), key)
        text = translated if isinstance(translated, str) else key
        try:
            return text.format(**values)
        except (KeyError, ValueError):
            logger.warning("Invalid translation placeholders for key: %s", key)
            return text

    @staticmethod
    def _resolve(catalog: dict[str, object], key: str) -> object | None:
        value: object = catalog
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
        return value


def normalized_language(value: object) -> str:
    if isinstance(value, str):
        code = value.strip().lower()
        code = "uk" if code == "ua" else code
        if code in SUPPORTED_LANGUAGES:
            return code
    system_language = os.environ.get("LANG", "").lower()
    return "uk" if system_language.startswith("uk") else DEFAULT_LANGUAGE
