import os
import threading
from datetime import datetime

_write_lock = threading.Lock()


def diagnostic_log_path() -> str:
    base_dir = os.environ.get("LOCALAPPDATA") or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "HelldiversStratagems", "plugin_events.log")


def write_diagnostic(message: str) -> None:
    """Write an unbuffered plugin event trace independent of logging config."""
    path = diagnostic_log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        line = f"{datetime.now().isoformat(timespec='milliseconds')} pid={os.getpid()} {message}\n"
        with _write_lock, open(path, "a", encoding="utf-8", buffering=1) as trace_file:
            trace_file.write(line)
            trace_file.flush()
            os.fsync(trace_file.fileno())
    except Exception:
        # Diagnostics must never terminate the Stream Deck plugin.
        pass
