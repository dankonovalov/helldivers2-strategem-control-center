import json
import os

APP_FOLDER_NAME = "HelldiversStratagems"


def shared_config_path() -> str | None:
    """Return a config path shared by the GUI and the installed plugin."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None
    return os.path.join(local_app_data, APP_FOLDER_NAME, "config.json")


def load_config_file(path: str) -> dict:
    with open(path, encoding="utf-8") as config_file:
        return json.load(config_file)


def load_runtime_config(bundled_path: str) -> tuple[dict, str]:
    """Prefer live user calibration, falling back to the bundled config."""
    shared_path = shared_config_path()
    for candidate in (shared_path, bundled_path):
        if candidate and os.path.exists(candidate):
            return load_config_file(candidate), candidate
    raise FileNotFoundError(bundled_path)


def save_shared_config(config: dict) -> str | None:
    shared_path = shared_config_path()
    if not shared_path:
        return None
    os.makedirs(os.path.dirname(shared_path), exist_ok=True)
    with open(shared_path, "w", encoding="utf-8") as config_file:
        json.dump(config, config_file, indent=4)
    return shared_path


def last_state_path() -> str | None:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None
    return os.path.join(local_app_data, APP_FOLDER_NAME, "last_state.json")


def load_last_state() -> dict:
    state_path = last_state_path()
    if not state_path or not os.path.exists(state_path):
        return {}
    try:
        data = load_config_file(state_path)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_last_state(state: dict) -> str | None:
    state_path = last_state_path()
    if not state_path:
        return None
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    temporary_path = state_path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as state_file:
        json.dump(state, state_file, indent=4)
    os.replace(temporary_path, state_path)
    return state_path
