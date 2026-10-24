from __future__ import annotations

import ctypes
import json
import logging
import os
import sys
import threading
import time
from collections.abc import Callable

try:
    from PyQt6.QtCore import QPoint, QRect, Qt, QTimer, pyqtSignal
    from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPen
    from PyQt6.QtWidgets import (
        QApplication,
        QComboBox,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:
    startup_dir = (
        os.path.dirname(sys.executable)
        if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__))
    )
    try:
        with open(
            os.path.join(startup_dir, "startup_error.txt"),
            "w",
            encoding="utf-8",
        ) as error_file:
            error_file.write(f"PyQt6 import failed: {exc!r}\n")
    except OSError:
        pass
    raise

import cv2
import mss
import numpy as np

from config_store import (
    load_last_state,
    load_runtime_config,
    save_last_state,
    save_shared_config,
    shared_config_path,
)
from i18n import Translator, normalized_language
from parser import StratagemParser
from screengrabber import split_loadout_zone

logger = logging.getLogger("HelldiversApp")

APP_DIR = (
    os.path.dirname(sys.executable)
    if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__))
)
APP_ICON_PATH = os.path.join(APP_DIR, "app_icon.ico")

COLOR_VOID = "#090A0B"
COLOR_PANEL = "#111315"
COLOR_PANEL_ELEVATED = "#17191B"
COLOR_BORDER = "#25282B"
COLOR_TEXT = "#E6E7E5"
COLOR_MUTED = "#8A8D8F"
COLOR_YELLOW = "#FFE900"
COLOR_GREEN = "#4EE077"
COLOR_WARNING = "#E59F2D"
COLOR_RED = "#AF4141"

