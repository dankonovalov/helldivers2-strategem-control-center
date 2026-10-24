from __future__ import annotations

import argparse
import logging
import os
import sys

from config_store import load_last_state, load_runtime_config
from diagnostics import diagnostic_log_path, write_diagnostic
from input_sender import StratagemKeySender
from stratagem_catalog import StratagemCatalog
from streamdeck_client import StreamDeckPluginClient

BASE_DIR = (
    os.path.dirname(os.path.dirname(sys.executable))
    if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__))
)
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", BASE_DIR), "HelldiversStratagems")
os.makedirs(LOG_DIR, exist_ok=True)

handlers: list[logging.Handler] = [
    logging.FileHandler(os.path.join(LOG_DIR, "helldivers_parser.log"), encoding="utf-8")
]
if sys.stdout is not None:
    handlers.insert(0, logging.StreamHandler(sys.stdout))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=handlers,
    force=True,
)
logger = logging.getLogger("HelldiversParser.Plugin")


def parse_streamdeck_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-port", type=int)
    parser.add_argument("-pluginUUID")
    parser.add_argument("-registerEvent", default="registerPlugin")
    parser.add_argument("-info")
    return parser.parse_known_args()[0]


def load_config() -> dict:
    config, source = load_runtime_config(CONFIG_FILE)
    logger.info("Loaded configuration from %s", source)
    return config


def normalized_state() -> dict[int, str]:
    return {
        int(slot): name
        for slot, name in load_last_state().items()
        if str(slot).isdigit() and isinstance(name, str) and name
    }


def main() -> int:
    args = parse_streamdeck_arguments()
    write_diagnostic(
        "START "
        f"frozen={getattr(sys, 'frozen', False)} "
        f"port={args.port} plugin_uuid={args.pluginUUID or 'missing'} "
        f"trace={diagnostic_log_path()}"
    )

    try:
        config = load_config()
    except (OSError, ValueError) as exc:
        logger.error("Could not load configuration: %s", exc)
        return 1

    library_dir = config.get("matching", {}).get("stratagem_library_dir", "stratagem_library")
    if not os.path.isabs(library_dir):
        library_dir = os.path.join(BASE_DIR, library_dir)
    catalog = StratagemCatalog(os.path.join(library_dir, "stratagems.json"))

    input_config = config.get("input", {})
    key_sender = StratagemKeySender(
        key_press_seconds=input_config.get("key_press_seconds", 0.055),
        key_gap_seconds=input_config.get("key_gap_seconds", 0.045),
        repeated_key_gap_seconds=input_config.get("repeated_key_gap_seconds", 0.08),
        ctrl_settle_seconds=input_config.get("ctrl_settle_seconds", 0.08),
        cooldown_seconds=input_config.get("cooldown_seconds", 0.75),
    )
    current_state = normalized_state()
    current_state[4] = "reinforce"
    current_state[5] = "resupply"
    current_state[6] = "hellbomb"

    def execute_slot(slot: int) -> bool:
        stratagem_name = current_state.get(slot)
        if not stratagem_name:
            write_diagnostic(f"SLOT {slot + 1} FAILED no persisted stratagem")
            return False
        code = catalog.get_code(stratagem_name)
        if not code:
            write_diagnostic(f"SLOT {slot + 1} FAILED stratagem={stratagem_name} code=missing")
            return False
        write_diagnostic(f"SLOT {slot + 1} stratagem={stratagem_name} code={' '.join(code)}")
        result = key_sender.execute(code)
        write_diagnostic(f"SLOT {slot + 1} RESULT success={result}")
        return result

    streamdeck_config = config.get("streamdeck", {})
    client = StreamDeckPluginClient(
        library_dir=library_dir,
        use_mock=(streamdeck_config.get("use_mock", True) if args.port is None else False),
        port=args.port,
        plugin_uuid=args.pluginUUID,
        register_event=args.registerEvent,
        on_key_down=execute_slot,
    )

    for slot, name in current_state.items():
        client.update_button_icon(slot, name)

    poll_seconds = max(0.1, float(config.get("loop_delay_seconds", 0.5)))
    try:
        while not client.wait_until_closed(poll_seconds):
            latest_state = normalized_state()
            latest_state[4] = "reinforce"
            latest_state[5] = "resupply"
            latest_state[6] = "hellbomb"
            for slot, name in latest_state.items():
                if current_state.get(slot) != name:
                    client.update_button_icon(slot, name)
            current_state = latest_state
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
