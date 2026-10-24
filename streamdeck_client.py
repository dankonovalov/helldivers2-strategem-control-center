import base64
import json
import logging
import os
import threading
from collections.abc import Callable
from contextlib import suppress

from diagnostics import write_diagnostic

logger = logging.getLogger("HelldiversParser.StreamDeckPlugin")

ACTION_TO_SLOT = {
    "com.super-earth.helldivers2.stratagem.slot1": 0,
    "com.super-earth.helldivers2.stratagem.slot2": 1,
    "com.super-earth.helldivers2.stratagem.slot3": 2,
    "com.super-earth.helldivers2.stratagem.slot4": 3,
    "com.super-earth.helldivers2.stratagem.reinforce": 4,
    "com.super-earth.helldivers2.stratagem.resupply": 5,
    "com.super-earth.helldivers2.stratagem.hellbomb": 6,
}


class StreamDeckPluginClient:
    """Stream Deck SDK WebSocket client, compatible with Stream Deck Mobile."""

    def __init__(
        self,
        library_dir: str = "stratagem_library",
        use_mock: bool = True,
        port: int | None = None,
        plugin_uuid: str | None = None,
        register_event: str = "registerPlugin",
        on_key_down: Callable[[int], bool] | None = None,
    ):
        self.library_dir = library_dir
        self.use_mock = use_mock
        self.port = port
        self.plugin_uuid = plugin_uuid
        self.register_event = register_event
        self.on_key_down = on_key_down
        self._ws = None
        self._send_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._contexts: dict[int, str] = {}
        self._desired_images: dict[int, str] = {}
        self._closed = threading.Event()

        if self.use_mock:
            logger.info("Stream Deck plugin client is running in MOCK mode.")
        elif self.port is None or not self.plugin_uuid:
            logger.error(
                "Stream Deck SDK arguments are missing. The official Stream Deck "
                "application must launch this executable as a plugin."
            )
        else:
            self.connect()

    @property
    def connected(self) -> bool:
        return self._ws is not None and self._ws.connected

    def wait_until_closed(self, timeout: float) -> bool:
        """Wait for SDK disconnect; also acts as an interruptible sleep."""
        if self.use_mock:
            self._closed.wait(timeout)
            return False
        return self._closed.wait(timeout)

    def connect(self) -> bool:
        try:
            import websocket

            self._ws = websocket.create_connection(f"ws://127.0.0.1:{self.port}", timeout=5.0)
            self._ws.send(json.dumps({"event": self.register_event, "uuid": self.plugin_uuid}))
            self._ws.settimeout(None)
            threading.Thread(
                target=self._receive_loop,
                name="StreamDeckSDKReceiver",
                daemon=True,
            ).start()
            logger.info("Registered Stream Deck plugin '%s'.", self.plugin_uuid)
            return True
        except ImportError:
            logger.error("Install websocket-client to use the Stream Deck SDK.")
        except Exception as exc:
            logger.error("Could not connect to the Stream Deck application: %s", exc)
        self._ws = None
        return False

    def _receive_loop(self) -> None:
        try:
            while not self._closed.is_set() and self._ws is not None:
                raw_message = self._ws.recv()
                if not raw_message:
                    break
                self._handle_event(json.loads(raw_message))
        except Exception as exc:
            if not self._closed.is_set():
                logger.error("Stream Deck SDK connection closed: %s", exc)
        finally:
            # Wake the parser loop immediately. This is essential for
            # PyInstaller one-file plugins: an orphaned child process keeps the
            # installed .sdPlugin directory locked during an update.
            self._closed.set()

    def _handle_event(self, message: dict) -> None:
        event = message.get("event")
        slot = ACTION_TO_SLOT.get(message.get("action"))
        context = message.get("context")
        if event in ("keyDown", "keyUp"):
            logger.info(
                "SDK %s received: action=%s slot=%s context=%s",
                event,
                message.get("action"),
                slot + 1 if slot is not None else "unknown",
                context or "missing",
            )
            write_diagnostic(
                f"SDK {event} action={message.get('action')} "
                f"slot={slot + 1 if slot is not None else 'unknown'} "
                f"context={'present' if context else 'missing'}"
            )
        if slot is None or not context:
            return

        if event == "willAppear":
            with self._state_lock:
                self._contexts[slot] = context
                desired_image = self._desired_images.get(slot)
            logger.info("Stratagem slot %d appeared.", slot + 1)
            if desired_image is not None:
                self._send_image(context, desired_image)
        elif event == "willDisappear":
            with self._state_lock:
                if self._contexts.get(slot) == context:
                    self._contexts.pop(slot, None)
        elif event == "keyDown" and self.on_key_down is not None:
            threading.Thread(
                target=self._invoke_key_down,
                args=(slot, context),
                name=f"StratagemKeySender-{slot + 1}",
                daemon=True,
            ).start()

    def _invoke_key_down(self, slot: int, context: str) -> None:
        try:
            success = bool(self.on_key_down(slot)) if self.on_key_down else False
        except Exception as exc:
            logger.error("Key handler failed for slot %d: %s", slot + 1, exc, exc_info=True)
            write_diagnostic(f"HANDLER slot={slot + 1} EXCEPTION {exc!r}")
            success = False
        write_diagnostic(f"HANDLER slot={slot + 1} feedback={'showOk' if success else 'showAlert'}")
        self._send_event("showOk" if success else "showAlert", context)

    def _send_event(self, event: str, context: str) -> bool:
        if not self.connected:
            return False
        try:
            with self._send_lock:
                self._ws.send(json.dumps({"event": event, "context": context}))
            return True
        except Exception as exc:
            logger.error("Could not send %s: %s", event, exc)
            return False

    def update_button_icon(self, slot: int, stratagem_name: str | None) -> bool:
        image_data_url = ""
        if stratagem_name:
            image_path = self._find_icon(stratagem_name)
            if not image_path:
                logger.error("No PNG icon found for '%s'.", stratagem_name)
                return False
            try:
                with open(image_path, "rb") as image_file:
                    encoded = base64.b64encode(image_file.read()).decode("ascii")
                image_data_url = f"data:image/png;base64,{encoded}"
            except OSError as exc:
                logger.error("Could not read icon %s: %s", image_path, exc)
                return False

        if self.use_mock:
            logger.info(
                "[MOCK Stream Deck] Slot %d <- %s",
                slot + 1,
                stratagem_name or "empty",
            )
            return True

        with self._state_lock:
            self._desired_images[slot] = image_data_url
            context = self._contexts.get(slot)

        # The parser may identify an icon before Stream Deck Mobile opens the page.
        # It is cached and sent when willAppear supplies the instance context.
        if context is None:
            return self.connected
        return self._send_image(context, image_data_url)

    def _send_image(self, context: str, image_data_url: str) -> bool:
        if not self.connected:
            return False
        message = {
            "event": "setImage",
            "context": context,
            "payload": {"image": image_data_url, "target": 0},
        }
        try:
            with self._send_lock:
                self._ws.send(json.dumps(message))
            return True
        except Exception as exc:
            logger.error("Could not send setImage: %s", exc)
            return False

    def _find_icon(self, stratagem_name: str) -> str | None:
        expected = f"{stratagem_name}.png".lower()
        for root, _, files in os.walk(self.library_dir):
            for filename in files:
                if filename.lower() == expected:
                    return os.path.join(root, filename)
        return None

    def close(self) -> None:
        self._closed.set()
        websocket_connection = self._ws
        self._ws = None
        if websocket_connection is not None:
            with suppress(Exception):
                websocket_connection.close()