APP_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {COLOR_VOID};
    color: {COLOR_TEXT};
    font-family: "Bahnschrift Condensed", "Arial Narrow", sans-serif;
}}
QFrame#brandHeader, QFrame#controlBar, QFrame#settingsPanel {{
    background-color: {COLOR_PANEL_ELEVATED};
    border: 1px solid {COLOR_BORDER};
}}
QFrame#recognitionBlock, QFrame#parserStateBlock {{
    background-color: {COLOR_VOID};
    border: 1px solid {COLOR_BORDER};
}}
QFrame#parserStateBlock[running="true"] {{
    border-color: #285C38;
}}
QFrame#parserStateBlock[running="false"] {{
    border-color: #5C2929;
}}
QFrame#sectionPanel {{
    background-color: {COLOR_PANEL};
    border: 1px solid {COLOR_BORDER};
}}
QLabel#brandMark {{
    background-color: {COLOR_YELLOW};
    color: {COLOR_VOID};
    font-family: Consolas, monospace;
    font-size: 13px;
    font-weight: 700;
    padding: 2px 5px;
}}
QLabel#brandTitle {{
    color: {COLOR_TEXT};
    font-size: 17px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 2px 7px;
}}
QLabel#sectionMark {{
    background-color: {COLOR_YELLOW};
    color: {COLOR_VOID};
    font-family: Consolas, monospace;
    font-weight: 700;
    padding: 0 3px;
}}
QLabel#sectionTitle {{
    color: {COLOR_YELLOW};
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 1px 6px;
}}
QLabel#microLabel, QLabel#secondaryText {{
    color: {COLOR_MUTED};
    font-family: Consolas, monospace;
    font-size: 9px;
    letter-spacing: 1px;
}}
QLabel#headerCode, QLabel#headerStatus {{
    background-color: {COLOR_VOID};
    color: {COLOR_MUTED};
    font-family: Consolas;
    font-size: 9px;
    letter-spacing: 1px;
    padding: 2px 6px;
}}
QLabel#bodyText {{
    background-color: {COLOR_VOID};
    color: {COLOR_TEXT};
    font-size: 12px;
    padding: 5px 8px;
}}
QLabel#formLabel {{
    background-color: {COLOR_VOID};
    color: {COLOR_MUTED};
    font-family: Consolas;
    font-size: 9px;
    letter-spacing: 1px;
    padding: 6px 8px;
}}
QLabel#coordinateValue {{
    background-color: {COLOR_VOID};
    border: 1px solid {COLOR_BORDER};
    color: {COLOR_YELLOW};
    font-family: Consolas, monospace;
    font-size: 13px;
    font-weight: 700;
    padding: 5px 7px;
}}
QLabel#parserBadge {{
    background-color: {COLOR_VOID};
    border: 1px solid {COLOR_BORDER};
    color: {COLOR_RED};
    font-family: Consolas, monospace;
    font-size: 9px;
    font-weight: 700;
    padding: 3px 6px;
}}
QLabel#parserBadge[running="true"] {{
    color: {COLOR_GREEN};
}}
QTabWidget::pane {{
    border: 0;
    background-color: {COLOR_VOID};
    top: -1px;
}}
QTabBar::tab {{
    background-color: {COLOR_PANEL};
    border: 0;
    border-bottom: 2px solid transparent;
    color: {COLOR_MUTED};
    font-size: 12px;
    font-weight: 600;
    min-width: 122px;
    padding: 8px 12px;
}}
QTabBar::tab:hover {{
    color: {COLOR_TEXT};
    background-color: {COLOR_PANEL_ELEVATED};
}}
QTabBar::tab:selected {{
    color: {COLOR_YELLOW};
    background-color: {COLOR_PANEL_ELEVATED};
    border-bottom: 2px solid {COLOR_YELLOW};
}}
QPushButton {{
    background-color: {COLOR_PANEL_ELEVATED};
    border: 1px solid {COLOR_BORDER};
    border-radius: 0;
    color: {COLOR_TEXT};
    font-size: 12px;
    font-weight: 700;
    padding: 7px 12px;
}}
QPushButton:hover {{
    border-color: {COLOR_YELLOW};
    color: {COLOR_YELLOW};
}}
QPushButton:pressed {{
    background-color: #292A2B;
}}
QPushButton#outlineButton {{
    border: 1px solid {COLOR_YELLOW};
    color: {COLOR_YELLOW};
}}
QPushButton#languageButton {{
    background-color: {COLOR_VOID};
    border: 1px solid {COLOR_BORDER};
    color: {COLOR_YELLOW};
    font-family: Consolas;
    font-size: 10px;
    padding: 3px 5px;
}}
QPushButton#languageButton:hover {{
    border-color: {COLOR_YELLOW};
    color: {COLOR_TEXT};
}}
QPushButton#primaryButton {{
    background-color: {COLOR_YELLOW};
    border: 1px solid {COLOR_YELLOW};
    color: {COLOR_VOID};
    font-size: 13px;
    padding: 8px 16px;
}}
QPushButton#primaryButton:hover {{
    background-color: {COLOR_WARNING};
    border-color: {COLOR_WARNING};
    color: {COLOR_VOID};
}}
QPushButton#primaryButton[running="true"] {{
    background-color: {COLOR_PANEL_ELEVATED};
    border-color: {COLOR_RED};
    color: #FFB4AB;
}}
QSpinBox {{
    background-color: {COLOR_VOID};
    border: 1px solid {COLOR_BORDER};
    border-radius: 0;
    color: {COLOR_YELLOW};
    font-family: Consolas, monospace;
    font-size: 13px;
    font-weight: 700;
    min-height: 30px;
    padding: 0 8px;
}}
QSpinBox:focus {{
    border-color: {COLOR_YELLOW};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {COLOR_PANEL_ELEVATED};
    border: 0;
    width: 18px;
}}
QComboBox {{
    background-color: {COLOR_PANEL_ELEVATED};
    border: 1px solid {COLOR_BORDER};
    border-radius: 0;
    color: {COLOR_TEXT};
    font-family: Consolas;
    font-size: 9px;
    min-height: 20px;
    padding: 2px 6px;
}}
QComboBox:hover, QComboBox:focus {{
    border-color: {COLOR_YELLOW};
}}
QComboBox::drop-down {{
    background-color: {COLOR_PANEL};
    border: 0;
    width: 18px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLOR_PANEL_ELEVATED};
    border: 1px solid {COLOR_BORDER};
    color: {COLOR_TEXT};
    selection-background-color: {COLOR_YELLOW};
    selection-color: {COLOR_VOID};
}}
QFrame#slotCard {{
    background-color: {COLOR_VOID};
    border: 1px dashed #3E4348;
}}
QFrame#slotCard[state="accepted"] {{
    background-color: #0D1F14;
    border: 1px solid {COLOR_GREEN};
}}
QFrame#slotCard[state="candidate"] {{
    background-color: #1E170A;
    border: 1px solid {COLOR_WARNING};
}}
QFrame#slotCard[state="manual"] {{
    background-color: #1E1C0A;
    border: 1px solid {COLOR_YELLOW};
}}
QLabel#slotNumber, QLabel#slotState, QLabel#slotScore {{
    color: {COLOR_MUTED};
    font-family: Consolas, monospace;
    font-size: 10px;
    font-weight: 700;
}}
QLabel#slotNumber[state="accepted"], QLabel#slotScore[state="accepted"] {{
    color: {COLOR_GREEN};
}}
QLabel#slotNumber[state="candidate"], QLabel#slotScore[state="candidate"] {{
    color: {COLOR_WARNING};
}}
QLabel#slotNumber[state="manual"], QLabel#slotScore[state="manual"] {{
    color: {COLOR_YELLOW};
}}
QLabel#slotBadge {{
    background-color: #292A2B;
    color: {COLOR_MUTED};
    font-family: Consolas, monospace;
    font-size: 8px;
    font-weight: 700;
    padding: 2px 4px;
}}
QLabel#slotBadge[state="accepted"] {{
    background-color: {COLOR_GREEN};
    color: {COLOR_VOID};
}}
QLabel#slotBadge[state="candidate"] {{
    background-color: {COLOR_WARNING};
    color: {COLOR_VOID};
}}
QLabel#slotBadge[state="manual"] {{
    background-color: {COLOR_YELLOW};
    color: {COLOR_VOID};
}}
QLabel#slotName {{
    color: {COLOR_TEXT};
    font-size: 15px;
    font-weight: 700;
}}
QLabel#statusText {{
    color: {COLOR_RED};
    font-family: Consolas, monospace;
    font-size: 11px;
    font-weight: 700;
}}
QLabel#statusText[running="true"] {{
    color: {COLOR_GREEN};
}}
QMessageBox {{
    background-color: {COLOR_PANEL};
}}
"""


def refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class StratagemSlotCard(QFrame):
    """Compact status tile for one detected loadout slot."""

    manual_selection_changed = pyqtSignal(int, object)

    def __init__(self, slot_index: int, translator: Translator) -> None:
        super().__init__()
        self.slot_index = slot_index
        self.translator = translator
        self.strat_name: str | None = None
        self.score = 0.0
        self.accepted = False
        self.candidates: list[tuple[str, float]] = []
        self.manual_name: str | None = None
        self.setObjectName("slotCard")
        self.setProperty("state", "idle")
        self.setMinimumHeight(112)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(4)
        self.slot_label = QLabel()
        self.slot_label.setObjectName("slotNumber")
        self.badge_label = QLabel()
        self.badge_label.setObjectName("slotBadge")
        top_row.addWidget(self.slot_label)
        top_row.addStretch()
        top_row.addWidget(self.badge_label)
        layout.addLayout(top_row)

        self.state_label = QLabel()
        self.state_label.setObjectName("slotState")
        layout.addWidget(self.state_label)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"color: {COLOR_BORDER};")
        layout.addWidget(divider)

        self.name_label = QLabel()
        self.name_label.setObjectName("slotName")
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label, 1)

        self.candidate_combo = QComboBox()
        self.candidate_combo.currentIndexChanged.connect(self._candidate_selected)
        layout.addWidget(self.candidate_combo)

        score_row = QHBoxLayout()
        self.score_caption = QLabel()
        self.score_caption.setObjectName("microLabel")
        self.score_label = QLabel("---")
        self.score_label.setObjectName("slotScore")
        score_row.addWidget(self.score_caption)
        score_row.addStretch()
        score_row.addWidget(self.score_label)
        layout.addLayout(score_row)
        self.retranslate()

    def set_result(
        self,
        strat_name: str | None,
        score: float,
        accepted: bool,
        candidates: list[tuple[str, float]] | None = None,
    ) -> None:
        self.strat_name = strat_name
        self.score = score
        self.accepted = accepted
        if candidates is not None:
            self.candidates = candidates
        self.retranslate()

    def set_manual_selection(self, strat_name: str | None) -> None:
        self.manual_name = strat_name
        self.retranslate()

    def _candidate_selected(self, index: int) -> None:
        if index < 0:
            return
        selected = self.candidate_combo.itemData(index)
        self.manual_name = selected if isinstance(selected, str) else None
        self.retranslate()
        self.manual_selection_changed.emit(self.slot_index, self.manual_name)

    def retranslate(self) -> None:
        effective_name = self.manual_name or self.strat_name
        effective_score = self.score
        if self.manual_name:
            effective_score = next(
                (
                    score
                    for candidate_name, score in self.candidates
                    if candidate_name == self.manual_name
                ),
                self.score,
            )
            state = "manual"
            state_key = "slots.state_manual"
            badge_key = "slots.badge_manual"
        elif self.accepted and self.strat_name:
            state = "accepted"
            state_key = "slots.state_recognized"
            badge_key = "slots.badge_match"
        elif self.strat_name:
            state = "candidate"
            state_key = "slots.state_candidate"
            badge_key = "slots.badge_candidate"
        else:
            state = "idle"
            state_key = "slots.state_idle"
            badge_key = "slots.badge_idle"

        display_name = (
            effective_name.replace("_", " ").title()
            if effective_name
            else self.translator.translate("slots.no_candidate")
        )
        self.slot_label.setText(
            self.translator.translate("slots.number", number=f"{self.slot_index + 1:02d}")
        )
        self.name_label.setText(display_name)
        self.state_label.setText(self.translator.translate(state_key))
        self.badge_label.setText(self.translator.translate(badge_key))
        self.score_caption.setText(self.translator.translate("slots.score"))
        self.score_label.setText(f"{effective_score:.3f}" if effective_name else "---")
        self._refresh_candidate_combo()

        for widget in (self, self.slot_label, self.state_label, self.badge_label, self.score_label):
            widget.setProperty("state", state)
            refresh_style(widget)

    def _refresh_candidate_combo(self) -> None:
        selected_name = self.manual_name
        self.candidate_combo.blockSignals(True)
        self.candidate_combo.clear()
        self.candidate_combo.addItem(self.translator.translate("slots.auto"), None)
        candidate_names = {name for name, _ in self.candidates}
        candidates = list(self.candidates)
        if selected_name and selected_name not in candidate_names:
            candidates.append((selected_name, self.score))
        for name, score in candidates:
            display_name = name.replace("_", " ").title()
            self.candidate_combo.addItem(f"{display_name} · {score:.3f}", name)
        selected_index = self.candidate_combo.findData(selected_name)
        self.candidate_combo.setCurrentIndex(max(0, selected_index))
        self.candidate_combo.blockSignals(False)


class ScreenSelectorOverlay(QWidget):
    """Full-screen overlay used to select the loadout capture rectangle."""

    selection_finished = pyqtSignal(dict)
    selection_cancelled = pyqtSignal()

    def __init__(self, monitor_geometry: dict, instruction: str):
        super().__init__()
        self.instruction = instruction
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.setGeometry(
            monitor_geometry["left"],
            monitor_geometry["top"],
            monitor_geometry["width"],
            monitor_geometry["height"],
        )

        self.begin = QPoint()
        self.end = QPoint()
        self.is_drawing = False
        self.selection_completed = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        painter.drawText(
            self.rect().adjusted(20, 20, -20, -20),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
            self.instruction,
        )

        if self.is_drawing:
            pen = QPen(QColor(255, 140, 0), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.setBrush(QColor(255, 140, 0, 50))

            rect = QRect(self.begin, self.end).normalized()
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin = event.position().toPoint()
            self.end = self.begin
            self.is_drawing = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = False
            rect = QRect(self.begin, self.end).normalized()

            if rect.width() > 10 and rect.height() > 10:
                zone_data = {
                    "x": rect.x(),
                    "y": rect.y(),
                    "width": rect.width(),
                    "height": rect.height(),
                }
                self.selection_completed = True
                self.selection_finished.emit(zone_data)
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, event):
        if not self.selection_completed:
            self.selection_cancelled.emit()
        event.accept()


class ParsingWorker(threading.Thread):
    """Capture only the configured loadout rectangle and recognize four slots."""

    def __init__(
        self,
        config: dict,
        callback_status: Callable[[str], None],
        callback_icon_update: Callable[
            [int, int, str | None, float, bool, list[tuple[str, float]]], None
        ],
    ) -> None:
        super().__init__(name="StratagemParser", daemon=True)
        self.config = config
        self.callback_status = callback_status
        self.callback_icon_update = callback_icon_update
        self._stop_event = threading.Event()
        self._manual_lock = threading.Lock()
        self._manual_overrides: dict[int, str] = {}
        library_dir = self.config.get("matching", {}).get(
            "stratagem_library_dir", "stratagem_library"
        )
        if not os.path.isabs(library_dir):
            library_dir = os.path.join(APP_DIR, library_dir)
        self.parser = StratagemParser(
            library_dir=library_dir,
            threshold=self.config.get("matching", {}).get("threshold", 0.65),
        )

    def set_manual_override(self, slot: int, strat_name: str | None) -> None:
        """Pin a slot to a selected candidate until automatic mode is restored."""
        with self._manual_lock:
            if strat_name:
                self._manual_overrides[slot] = strat_name
            else:
                self._manual_overrides.pop(slot, None)

    def _manual_overrides_snapshot(self) -> dict[int, str]:
        with self._manual_lock:
            return dict(self._manual_overrides)

    def run(self) -> None:
        capture_cfg = self.config.get("capture", {})
        loadout_zone = capture_cfg.get("loadout_zone")
        if not loadout_zone:
            self.callback_status("parser.region_missing")
            return

        matching_cfg = self.config.get("matching", {})
        stable_frames = max(1, int(matching_cfg.get("stable_frames", 4)))
        min_confident_slots = max(1, int(matching_cfg.get("min_confident_slots", 2)))
        monitor_index = int(capture_cfg.get("monitor_index", 1))
        loop_delay = max(0.05, float(self.config.get("loop_delay_seconds", 0.5)))
        confirmed_state = {
            int(slot): name
            for slot, name in load_last_state().items()
            if str(slot).isdigit() and isinstance(name, str) and name
        }
        pending = {slot: (None, 0) for slot in range(4)}
        local_zones = split_loadout_zone(
            {
                "x": 0,
                "y": 0,
                "width": int(loadout_zone["width"]),
                "height": int(loadout_zone["height"]),
            }
        )

        self.callback_status("parser.started")
        last_preview_at = 0.0
        try:
            with mss.MSS() as capture:
                if monitor_index >= len(capture.monitors):
                    monitor_index = 1
                monitor = capture.monitors[monitor_index]
                region = {
                    "left": monitor["left"] + int(loadout_zone["x"]),
                    "top": monitor["top"] + int(loadout_zone["y"]),
                    "width": int(loadout_zone["width"]),
                    "height": int(loadout_zone["height"]),
                }
                self._validate_region(region, monitor)

                while not self._stop_event.is_set():
                    started_at = time.monotonic()
                    screenshot = capture.grab(region)
                    frame = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_BGRA2BGR)
                    ranked_candidates: list[list[tuple[str, float]]] = []

                    for zone in local_zones:
                        x, y = zone["x"], zone["y"]
                        width, height = zone["width"], zone["height"]
                        ranked_candidates.append(
                            self.parser.score_candidates(
                                frame[y : y + height, x : x + width],
                                limit=5,
                            )
                        )

                    candidates = [
                        ranked[0] if ranked else (None, 0.0) for ranked in ranked_candidates
                    ]
                    manual_overrides = self._manual_overrides_snapshot()
                    for slot, manual_name in manual_overrides.items():
                        confirmed_state[slot] = manual_name

                    confident = [
                        (name if score >= self.parser.threshold else None, score)
                        for name, score in candidates
                    ]
                    if sum(name is not None for name, _ in confident) >= min_confident_slots:
                        changed = False
                        for slot, (name, score) in enumerate(confident):
                            if slot in manual_overrides:
                                pending[slot] = (None, 0)
                                continue
                            if name is None:
                                pending[slot] = (None, 0)
                                continue
                            pending_name, count = pending[slot]
                            count = count + 1 if pending_name == name else 1
                            pending[slot] = (name, count)
                            if count >= stable_frames and confirmed_state.get(slot) != name:
                                confirmed_state[slot] = name
                                changed = True
                                self.callback_icon_update(
                                    slot,
                                    slot,
                                    name,
                                    score,
                                    True,
                                    ranked_candidates[slot],
                                )
                        if changed:
                            save_last_state(
                                {str(slot): name for slot, name in confirmed_state.items()}
                            )
                    else:
                        pending = {slot: (None, 0) for slot in range(4)}

                    now = time.monotonic()
                    if now - last_preview_at >= 1.0:
                        for slot, (name, score) in enumerate(candidates):
                            accepted = (
                                name is not None
                                and score >= self.parser.threshold
                                and confirmed_state.get(slot) == name
                            )
                            self.callback_icon_update(
                                slot,
                                slot,
                                name,
                                score,
                                accepted,
                                ranked_candidates[slot],
                            )
                        last_preview_at = now

                    self._stop_event.wait(max(0.01, loop_delay - (time.monotonic() - started_at)))
        except Exception:
            logger.exception("Parser worker failed")
            self.callback_status("parser.failed")
        finally:
            self.callback_status("parser.stopped_message")

    @staticmethod
    def _validate_region(region: dict[str, int], monitor: dict[str, int]) -> None:
        relative_x = region["left"] - monitor["left"]
        relative_y = region["top"] - monitor["top"]
        if (
            relative_x < 0
            or relative_y < 0
            or region["width"] <= 0
            or region["height"] <= 0
            or relative_x + region["width"] > monitor["width"]
            or relative_y + region["height"] > monitor["height"]
        ):
            raise ValueError("Loadout region is outside the selected monitor")

    def stop(self) -> None:
        self._stop_event.set()


class MainWindow(QMainWindow):
    status_received = pyqtSignal(str)
    icon_received = pyqtSignal(int, int, object, float, bool, object)

    def __init__(self):
        super().__init__()
        self.config_file = os.path.join(APP_DIR, "config.json")
        self.config = self.load_config()
        language = normalized_language(self.config.get("ui", {}).get("language"))
        self.translator = Translator(language)

        self.setWindowTitle(self.tr("window.title"))
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setMinimumSize(900, 520)
        self.resize(900, 520)
        self.setStyleSheet(APP_STYLESHEET)

        self.config.setdefault("ui", {})["language"] = language
        self.config.setdefault("runtime", {})["enabled"] = False
        try:
            save_shared_config(self.config)
        except Exception as exc:
            logger.warning("Failed to synchronize the live configuration: %s", exc)

        self.worker: ParsingWorker | None = None
        self.manual_overrides: dict[int, str] = {}
        self.overlays: list[ScreenSelectorOverlay] = []
        self._localized_widgets: list[tuple[QLabel | QPushButton, str]] = []
        self._parser_running = False
        self._status_title_key = "parser.stopped"
        self._status_detail_key = "parser.idle_detail"

        self.init_ui()
        self.status_received.connect(self.statusBar_update)
        self.icon_received.connect(self.update_ui_icon)
        self.retranslate_ui()

    def tr(self, key: str, **values: object) -> str:
        return self.translator.translate(key, **values)

    def load_config(self) -> dict:
        try:
            config, _ = load_runtime_config(self.config_file)
            return config
        except Exception:
            pass
        return {
            "streamdeck": {"use_mock": True},
            "ui": {"language": "uk"},
            "runtime": {"enabled": False},
            "matching": {
                "threshold": 0.65,
                "stratagem_library_dir": "stratagem_library",
                "stable_frames": 4,
                "min_confident_slots": 2,
            },
            "capture": {
                "monitor_index": 1,
                "loadout_zone": {"x": 400, "y": 850, "width": 400, "height": 100},
            },
            "loop_delay_seconds": 0.3,
        }

    def save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            save_shared_config(self.config)
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("dialogs.error_title"),
                self.tr("dialogs.save_failed", error=e),
            )

    def _bind_text(
        self,
        widget: QLabel | QPushButton,
        key: str,
    ) -> QLabel | QPushButton:
        self._localized_widgets.append((widget, key))
        widget.setText(self.tr(key))
        return widget

    def _section_header(
        self,
        title_key: str,
        code: str,
        right_key: str = "",
    ) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(6)

        mark = QLabel("//")
        mark.setObjectName("sectionMark")
        header.addWidget(mark)

        title_label = QLabel()
        title_label.setObjectName("sectionTitle")
        self._bind_text(title_label, title_key)
        header.addWidget(title_label)

        code_label = QLabel(f"[{code}]")
        code_label.setObjectName("headerCode")
        header.addWidget(code_label)
        header.addStretch()

        if right_key:
            status_label = QLabel()
            status_label.setObjectName("headerStatus")
            self._bind_text(status_label, right_key)
            header.addWidget(status_label)
        return header

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        brand_header = QFrame()
        brand_header.setObjectName("brandHeader")
        brand_header.setFixedHeight(40)
        brand_layout = QHBoxLayout(brand_header)
        brand_layout.setContentsMargins(10, 5, 10, 5)
        brand_layout.setSpacing(8)

        brand_mark = QLabel("SE")
        brand_mark.setObjectName("brandMark")
        brand_layout.addWidget(brand_mark)

        brand_title = QLabel()
        brand_title.setObjectName("brandTitle")
        self._bind_text(brand_title, "window.brand")
        brand_layout.addWidget(brand_title)

        self.header_status_label = QLabel()
        self.header_status_label.setObjectName("parserBadge")
        self.header_status_label.setProperty("running", False)
        brand_layout.addWidget(self.header_status_label)
        brand_layout.addStretch()

        recognition_block = QFrame()
        recognition_block.setObjectName("recognitionBlock")
        recognition_layout = QHBoxLayout(recognition_block)
        recognition_layout.setContentsMargins(8, 3, 8, 3)
        recognition_layout.setSpacing(7)

        self.language_button = QPushButton()
        self.language_button.setObjectName("languageButton")
        self.language_button.setFixedWidth(42)
        self.language_button.clicked.connect(self.toggle_language)
        recognition_layout.addWidget(self.language_button)

        self.optical_label = QLabel()
        self.optical_label.setObjectName("microLabel")
        self._bind_text(self.optical_label, "window.optical_recognition")
        recognition_layout.addWidget(self.optical_label)
        brand_layout.addWidget(recognition_block)
        main_layout.addWidget(brand_header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        main_layout.addWidget(self.tabs)

        tab_control = QWidget()
        control_layout = QVBoxLayout(tab_control)
        control_layout.setContentsMargins(2, 6, 2, 0)
        control_layout.setSpacing(6)

        zones_group = QFrame()
        zones_group.setObjectName("sectionPanel")
        zones_layout = QVBoxLayout(zones_group)
        zones_layout.setContentsMargins(12, 8, 12, 8)
        zones_layout.setSpacing(6)
        zones_layout.addLayout(
            self._section_header(
                "calibration.title",
                "SE-OPT-CALIB.01",
                "calibration.buffer_ready",
            )
        )

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"color: {COLOR_BORDER};")
        zones_layout.addWidget(separator)

        self.calibration_info_label = QLabel()
        self.calibration_info_label.setObjectName("bodyText")

        zone_info = self.config.get("capture", {}).get("loadout_zone")

        calibration_row = QHBoxLayout()
        calibration_row.setSpacing(8)
        calibration_row.addWidget(self.calibration_info_label, 1)

        coordinates = QHBoxLayout()
        coordinates.setSpacing(3)
        self.zone_value_labels: dict[str, QLabel] = {}
        for key in ("x", "y", "width", "height"):
            short_name = {"x": "X", "y": "Y", "width": "W", "height": "H"}[key]
            value = int(zone_info.get(key, 0)) if zone_info else 0
            value_label = QLabel(f"{short_name} {value:03d}")
            value_label.setObjectName("coordinateValue")
            coordinates.addWidget(value_label)
            self.zone_value_labels[key] = value_label
        calibration_row.addLayout(coordinates)

        self.zone_button = QPushButton()
        self.zone_button.setObjectName("outlineButton")
        self.zone_button.setMinimumHeight(36)
        self._bind_text(self.zone_button, "calibration.select_button")
        self.zone_button.clicked.connect(lambda: start_zone_selection())
        calibration_row.addWidget(self.zone_button)
        zones_layout.addLayout(calibration_row)
        control_layout.addWidget(zones_group)

        status_group = QFrame()
        status_group.setObjectName("sectionPanel")
        status_outer_layout = QVBoxLayout(status_group)
        status_outer_layout.setContentsMargins(12, 8, 12, 8)
        status_outer_layout.setSpacing(6)

        threshold = self.config.get("matching", {}).get("threshold", 0.65)
        status_header = self._section_header(
            "slots.section_title",
            "4-SLOT BUS",
        )
        self.threshold_summary = QLabel(self.tr("format.threshold_summary", value=threshold))
        self.threshold_summary.setObjectName("headerStatus")
        status_header.addWidget(self.threshold_summary)
        status_outer_layout.addLayout(status_header)

        status_separator = QFrame()
        status_separator.setFrameShape(QFrame.Shape.HLine)
        status_separator.setStyleSheet(f"color: {COLOR_BORDER};")
        status_outer_layout.addWidget(status_separator)

        status_layout = QHBoxLayout()
        status_layout.setSpacing(7)

        self.deck_labels = []
        for i in range(4):
            card = StratagemSlotCard(i, self.translator)
            card.manual_selection_changed.connect(self._manual_selection_changed)
            status_layout.addWidget(card, 1)
            self.deck_labels.append(card)

        status_outer_layout.addLayout(status_layout, 1)
        control_layout.addWidget(status_group)

        control_bar = QFrame()
        control_bar.setObjectName("controlBar")
        control_bar.setFixedHeight(50)
        run_layout = QHBoxLayout(control_bar)
        run_layout.setContentsMargins(12, 5, 12, 5)
        run_layout.setSpacing(8)

        self.parser_state_block = QFrame()
        self.parser_state_block.setObjectName("parserStateBlock")
        self.parser_state_block.setProperty("running", False)
        parser_state_layout = QHBoxLayout(self.parser_state_block)
        parser_state_layout.setContentsMargins(8, 3, 10, 3)
        parser_state_layout.setSpacing(7)

        self.status_indicator = QLabel("■")
        self.status_indicator.setStyleSheet(f"color: {COLOR_RED}; font-size: 14px;")
        parser_state_layout.addWidget(self.status_indicator)

        status_column = QVBoxLayout()
        status_column.setSpacing(0)
        self.status_bar_label = QLabel()
        self.status_bar_label.setObjectName("statusText")
        self.status_bar_label.setProperty("running", False)
        status_column.addWidget(self.status_bar_label)
        self.status_detail_label = QLabel()
        self.status_detail_label.setObjectName("microLabel")
        status_column.addWidget(self.status_detail_label)
        parser_state_layout.addLayout(status_column)
        run_layout.addWidget(self.parser_state_block)

        run_layout.addStretch()

        self.btn_start = QPushButton()
        self.btn_start.setObjectName("primaryButton")
        self.btn_start.setProperty("running", False)
        self.btn_start.clicked.connect(self.toggle_parser)
        run_layout.addWidget(self.btn_start)

        control_layout.addWidget(control_bar)
        self.tabs.addTab(tab_control, "")

        tab_settings = QWidget()
        settings_layout = QVBoxLayout(tab_settings)
        settings_layout.setContentsMargins(2, 6, 2, 0)
        settings_layout.setSpacing(6)

        settings_panel = QFrame()
        settings_panel.setObjectName("settingsPanel")
        settings_panel_layout = QVBoxLayout(settings_panel)
        settings_panel_layout.setContentsMargins(16, 12, 16, 12)
        settings_panel_layout.setSpacing(10)
        settings_panel_layout.addLayout(
            self._section_header(
                "settings.title",
                "SE-LINK-CONFIG.02",
                "settings.bridge_ready",
            )
        )

        form_layout = QGridLayout()
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(10)
        form_layout.setColumnStretch(1, 1)

        streamdeck_title = QLabel()
        streamdeck_title.setObjectName("formLabel")
        self._bind_text(streamdeck_title, "settings.transfer")
        form_layout.addWidget(streamdeck_title, 0, 0)
        self.shared_path = shared_config_path() or self.tr("settings.localappdata_unavailable")
        self.streamdeck_info = QLabel()
        self.streamdeck_info.setObjectName("bodyText")
        self.streamdeck_info.setWordWrap(True)
        form_layout.addWidget(self.streamdeck_info, 0, 1)

        threshold_label = QLabel()
        threshold_label.setObjectName("formLabel")
        self._bind_text(threshold_label, "settings.threshold")
        form_layout.addWidget(threshold_label, 1, 0)
        self.spin_threshold = QSpinBox()
        self.spin_threshold.setRange(50, 95)
        self.spin_threshold.setSuffix(" %")
        self.spin_threshold.setValue(
            int(self.config.get("matching", {}).get("threshold", 0.65) * 100)
        )
        form_layout.addWidget(self.spin_threshold, 1, 1)

        monitor_label = QLabel()
        monitor_label.setObjectName("formLabel")
        self._bind_text(monitor_label, "settings.monitor")
        form_layout.addWidget(monitor_label, 2, 0)
        self.spin_monitor = QSpinBox()
        self.spin_monitor.setRange(1, 5)
        self.spin_monitor.setValue(self.config.get("capture", {}).get("monitor_index", 1))
        form_layout.addWidget(self.spin_monitor, 2, 1)

        settings_panel_layout.addLayout(form_layout)

        self.btn_save_settings = QPushButton()
        self.btn_save_settings.setObjectName("primaryButton")
        self._bind_text(self.btn_save_settings, "settings.save")
        self.btn_save_settings.clicked.connect(self.save_settings_from_ui)
        settings_panel_layout.addWidget(
            self.btn_save_settings,
            alignment=Qt.AlignmentFlag.AlignRight,
        )

        settings_layout.addWidget(settings_panel)
        settings_layout.addStretch()

        self.tabs.addTab(tab_settings, "")

        def start_zone_selection():
            with mss.MSS() as sct:
                mon_idx = self.config.get("capture", {}).get("monitor_index", 1)
                if mon_idx >= len(sct.monitors):
                    mon_idx = 1
                mon_geom = sct.monitors[mon_idx]

            self.showMinimized()

            def show_overlay():
                overlay = ScreenSelectorOverlay(
                    mon_geom,
                    self.tr("calibration.overlay"),
                )
                self.overlays.append(overlay)

                def cleanup_overlay(*_):
                    if overlay in self.overlays:
                        self.overlays.remove(overlay)

                def on_selected(zone_data):
                    capture = self.config.setdefault("capture", {})
                    capture["loadout_zone"] = zone_data
                    capture.pop("zones", None)
                    self.save_config()
                    self._update_zone_readout(zone_data)
                    self.showNormal()
                    self.raise_()
                    self.activateWindow()
                    self._status_title_key = "status.region_saved"
                    self._status_detail_key = "status.calibration_updated"
                    self._update_status_text()

                overlay.selection_finished.connect(on_selected)
                overlay.selection_cancelled.connect(self.showNormal)
                overlay.destroyed.connect(cleanup_overlay)
                overlay.show()
                overlay.raise_()
                overlay.activateWindow()

            QTimer.singleShot(350, show_overlay)

    def _update_zone_readout(self, zone_data: dict[str, int]) -> None:
        labels = {"x": "X", "y": "Y", "width": "W", "height": "H"}
        for key, short_name in labels.items():
            self.zone_value_labels[key].setText(f"{short_name} {int(zone_data[key]):03d}")

    def toggle_language(self) -> None:
        language = "en" if self.translator.language == "uk" else "uk"
        self.translator.set_language(language)
        self.config.setdefault("ui", {})["language"] = language
        self.save_config()
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("window.title"))
        for widget, key in self._localized_widgets:
            widget.setText(self.tr(key))

        self.tabs.setTabText(0, self.tr("tabs.control"))
        self.tabs.setTabText(1, self.tr("tabs.stream_deck"))
        self.language_button.setText("EN" if self.translator.language == "uk" else "UA")
        self.language_button.setToolTip(self.tr("window.language_tooltip"))
        self.calibration_info_label.setText(
            f"{self.tr('calibration.instruction_title')}\n{self.tr('calibration.instruction')}"
        )
        self.streamdeck_info.setText(
            f"{self.tr('settings.plugin_handles')}\n"
            f"{self.tr('settings.shared_config', path=self.shared_path)}"
        )
        threshold = self.spin_threshold.value() / 100.0
        self.threshold_summary.setText(self.tr("format.threshold_summary", value=threshold))
        self._update_status_text()
        for card in self.deck_labels:
            card.retranslate()

    def _update_status_text(self) -> None:
        self.header_status_label.setText(
            self.tr("parser.badge_online" if self._parser_running else "parser.badge_offline")
        )
        self.status_bar_label.setText(self.tr(self._status_title_key))
        self.status_detail_label.setText(self.tr(self._status_detail_key))
        self.btn_start.setText(self.tr("parser.stop" if self._parser_running else "parser.start"))

    def _set_parser_running(self, running: bool) -> None:
        self._parser_running = running
        self._status_title_key = "parser.active" if running else "parser.stopped"
        self._status_detail_key = "parser.active_detail" if running else "parser.idle_detail"
        self._update_status_text()
        self.header_status_label.setProperty("running", running)
        self.status_bar_label.setProperty("running", running)
        self.parser_state_block.setProperty("running", running)
        self.status_indicator.setStyleSheet(
            f"color: {COLOR_GREEN if running else COLOR_RED}; font-size: 14px;"
        )
        self.btn_start.setProperty("running", running)
        for widget in (
            self.header_status_label,
            self.status_bar_label,
            self.btn_start,
            self.parser_state_block,
        ):
            refresh_style(widget)

    def toggle_parser(self):
        if self.worker and self.worker.is_alive():
            self.worker.stop()
            self.worker.join(timeout=1.0)
            self.worker = None
            self.config.setdefault("runtime", {})["enabled"] = False
            self.save_config()
            self._set_parser_running(False)
        else:
            self.config = self.load_config()
            loadout_zone = self.config.get("capture", {}).get("loadout_zone")
            if not loadout_zone:
                QMessageBox.warning(
                    self,
                    self.tr("dialogs.region_missing_title"),
                    self.tr("dialogs.region_missing_text"),
                )
                return
            self.config.setdefault("runtime", {})["enabled"] = True
            self.save_config()
            self.worker = ParsingWorker(
                self.config,
                callback_status=self.status_received.emit,
                callback_icon_update=self.icon_received.emit,
            )
            for slot, strat_name in self.manual_overrides.items():
                self.worker.set_manual_override(slot, strat_name)
            self.worker.start()
            self._set_parser_running(True)

    def statusBar_update(self, msg: str):
        if msg == "parser.started":
            self._set_parser_running(True)
        elif msg in {"parser.stopped_message", "parser.failed"}:
            self._set_parser_running(False)
        self._status_detail_key = msg
        self.status_detail_label.setText(self.tr(msg))

    def update_ui_icon(
        self,
        zone_idx: int,
        button_id: int,
        strat_name: str | None,
        score: float,
        accepted: bool,
        candidates: list[tuple[str, float]],
    ) -> None:
        if 0 <= zone_idx < len(self.deck_labels):
            self.deck_labels[zone_idx].set_result(
                strat_name,
                score,
                accepted,
                candidates,
            )

    def _manual_selection_changed(
        self,
        slot: int,
        strat_name: str | None,
    ) -> None:
        if strat_name:
            self.manual_overrides[slot] = strat_name
            state = load_last_state()
            state[str(slot)] = strat_name
            save_last_state(state)
        else:
            self.manual_overrides.pop(slot, None)

        if self.worker:
            self.worker.set_manual_override(slot, strat_name)

    def save_settings_from_ui(self):
        self.config.setdefault("matching", {})["threshold"] = self.spin_threshold.value() / 100.0
        self.config.setdefault("capture", {})["monitor_index"] = self.spin_monitor.value()
        self.save_config()
        threshold = self.config["matching"]["threshold"]
        self.threshold_summary.setText(self.tr("format.threshold_summary", value=threshold))
        QMessageBox.information(
            self,
            self.tr("dialogs.success_title"),
            self.tr("dialogs.settings_saved"),
        )
        self._status_detail_key = "settings.saved"
        self.status_detail_label.setText(self.tr(self._status_detail_key))

    def closeEvent(self, event):
        if self.worker and self.worker.is_alive():
            self.worker.stop()
            self.worker.join(timeout=1.0)
            self.config.setdefault("runtime", {})["enabled"] = False
            self.save_config()
        event.accept()


def main() -> None:
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "SuperEarthEngineering.Helldivers2Stratagems.ControlCenter"
        )
    app = QApplication(sys.argv)
    app.setApplicationName("Helldivers 2 Stratagems")
    app.setOrganizationName("Super Earth Engineering")
    app.setWindowIcon(QIcon(APP_ICON_PATH))
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
