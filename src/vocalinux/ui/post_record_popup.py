"""Popup window shown after recording completes (popup-after-record mode)."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Callable, Optional

try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk, GLib, Gtk  # noqa: E402
except Exception:  # pragma: no cover - GTK not available in some test envs
    Gdk = GLib = Gtk = None

from ..llm.gemini_client import GeminiClient, GeminiRequest, GeminiUsage
from ..llm.llm_config import load_llm_config
from ..llm.prompts import prompt_correct_bash, prompt_correct_email, prompt_correct_post

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PopupResult:
    text: str


_BASE_WINDOW = Gtk.Window if isinstance(getattr(Gtk, "Window", None), type) else object


class PostRecordPopup(_BASE_WINDOW):
    def __init__(
        self,
        *,
        initial_text: str,
        on_complete: Callable[[PopupResult], None],
        title: str = "Vocalinux - Review Transcript",
    ):
        super().__init__(title=title)
        self.set_default_size(720, 420)
        self.set_border_width(14)
        self.set_position(Gtk.WindowPosition.CENTER)

        self._on_complete = on_complete
        self._command_mode = False
        self._busy = False

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(outer)

        header = Gtk.Label()
        header.set_markup(
            "<b>Recording complete.</b> Edit the text, then press <b>Esc</b> for hotkeys. "
            "In hotkey mode: <b>a</b>/<b>b</b>/<b>c</b> to correct, <b>Enter</b> to copy &amp; close."
        )
        header.set_halign(Gtk.Align.START)
        header.set_line_wrap(True)
        outer.pack_start(header, False, False, 0)

        self._mode_label = Gtk.Label(label="Mode: Edit")
        self._mode_label.set_halign(Gtk.Align.START)
        outer.pack_start(self._mode_label, False, False, 0)

        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        outer.pack_start(scroller, True, True, 0)

        self._textview = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self._buffer = self._textview.get_buffer()
        self._buffer.set_text(initial_text or "")
        scroller.add(self._textview)

        labels = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        outer.pack_start(labels, False, False, 0)

        self._label_email = Gtk.Label()
        self._label_email.set_markup("<b>[A] Correct for email</b>")
        self._label_post = Gtk.Label()
        self._label_post.set_markup("<b>[B] Correct for post/message</b>")
        self._label_bash = Gtk.Label()
        self._label_bash.set_markup("<b>[C] Correct bash command</b>")
        self._label_copy = Gtk.Label()
        self._label_copy.set_markup("<b>[Enter] Copy &amp; Close</b>")

        # Center align all labels
        for label in [self._label_email, self._label_post, self._label_bash, self._label_copy]:
            label.set_halign(Gtk.Align.CENTER)

        labels.pack_start(self._label_email, True, True, 0)
        labels.pack_start(self._label_post, True, True, 0)
        labels.pack_start(self._label_bash, True, True, 0)
        labels.pack_start(self._label_copy, True, True, 0)

        self._status = Gtk.Label(label="")
        self._status.set_halign(Gtk.Align.START)
        self._status.set_line_wrap(True)
        outer.pack_start(self._status, False, False, 0)

        self.connect("key-press-event", self._on_key_press)
        self.connect("delete-event", self._on_delete)

        self._update_mode_ui()

    def _on_delete(self, *_args):
        # Close without completing
        return False

    def _on_key_press(self, _widget, event: Gdk.EventKey):
        keyval = event.keyval
        logger.debug(f"Key pressed: {keyval}, current mode: {self._command_mode}")

        if keyval == Gdk.KEY_Escape:
            self._command_mode = not self._command_mode
            self._update_mode_ui()
            return True

        if not self._command_mode:
            return False

        # Hotkey mode
        if keyval in (Gdk.KEY_a, Gdk.KEY_A):
            self._trigger_correct("email")
            return True
        if keyval in (Gdk.KEY_b, Gdk.KEY_B):
            self._trigger_correct("post")
            return True
        if keyval in (Gdk.KEY_c, Gdk.KEY_C):
            self._trigger_correct("bash")
            return True

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._copy_and_close()
            return True

        return False

    def _set_status(self, text: str, *, is_error: bool = False):
        if not text:
            self._status.set_markup("")
            return
        if is_error:
            self._status.set_markup(
                f"<span foreground='red'>{GLib.markup_escape_text(text)}</span>"
            )
        else:
            self._status.set_markup(
                f"<span foreground='gray'>{GLib.markup_escape_text(text)}</span>"
            )

    def _update_mode_ui(self):
        if self._command_mode:
            self._mode_label.set_markup("Mode: <b>Hotkeys</b> (a/b/c, Enter)")
        else:
            self._mode_label.set_markup("Mode: <b>Edit</b> (Esc for hotkeys)")

    def _get_text(self) -> str:
        start = self._buffer.get_start_iter()
        end = self._buffer.get_end_iter()
        return self._buffer.get_text(start, end, False)

    def _set_text(self, text: str):
        self._buffer.set_text(text or "")

    def _trigger_correct(self, mode: str):
        if self._busy:
            return

        current_text = self._get_text().strip()
        if not current_text:
            self._set_status("Nothing to correct.", is_error=True)
            return

        self._busy = True
        self._update_mode_ui()
        self._set_status("Calling LLM…")

        threading.Thread(
            target=self._correct_in_thread, args=(mode, current_text), daemon=True
        ).start()

    def _correct_in_thread(self, mode: str, text: str):
        try:
            cfg = load_llm_config()
            if cfg.provider != "gemini":
                raise RuntimeError(f"Unsupported LLM provider: {cfg.provider}")

            if mode == "email":
                prompt = prompt_correct_email(text)
            elif mode == "post":
                prompt = prompt_correct_post(text)
            elif mode == "bash":
                prompt = prompt_correct_bash(text)
            else:
                raise RuntimeError(f"Unknown correction mode: {mode}")

            logger.info(f"Gemini prompt ({mode}):\n{prompt}")
            client = GeminiClient()
            result = client.generate_text_with_usage(
                GeminiRequest(
                    model=cfg.model,
                    api_key=cfg.api_key,
                    prompt=prompt,
                    temperature=cfg.temperature,
                    timeout_seconds=cfg.timeout_seconds,
                )
            )

            if not result.text:
                raise RuntimeError("LLM returned empty output")

            GLib.idle_add(self._on_correct_success, result.text, result.usage)
        except Exception as e:
            GLib.idle_add(self._on_correct_error, str(e))

    def _on_correct_success(self, out: str, usage=None):
        self._set_text(out)
        tokens_msg = ""
        if usage and usage.total_tokens is not None:
            tokens_msg = f" tokens={usage.total_tokens}"
        self._set_status(f"Updated.{tokens_msg}")
        self._busy = False
        self._update_mode_ui()
        return False

    def _on_correct_error(self, err: str):
        self._set_status(err, is_error=True)
        self._busy = False
        self._update_mode_ui()
        return False

    def _copy_and_close(self):
        if self._busy:
            return

        text = self._get_text().strip()
        if not text:
            self._set_status("Nothing to copy.", is_error=True)
            return

        try:
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(text, -1)
            clipboard.store()
        except Exception as e:
            self._set_status(f"Failed to copy to clipboard: {e}", is_error=True)
            return

        try:
            self._on_complete(PopupResult(text=text))
        finally:
            self.destroy()
