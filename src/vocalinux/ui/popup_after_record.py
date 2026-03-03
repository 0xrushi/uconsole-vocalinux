"""Popup-after-record flow.

When enabled, we do not inject text while recording. Instead we buffer the
transcript and show a review/correction popup on completion.

After the popup is closed via Enter (copy), we arm a temporary global ppp
trigger. When ppp is detected, we paste into the target window.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
import threading
import time
from typing import Optional

from gi.repository import GLib

from ..common_types import RecognitionState
from ..text_injection.text_injector import TextInjector
from ..utils.clipboard import set_clipboard_text
from .keyboard_shortcuts import KeyboardShortcutManager
from .post_record_popup import PostRecordPopup, PopupResult
from .terminal_launcher import build_terminal_launch, center_window

logger = logging.getLogger(__name__)


class PopupAfterRecordFlow:
    def __init__(
        self,
        *,
        speech_engine,
        text_injector: TextInjector,
        shortcut_manager: KeyboardShortcutManager,
        arm_seconds: float = 20.0,
        ui: str = "terminal",
    ):
        self.speech_engine = speech_engine
        self.text_injector = text_injector
        self.shortcut_manager = shortcut_manager
        self.arm_seconds = arm_seconds
        self.ui = ui

        self._in_session = False
        self._chunks = []  # list[str]
        self._armed_window_id: Optional[str] = None

        # Register callbacks
        self.speech_engine.register_state_callback(self._on_state)
        self.speech_engine.register_text_callback(self._on_text)

        # ppp paste handler (armed-only)
        self.shortcut_manager.register_paste_callback(self._on_ppp)

    def _on_text(self, text: str):
        if not self._in_session:
            return
        t = (text or "").strip()
        if not t:
            return
        self._chunks.append(t)

    def _on_state(self, state: RecognitionState):
        if state == RecognitionState.LISTENING:
            self._in_session = True
            self._chunks = []
            return

        if state == RecognitionState.IDLE and self._in_session:
            self._in_session = False
            transcript = " ".join(self._chunks).strip()

            # Capture target window before showing popup (best-effort)
            target_window_id = self.text_injector.get_active_window_id()
            logger.debug(f"popup-after-record target window: {target_window_id}")

            GLib.idle_add(self._show_popup, transcript, target_window_id)

    def _show_popup(self, transcript: str, target_window_id: Optional[str]):
        ui = (self.ui or "textual").lower()

        if ui == "gtk":

            def on_complete(result: PopupResult):
                if not set_clipboard_text(result.text):
                    logger.warning("Failed to set clipboard")
                self._armed_window_id = target_window_id
                self.shortcut_manager.arm_paste(self.arm_seconds)

            popup = PostRecordPopup(initial_text=transcript, on_complete=on_complete)
            popup.set_keep_above(True)
            popup.show_all()
            popup.present()
            return False

        # Textual UI
        try:
            td = tempfile.mkdtemp(prefix="vocalinux-popup-")
            in_path = f"{td}/input.txt"
            out_path = f"{td}/output.txt"
            with open(in_path, "w", encoding="utf-8") as f:
                f.write(transcript or "")

            python_argv = [
                sys.executable,
                "-m",
                "vocalinux.ui.textual_popup",
                "--input",
                in_path,
                "--output",
                out_path,
            ]

            spec = build_terminal_launch(python_argv=python_argv)
            proc = subprocess.Popen(spec.argv)
            threading.Thread(
                target=center_window,
                kwargs={"title": "Vocalinux", "wm_class": "vocalinux-popup"},
                daemon=True,
            ).start()

            def waiter():
                try:
                    rc = proc.wait()
                    if rc != 0:
                        return
                    try:
                        with open(out_path, "r", encoding="utf-8") as f:
                            final_text = f.read().strip()
                    except Exception:
                        final_text = ""

                    if not final_text:
                        return

                    set_clipboard_text(final_text)
                    self._armed_window_id = target_window_id
                    self.shortcut_manager.arm_paste(self.arm_seconds)
                except Exception as e:
                    logger.warning(f"Textual popup failed: {e}")

            threading.Thread(target=waiter, daemon=True).start()
        except Exception as e:
            logger.warning(f"Failed to launch popup: {e}")

        return False

    def _on_ppp(self):
        window_id = self._armed_window_id
        self._armed_window_id = None

        if window_id:
            self.text_injector.activate_window(window_id)
            time.sleep(0.15)

        # Best-effort: remove the literal 'ppp' that was typed.
        try:
            self.text_injector.inject_text("\b" * 3)
            time.sleep(0.05)
        except Exception:
            pass

        ok = self.text_injector._inject_keyboard_shortcut("ctrl+v")
        if not ok:
            logger.warning("Paste injection failed (ctrl+v)")
