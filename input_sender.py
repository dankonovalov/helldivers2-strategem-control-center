import ctypes
import logging
import sys
import threading
import time
from collections.abc import Iterable
from ctypes import wintypes

from diagnostics import write_diagnostic

logger = logging.getLogger("HelldiversParser.InputSender")

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INPUT_KEYBOARD = 1

# Physical scan codes for the default Helldivers 2 stratagem bindings.
DIRECTION_SCAN_CODES = {
    "up": 0x11,  # W
    "left": 0x1E,  # A
    "down": 0x1F,  # S
    "right": 0x20,  # D
}
LEFT_CTRL_SCAN_CODE = 0x1D


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.WPARAM),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.WPARAM),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


class StratagemKeySender:
    """Send Ctrl-held stratagem sequences using native Windows SendInput."""

    def __init__(
        self,
        key_press_seconds: float = 0.055,
        key_gap_seconds: float = 0.045,
        repeated_key_gap_seconds: float = 0.08,
        ctrl_settle_seconds: float = 0.08,
        cooldown_seconds: float = 0.75,
    ):
        self.key_press_seconds = max(0.01, float(key_press_seconds))
        self.key_gap_seconds = max(0.01, float(key_gap_seconds))
        self.repeated_key_gap_seconds = max(
            self.key_gap_seconds,
            float(repeated_key_gap_seconds),
        )
        self.ctrl_settle_seconds = max(0.01, float(ctrl_settle_seconds))
        self.cooldown_seconds = max(0.0, float(cooldown_seconds))
        self._execution_lock = threading.Lock()
        self._blocked_until = 0.0

    def execute(self, directions: Iterable[str]) -> bool:
        normalized = [str(direction).strip().lower() for direction in directions]
        if not normalized or any(item not in DIRECTION_SCAN_CODES for item in normalized):
            logger.error("Invalid or empty stratagem sequence: %s", normalized)
            write_diagnostic(f"INPUT FAILED invalid_sequence={normalized!r}")
            return False
        if sys.platform != "win32":
            logger.error("Stratagem key execution is supported only on Windows.")
            return False
        if not self._execution_lock.acquire(blocking=False):
            logger.warning("Another stratagem sequence is already running; press ignored.")
            write_diagnostic("INPUT FAILED another sequence is running")
            return False

        pressed_scan_codes = []
        try:
            remaining_cooldown = self._blocked_until - time.monotonic()
            if remaining_cooldown > 0:
                write_diagnostic(f"INPUT IGNORED cooldown remaining={remaining_cooldown:.3f}s")
                return False

            write_diagnostic(f"INPUT BEGIN ctrl + {' '.join(normalized)}")
            self._send_scan_code(LEFT_CTRL_SCAN_CODE, key_up=False)
            pressed_scan_codes.append(LEFT_CTRL_SCAN_CODE)
            time.sleep(self.ctrl_settle_seconds)
            for index, direction in enumerate(normalized):
                scan_code = DIRECTION_SCAN_CODES[direction]
                self._send_scan_code(scan_code, key_up=False)
                pressed_scan_codes.append(scan_code)
                time.sleep(self.key_press_seconds)
                self._send_scan_code(scan_code, key_up=True)
                pressed_scan_codes.remove(scan_code)
                # A delay is useful between inputs, but after the final input it
                # keeps Ctrl held while the game is already selecting the ball.
                if index < len(normalized) - 1:
                    next_direction = normalized[index + 1]
                    gap = (
                        self.repeated_key_gap_seconds
                        if next_direction == direction
                        else self.key_gap_seconds
                    )
                    time.sleep(gap)

            # Release Ctrl immediately after the final direction. File logging
            # uses fsync and must not delay this key-up.
            self._send_scan_code(LEFT_CTRL_SCAN_CODE, key_up=True)
            pressed_scan_codes.remove(LEFT_CTRL_SCAN_CODE)
            self._blocked_until = time.monotonic() + self.cooldown_seconds
            logger.info("Executed Ctrl + %s", " ".join(normalized))
            write_diagnostic(f"INPUT SENT ctrl + {' '.join(normalized)}")
            return True
        except Exception as exc:
            logger.error("Could not execute stratagem sequence: %s", exc, exc_info=True)
            write_diagnostic(f"INPUT EXCEPTION {exc!r}")
            return False
        finally:
            # If an exception occurs after any key-down, release every key that
            # this sequence injected. Ctrl is last because it owns the menu.
            for scan_code in reversed(pressed_scan_codes):
                try:
                    self._send_scan_code(scan_code, key_up=True)
                except Exception:
                    logger.exception("Could not release scan code 0x%02X", scan_code)
                    write_diagnostic(f"INPUT CLEANUP FAILED scan_code=0x{scan_code:02X}")
            self._execution_lock.release()

    @staticmethod
    def _send_scan_code(scan_code: int, key_up: bool) -> None:
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if key_up else 0)
        # Python 3.14 no longer coerces None to the integer-sized WPARAM
        # field. dwExtraInfo is optional for our synthetic input, so use 0.
        keyboard = KEYBDINPUT(0, scan_code, flags, 0, 0)
        input_event = INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=keyboard))
        sent = ctypes.windll.user32.SendInput(1, ctypes.byref(input_event), ctypes.sizeof(INPUT))
        if sent != 1:
            raise ctypes.WinError()
